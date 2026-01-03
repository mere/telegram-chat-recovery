#!/usr/bin/env python3
"""
Extract COMPLETE message data from a Telegram chat including:
- Text content
- Media (images, videos, files, voice)
- Attributes (links, mentions, formatting)
- Forwarded messages
- Reply information
- Everything needed for UI visualization
"""

import sqlite3
import struct
import datetime
import json
import sys
import io
import enum
import mmh3

# ============================================================================
# UTILITY CLASSES
# ============================================================================

class byteutil:
    def __init__(self, buffer, endian='<'):
        self.endian = endian
        self.buf = buffer

    def read_fmt(self, fmt):
        fmt = self.endian + fmt
        data = self.buf.read(struct.calcsize(fmt))
        if len(data) < struct.calcsize(fmt):
            raise EOFError("Not enough data")
        return struct.unpack(fmt, data)[0]

    def read_int8(self):
        return self.read_fmt('b')
    def read_uint8(self):
        return self.read_fmt('B')
    def read_int32(self):
        return self.read_fmt('i')
    def read_uint32(self):
        return self.read_fmt('I')
    def read_int64(self):
        return self.read_fmt('q')
    def read_uint64(self):
        return self.read_fmt('Q')
    def read_bytes(self):
        slen = self.read_int32()
        return self.buf.read(slen)
    def read_str(self):
        return self.read_bytes().decode('utf-8', errors='replace')
    def read_short_bytes(self):
        slen = self.read_uint8()
        return self.buf.read(slen)
    def read_short_str(self):
        return self.read_short_bytes().decode('utf-8', errors='replace')
    def read_double(self):
        return self.read_fmt('d')


class PostboxDecoder:
    registry = {}
    
    @classmethod
    def registerDecoder(cls, t):
        cls.registry[mmh3.hash(t.__name__, seed=0xf7ca7fd2)] = t
        return t

    class ValueType(enum.Enum):
        Int32 = 0
        Int64 = 1
        Bool = 2
        Double = 3
        String = 4
        Object = 5
        Int32Array = 6
        Int64Array = 7
        ObjectArray = 8
        ObjectDictionary = 9
        Bytes = 10
        Nil = 11
        StringArray = 12
        BytesArray = 13
    
    def __init__(self, data):
        self.bio = byteutil(io.BytesIO(data), endian='<')
        self.size = len(data)

    def decodeRootObject(self):
        return self.decodeObjectForKey('_')

    def decodeObjectForKey(self, key):
        t, v = self.get(self.ValueType.Object, key)
        if v:
            return v

    def get(self, valueType, key, decodeObjects=None):
        for k, t, v in self._iter_kv(decodeObjects=decodeObjects):
            if k != key:
                pass
            elif valueType == None:
                return t, v
            elif t == valueType:
                return t, v
            elif t == self.ValueType.Nil:
                return t, None
        return None, None
    
    def _iter_kv(self, decodeObjects=None, registry=None):
        self.bio.buf.seek(0, io.SEEK_SET)
        while True:
            pos = self.bio.buf.tell()
            if pos >= self.size:
                break
    
            key = self.bio.read_short_str()
            valueType, value = self.readValue(decodeObjects=decodeObjects, registry=registry)
            yield key, valueType, value

    def _readObject(self, decode=None, registry=None):
        if decode is None:
            decode = True
        if registry is None:
            registry = self.registry

        typeHash = self.bio.read_int32()
        dataLen = self.bio.read_int32()
        data = self.bio.buf.read(dataLen)

        if not decode:
            value = {'type': typeHash, 'data': data.hex()}
        elif typeHash in self.registry:
            decoder = self.__class__(data)
            value = self.registry[typeHash](decoder)
        else:
            decoder = self.__class__(data)
            value = {k: v for k, t, v in decoder._iter_kv()}
            value['@type'] = typeHash

        return value

    def readValue(self, decodeObjects=None, registry=None):
        valueType = self.ValueType(self.bio.read_uint8())
        value = None
        
        objectArgs = {'decode': decodeObjects, 'registry': registry}

        if valueType == self.ValueType.Int32:
            value = self.bio.read_int32()
        elif valueType == self.ValueType.Int64:
            value = self.bio.read_int64()
        elif valueType == self.ValueType.Bool:
            value = self.bio.read_uint8() != 0
        elif valueType == self.ValueType.Double:
            value = self.bio.read_double()
        elif valueType == self.ValueType.String:
            value = self.bio.read_str()
        elif valueType == self.ValueType.Object:
            value = self._readObject(**objectArgs)
        elif valueType == self.ValueType.Int32Array:
            alen = self.bio.read_int32()
            value = [self.bio.read_int32() for _ in range(alen)]
        elif valueType == self.ValueType.Int64Array:
            alen = self.bio.read_int32()
            value = [self.bio.read_int64() for _ in range(alen)]
        elif valueType == self.ValueType.ObjectArray:
            alen = self.bio.read_int32()
            value = [self._readObject(**objectArgs) for _ in range(alen)]
        elif valueType == self.ValueType.ObjectDictionary:
            dlen = self.bio.read_int32()
            value = [(self._readObject(**objectArgs), self._readObject(**objectArgs)) for _ in range(dlen)]
        elif valueType == self.ValueType.Bytes:
            data = self.bio.read_bytes()
            # Convert bytes to hex string for JSON serialization
            value = data.hex() if data else None
        elif valueType == self.ValueType.Nil:
            pass  # Nil is None
        elif valueType == self.ValueType.StringArray:
            alen = self.bio.read_int32()
            value = [self.bio.read_str() for _ in range(alen)]
        elif valueType == self.ValueType.BytesArray:
            alen = self.bio.read_int32()
            value = [self.bio.read_bytes().hex() for _ in range(alen)]
        else:
            raise Exception('unknown value type')
        return valueType, value


# ============================================================================
# MESSAGE PARSING
# ============================================================================

class MessageIndex:
    def __init__(self, peerId, namespace, mid, timestamp):
        self.peerId = peerId
        self.namespace = namespace
        self.id = mid
        self.timestamp = timestamp
    
    @classmethod
    def from_bytes(cls, b):
        bio = byteutil(io.BytesIO(b), endian='>')
        peerId = bio.read_int64()
        namespace = bio.read_int32()
        timestamp = bio.read_int32()
        mid = bio.read_int32()
        return cls(peerId, namespace, mid, timestamp)


class MessageFlags(enum.IntFlag):
    Unsent = 1
    Failed = 2
    Incoming = 4
    TopIndexable = 16
    Sending = 32
    CanBeGroupedIntoFeed = 64
    WasScheduled = 128
    CountedAsIncoming = 256


class MessageDataFlags(enum.IntFlag):
    GloballyUniqueId = 1 << 0
    GlobalTags = 1 << 1
    GroupingKey = 1 << 2
    GroupInfo = 1 << 3
    LocalTags = 1 << 4
    ThreadId = 1 << 5


class MessageTags(enum.IntFlag):
    PhotoOrVideo = 1 << 0
    File = 1 << 1
    Music = 1 << 2
    WebPage = 1 << 3
    VoiceOrInstantVideo = 1 << 4
    UnseenPersonalMessage = 1 << 5
    LiveLocation = 1 << 6
    Gif = 1 << 7
    Photo = 1 << 8
    Video = 1 << 9
    Pinned = 1 << 10


class FwdInfoFlags(enum.IntFlag):
    SourceId = 1 << 1
    SourceMessage = 1 << 2
    Signature = 1 << 3
    PsaType = 1 << 4
    Flags = 1 << 5


def read_intermediate_fwd_info(buf):
    infoFlags = FwdInfoFlags(buf.read_int8())
    if infoFlags == 0:
        return None

    authorId = buf.read_int64()
    date = buf.read_int32()

    sourceId = None
    if FwdInfoFlags.SourceId in infoFlags:
        sourceId = buf.read_int64()

    sourceMessagePeerId = None
    sourceMessageNamespace = None
    sourceMessageIdId = None
    if FwdInfoFlags.SourceMessage in infoFlags:
        sourceMessagePeerId = buf.read_int64()
        sourceMessageNamespace = buf.read_int32()
        sourceMessageIdId = buf.read_int32()
    
    signature = None
    if FwdInfoFlags.Signature in infoFlags:
        signature = buf.read_str()
    
    psaType = None
    if FwdInfoFlags.PsaType in infoFlags:
        psaType = buf.read_str()
    
    flags = None
    if FwdInfoFlags.Flags in infoFlags:
        flags = buf.read_int32()
    
    return {
        'authorId': authorId,
        'date': date,
        'sourceId': sourceId,
        'sourceMessagePeerId': sourceMessagePeerId,
        'sourceMessageNamespace': sourceMessageNamespace,
        'sourceMessageIdId': sourceMessageIdId,
        'signature': signature,
        'psaType': psaType,
        'flags': flags,
    }


def read_intermediate_message_complete(v: bytes):
    """Complete message parsing - extract ALL data"""
    buf = byteutil(io.BytesIO(v))
    
    try:
        typ = buf.read_int8()
        if typ != 0:
            return None

        stableId = buf.read_uint32()
        stableVer = buf.read_uint32()
        
        dataFlags = MessageDataFlags(buf.read_uint8())
        
        globallyUniqueId = None
        if MessageDataFlags.GloballyUniqueId in dataFlags:
            globallyUniqueId = buf.read_int64()
        
        globalTags = None
        if MessageDataFlags.GlobalTags in dataFlags:
            globalTags = buf.read_uint32()
        
        groupingKey = None
        if MessageDataFlags.GroupingKey in dataFlags:
            groupingKey = buf.read_int64()
        
        groupInfoStableId = None
        if MessageDataFlags.GroupInfo in dataFlags:
            groupInfoStableId = buf.read_uint32()

        localTagsVal = None
        if MessageDataFlags.LocalTags in dataFlags:
            localTagsVal = buf.read_uint32()
        
        threadId = None
        if MessageDataFlags.ThreadId in dataFlags:
            threadId = buf.read_int64()
        
        flags = MessageFlags(buf.read_uint32())
        tags = MessageTags(buf.read_uint32())
        
        fwd_info = read_intermediate_fwd_info(buf)

        authorId = None
        hasAuthorId = buf.read_int8()
        if hasAuthorId == 1:
            authorId = buf.read_int64()
        
        text = buf.read_str()

        # Read attributes (contains links, mentions, formatting, etc.)
        attributesCount = buf.read_int32()
        attributes = []
        for _ in range(attributesCount):
            attr_data = buf.read_bytes()
            try:
                attr = PostboxDecoder(attr_data).decodeRootObject()
                attributes.append(attr)
            except:
                attributes.append({'raw': attr_data.hex()})

        # Read embedded media (photos, videos, files, etc.)
        embeddedMediaCount = buf.read_int32()
        embeddedMedia = []
        for _ in range(embeddedMediaCount):
            media_data = buf.read_bytes()
            try:
                media = PostboxDecoder(media_data).decodeRootObject()
                embeddedMedia.append(media)
            except:
                embeddedMedia.append({'raw': media_data.hex()})
        
        # Read referenced media IDs
        referencedMediaIds = []
        referencedMediaIdsCount = buf.read_int32()
        for _ in range(referencedMediaIdsCount):
            idNamespace = buf.read_int32()
            idId = buf.read_int64()
            referencedMediaIds.append({
                'namespace': idNamespace,
                'id': idId
            })

        # Parse tags into readable format
        tag_list = []
        for tag in MessageTags:
            if tag in tags:
                tag_list.append(tag.name)
        
        # Parse flags into readable format
        flag_list = []
        for flag in MessageFlags:
            if flag in flags:
                flag_list.append(flag.name)

        return {
            'stableId': stableId,
            'stableVersion': stableVer,
            'globallyUniqueId': globallyUniqueId,
            'authorId': authorId,
            'text': text,
            'flags': flag_list,
            'tags': tag_list,
            'forwarded': fwd_info,
            'attributes': attributes,
            'embeddedMedia': embeddedMedia,
            'referencedMediaIds': referencedMediaIds,
            'groupingKey': groupingKey,
            'threadId': threadId,
            'globalTags': globalTags,
            'localTags': localTagsVal,
        }
    
    except Exception as e:
        return {
            'error': str(e),
            'raw_hex': v.hex()[:200]  # First 100 bytes for debugging
        }


def get_peer_info(con, peer_id, cache={}):
    """Get peer information"""
    if peer_id in cache:
        return cache[peer_id]
    
    if peer_id is None:
        return None
    
    cur = con.cursor()
    try:
        cur.execute("SELECT value FROM t2 WHERE key = ? ORDER BY key LIMIT 1", (str(peer_id),))
        v = cur.fetchone()
        if v is None:
            cache[peer_id] = {'id': peer_id, 'unknown': True}
            return cache[peer_id]
        
        try:
            data = PostboxDecoder(v[0]).decodeRootObject()
            peer_info = {
                'id': peer_id,
                'firstName': data.get('fn', ''),
                'lastName': data.get('ln', ''),
                'username': data.get('un', ''),
                'phone': data.get('ph', ''),
            }
            cache[peer_id] = peer_info
            return peer_info
        except:
            cache[peer_id] = {'id': peer_id, 'parseError': True}
            return cache[peer_id]
    finally:
        cur.close()


# ============================================================================
# MAIN EXTRACTION
# ============================================================================

def extract_complete_chat(db_path, peer_id, output_file):
    """Extract complete chat with all data"""
    
    con = sqlite3.connect(db_path)
    
    print(f"Extracting COMPLETE data from peer {peer_id}...")
    print("This includes: text, media, attributes, links, formatting, forwarded info, etc.")
    print()
    
    messages = []
    cur = con.cursor()
    cur.execute("SELECT key, value FROM t7 ORDER BY key")
    
    total_processed = 0
    extracted = 0
    
    for key, value in cur:
        total_processed += 1
        
        if total_processed % 1000 == 0:
            print(f"Processed {total_processed} messages, extracted {extracted}...", end='\r')
        
        try:
            idx = MessageIndex.from_bytes(key)
            
            # Filter by peer ID
            if idx.peerId != peer_id:
                continue
            
            msg = read_intermediate_message_complete(value)
            if msg is None:
                continue
            
            # Get author info if available
            author_info = None
            if msg.get('authorId'):
                author_info = get_peer_info(con, msg['authorId'])
            
            # Get forwarded author info if available
            if msg.get('forwarded') and msg['forwarded'].get('authorId'):
                msg['forwarded']['authorInfo'] = get_peer_info(con, msg['forwarded']['authorId'])
            
            ts = datetime.datetime.fromtimestamp(idx.timestamp)
            
            message_data = {
                'id': idx.id,
                'namespace': idx.namespace,
                'timestamp': idx.timestamp,
                'datetime': ts.isoformat(),
                'date': ts.strftime('%Y-%m-%d'),
                'time': ts.strftime('%H:%M:%S'),
                'direction': 'received' if 'Incoming' in msg.get('flags', []) else 'sent',
                'author': author_info,
                'text': msg.get('text', ''),
                'flags': msg.get('flags', []),
                'tags': msg.get('tags', []),
                'forwarded': msg.get('forwarded'),
                'attributes': msg.get('attributes', []),
                'embeddedMedia': msg.get('embeddedMedia', []),
                'referencedMediaIds': msg.get('referencedMediaIds', []),
                'metadata': {
                    'stableId': msg.get('stableId'),
                    'globallyUniqueId': msg.get('globallyUniqueId'),
                    'groupingKey': msg.get('groupingKey'),
                    'threadId': msg.get('threadId'),
                }
            }
            
            messages.append(message_data)
            extracted += 1
            
        except Exception as e:
            continue

    cur.close()
    con.close()
    
    print(f"\nProcessed {total_processed} total messages")
    print(f"Extracted {extracted} messages from peer {peer_id}")
    print()
    
    # Save to JSON with pretty printing
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved to: {output_file}")
    print()
    
    return messages


# ============================================================================
# ANALYZE AND REPORT
# ============================================================================

def analyze_messages(messages):
    """Analyze the extracted messages"""
    
    total = len(messages)
    if total == 0:
        print("No messages found!")
        return
    
    with_text = sum(1 for m in messages if m['text'])
    with_media = sum(1 for m in messages if m['embeddedMedia'] or m['referencedMediaIds'])
    with_attributes = sum(1 for m in messages if m['attributes'])
    forwarded = sum(1 for m in messages if m['forwarded'])
    
    # Count by tag
    tag_counts = {}
    for msg in messages:
        for tag in msg.get('tags', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    print("="*80)
    print("MESSAGE ANALYSIS")
    print("="*80)
    print()
    print(f"Total messages: {total}")
    print(f"  With text: {with_text} ({100*with_text/total:.1f}%)")
    print(f"  With media: {with_media} ({100*with_media/total:.1f}%)")
    print(f"  With attributes: {with_attributes} ({100*with_attributes/total:.1f}%)")
    print(f"  Forwarded: {forwarded} ({100*forwarded/total:.1f}%)")
    print()
    
    if tag_counts:
        print("Message types:")
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            print(f"  {tag}: {count}")
    print()
    
    if messages:
        print(f"Date range: {messages[0]['date']} to {messages[-1]['date']}")
    
    print("="*80)


# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 4:
        print("Usage: python extract_messages.py <db_path> <peer_id> <output_file>")
        print("\nExample:")
        print("  python extract_messages.py plaintext.db 126459430 messages.json")
        sys.exit(1)
    
    db_path = sys.argv[1]
    peer_id = int(sys.argv[2])
    output_file = sys.argv[3]
    
    messages = extract_complete_chat(db_path, peer_id, output_file)
    analyze_messages(messages)
    
    print()
    print("You can now use this JSON to build your UI!")

if __name__ == '__main__':
    main()
