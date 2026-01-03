#!/usr/bin/env python3
"""
Telegram Chat Recovery Tool
Recovers deleted chats from local macOS Telegram database
"""

import os
import sys
import argparse
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from decrypt_database import decrypt_database
from extract_messages import extract_chat_messages
from create_media_index import create_media_index
from list_chats import list_all_chats


def main():
    parser = argparse.ArgumentParser(
        description='Recover deleted Telegram chats from local macOS database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all chats
  python3 recover.py list --database /path/to/backup/db_sqlite
  
  # Recover specific chat
  python3 recover.py extract --database /path/to/backup/db_sqlite --name "John Doe"
  
  # Full recovery pipeline
  python3 recover.py full --backup /path/to/telegram_backup --name "John Doe"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all chats in database')
    list_parser.add_argument('--database', required=True, help='Path to db_sqlite file')
    list_parser.add_argument('--key-file', help='Path to .tempkeyEncrypted file (default: same directory as database)')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract specific chat')
    extract_parser.add_argument('--database', required=True, help='Path to db_sqlite file')
    extract_parser.add_argument('--key-file', help='Path to .tempkeyEncrypted file')
    extract_parser.add_argument('--name', help='Name of person to search for')
    extract_parser.add_argument('--username', help='Username to search for')
    extract_parser.add_argument('--peer-id', type=int, help='Specific peer ID')
    extract_parser.add_argument('--output', default='./output', help='Output directory')
    extract_parser.add_argument('--with-media', action='store_true', help='Also extract media files')
    
    # Full command
    full_parser = subparsers.add_parser('full', help='Full recovery pipeline')
    full_parser.add_argument('--backup', required=True, help='Path to backup directory')
    full_parser.add_argument('--name', help='Name to search for')
    full_parser.add_argument('--username', help='Username to search for')
    full_parser.add_argument('--peer-id', type=int, help='Specific peer ID')
    full_parser.add_argument('--output', default='./output', help='Output directory')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'list':
            list_all_chats(args.database, args.key_file)
        
        elif args.command == 'extract':
            if not any([args.name, args.username, args.peer_id]):
                print("Error: Must specify --name, --username, or --peer-id")
                sys.exit(1)
            
            extract_chat_messages(
                database=args.database,
                key_file=args.key_file,
                name=args.name,
                username=args.username,
                peer_id=args.peer_id,
                output_dir=args.output,
                extract_media=args.with_media
            )
        
        elif args.command == 'full':
            backup_path = Path(args.backup)
            db_path = backup_path / 'db' / 'db_sqlite'
            
            if not db_path.exists():
                # Try finding it
                candidates = list(backup_path.rglob('db_sqlite'))
                if candidates:
                    db_path = candidates[0]
                else:
                    print(f"Error: Could not find db_sqlite in {backup_path}")
                    sys.exit(1)
            
            print("Starting full recovery pipeline...")
            print(f"Database: {db_path}")
            print()
            
            extract_chat_messages(
                database=str(db_path),
                key_file=None,
                name=args.name,
                username=args.username,
                peer_id=args.peer_id,
                output_dir=args.output,
                extract_media=True
            )
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
