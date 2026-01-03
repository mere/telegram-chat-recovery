#!/usr/bin/env python3
"""
Create a mapping between messages and their media files.
This creates an index so you can quickly find media files for each message.
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict


def parse_media_ids(media_obj):
    """Extract all possible media IDs from embedded media object"""
    if not isinstance(media_obj, dict):
        return []
    
    media_ids = []
    
    # TelegramMediaImage - check 'r' field for representations
    if 'r' in media_obj and isinstance(media_obj['r'], list):
        for rep in media_obj['r']:
            if isinstance(rep, dict) and 'r' in rep:
                res = rep['r']
                # Photo resource has 'd' (datacenter), 'i' (photo_id), 's' (size)
                if 'd' in res and 'i' in res:
                    dc = res['d']
                    photo_id = res['i']
                    size = res.get('s', 'x')
                    media_ids.append(f"telegram-cloud-photo-size-{dc}-{photo_id}-{size}")
    
    # TelegramMediaFile - check for document resource
    if 'r' in media_obj and isinstance(media_obj['r'], dict):
        res = media_obj['r']
        # Document resource has 'd' (datacenter), 'f' (file_id)
        if 'd' in res and 'f' in res:
            dc = res['d']
            file_id = res['f']
            media_ids.append(f"telegram-cloud-document-{dc}-{file_id}")
    
    return media_ids


def extract_referenced_media_id(ref):
    """Convert referenced media ID to filename"""
    if not isinstance(ref, dict):
        return None
    
    namespace = ref.get('namespace')
    media_id = ref.get('id')
    
    if namespace is not None and media_id is not None:
        return f"telegram-cloud-document-{namespace}-{media_id}"
    
    return None


def find_media_file(media_id, source_dir):
    """Find media file in source directory"""
    if not media_id:
        return None
    
    source_path = Path(source_dir)
    
    # Try exact match first
    exact_path = source_path / media_id
    if exact_path.exists():
        return str(exact_path)
    
    # Try with wildcards (some files have extensions or suffixes)
    matches = list(source_path.glob(f"{media_id}*"))
    if matches:
        return str(matches[0])
    
    # Try in cache directories
    for cache_dir in ['cache', 'cache-storage']:
        cache_path = source_path / cache_dir / media_id
        if cache_path.exists():
            return str(cache_path)
        
        # Try with wildcard in cache
        cache_dir_path = source_path / cache_dir
        if cache_dir_path.exists():
            matches = list(cache_dir_path.glob(f"{media_id}*"))
            if matches:
                return str(matches[0])
    
    # Try in all subdirectories as last resort
    for subdir in source_path.iterdir():
        if subdir.is_dir():
            matches = list(subdir.glob(f"{media_id}*"))
            if matches:
                return str(matches[0])
    
    return None


def get_media_info(file_path):
    """Get media file info"""
    if not file_path or not Path(file_path).exists():
        return None
    
    path = Path(file_path)
    stat = path.stat()
    
    # Determine type from extension or file command
    ext = path.suffix.lower()
    media_type = 'unknown'
    
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        media_type = 'image'
    elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
        media_type = 'video'
    elif ext in ['.mp3', '.m4a', '.ogg', '.wav']:
        media_type = 'audio'
    elif ext in ['.pdf', '.doc', '.docx', '.txt']:
        media_type = 'document'
    elif 'photo' in path.name:
        media_type = 'image'
    elif 'document' in path.name:
        media_type = 'file'
    
    return {
        'path': str(path),
        'filename': path.name,
        'size': stat.st_size,
        'size_mb': round(stat.st_size / (1024**2), 2),
        'type': media_type,
        'extension': ext
    }


def create_media_index(messages_file, media_source_dir, output_file):
    """Create media index from messages and media directory"""
    
    print("="*80)
    print("Creating Media Index")
    print("="*80)
    print()
    
    # Load messages
    print(f"Loading messages from {messages_file}...")
    with open(messages_file, 'r', encoding='utf-8') as f:
        messages = json.load(f)
    
    print(f"Loaded {len(messages)} messages")
    print()
    
    # Process each message
    print("Building media index...")
    media_index = []
    stats = defaultdict(int)
    
    for idx, msg in enumerate(messages):
        if (idx + 1) % 1000 == 0:
            print(f"Processed {idx + 1}/{len(messages)} messages...", end='\r')
        
        msg_id = msg['id']
        msg_date = msg['date']
        msg_time = msg['time']
        tags = msg.get('tags', [])
        
        message_media = {
            'message_id': msg_id,
            'date': msg_date,
            'time': msg_time,
            'datetime': msg['datetime'],
            'direction': msg['direction'],
            'text_preview': msg['text'][:100] if msg['text'] else '',
            'tags': tags,
            'media_files': []
        }
        
        # Process embedded media
        for media in msg.get('embeddedMedia', []):
            media_ids = parse_media_ids(media)
            for media_id in media_ids:
                file_path = find_media_file(media_id, media_source_dir)
                if file_path:
                    media_info = get_media_info(file_path)
                    if media_info:
                        media_info['media_id'] = media_id
                        media_info['source'] = 'embedded'
                        message_media['media_files'].append(media_info)
                        stats['found'] += 1
                else:
                    stats['not_found'] += 1
        
        # Process referenced media
        for ref in msg.get('referencedMediaIds', []):
            media_id = extract_referenced_media_id(ref)
            if media_id:
                file_path = find_media_file(media_id, media_source_dir)
                if file_path:
                    media_info = get_media_info(file_path)
                    if media_info:
                        media_info['media_id'] = media_id
                        media_info['source'] = 'referenced'
                        message_media['media_files'].append(media_info)
                        stats['found'] += 1
                else:
                    stats['not_found'] += 1
        
        # Only include messages that have media
        if message_media['media_files']:
            media_index.append(message_media)
            stats['messages_with_media'] += 1
    
    print()
    print()
    
    # Save index
    print(f"Saving media index to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(media_index, f, indent=2)
    
    # Calculate total size
    total_size = sum(
        media['size'] 
        for msg in media_index 
        for media in msg['media_files']
    )
    
    print()
    print("="*80)
    print("MEDIA INDEX CREATED")
    print("="*80)
    print()
    print(f"Output: {output_file}")
    print()
    print(f"Statistics:")
    print(f"  Messages with media: {stats['messages_with_media']}")
    print(f"  Media files found: {stats['found']}")
    print(f"  Media files not found: {stats['not_found']}")
    print(f"  Total size: {total_size / (1024**3):.2f} GB")
    print()
    
    return media_index


def main():
    if len(sys.argv) < 4:
        print("Usage: python create_media_index.py <messages_json> <media_source_dir> <output_json>")
        print("\nExample:")
        print("  python create_media_index.py messages.json /path/to/backup/postbox/media media_index.json")
        sys.exit(1)
    
    messages_file = sys.argv[1]
    media_source_dir = sys.argv[2]
    output_file = sys.argv[3]
    
    media_index = create_media_index(messages_file, media_source_dir, output_file)
    
    if media_index:
        print("Sample entry:")
        print(json.dumps(media_index[len(media_index)//2], indent=2)[:500])
        print("...")
    
    print()
    print("You can now use this index to find media files for any message!")
    print()

if __name__ == '__main__':
    main()
