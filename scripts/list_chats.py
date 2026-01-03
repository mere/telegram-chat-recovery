#!/usr/bin/env python3
import sqlite3
import struct
import sys
import io
import enum
import mmh3

class byteutil:
    def __init__(self, buffer, endian='<'):
        self.endian = endian
        self.buf = buffer

    def read_fmt(self, fmt):
        fmt = self.endian + fmt
        data = self.buf.read(struct.calcsize(fmt))
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
            value = {'type': typeHash, 'data': data}
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
            value = self.bio.read_bytes()
        elif valueType == self.ValueType.Nil:
            pass  # Nil is None
        elif valueType == self.ValueType.StringArray:
            alen = self.bio.read_int32()
            value = [self.bio.read_str() for _ in range(alen)]
        elif valueType == self.ValueType.BytesArray:
            alen = self.bio.read_int32()
            value = [self.bio.read_bytes() for _ in range(alen)]
        else:
            raise Exception('unknown value type')
        return valueType, value


db_path = '/Users/zoltanbourne/TGbackup/database_backup/original/plaintext.db'
con = sqlite3.connect(db_path)

print("Listing all peers in the database:\n")
print(f"{'ID':<20} {'First Name':<20} {'Last Name':<20} {'Username':<20}")
print("-" * 80)

cur = con.cursor()
cur.execute("SELECT key, value FROM t2")
count = 0
for key, value in cur:
    try:
        data = PostboxDecoder(value).decodeRootObject()
        if data is None:
            continue
        fn = data.get('fn', '')
        ln = data.get('ln', '')
        un = data.get('un', '')
        
        if fn or ln or un:
            # Key might be int or bytes
            if isinstance(key, bytes):
                peer_id = key.decode('utf-8', errors='replace')
            else:
                peer_id = str(key)
            print(f"{peer_id:<20} {fn:<20} {ln:<20} {un:<20}")
            count += 1
    except Exception as e:
        print(f"Error decoding: {e}")
        import traceback
        traceback.print_exc()
        if count > 2:  # Only show first few errors
            break

print(f"\n\nTotal peers found: {count}")
cur.close()
con.close()
