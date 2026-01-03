# Telegram Chat Recovery Tool

Recover deleted Telegram chats from your local macOS database backup.

This tool can extract **all messages, media files, and metadata** from Telegram chats that have been deleted from the server but still exist in your local cache.

## ⚠️ Important Notes

- **Only works on macOS** with Telegram App Store version
- **Must have a backup** of the database before it syncs with the server
- **Requires local cache** - deleted messages must have been cached locally
- **All media files must exist** in the local backup to be recovered

## What This Tool Recovers

✅ All text messages with timestamps  
✅ Photos, videos, and media files  
✅ Voice messages and audio files  
✅ Forwarded messages with attribution  
✅ Links, mentions, and formatting  
✅ Complete message metadata  
✅ Author information  

## Prerequisites

### Software Requirements

```bash
# macOS with Homebrew
brew install sqlcipher python3

# Python dependencies
pip3 install pycryptodomex mmh3
```

### Before You Start

**CRITICAL:** You must backup your Telegram database **before** opening Telegram online:

1. **Close Telegram completely**
2. **Turn on Airplane Mode** (or disable network)
3. **Create backup** (see instructions below)
4. Only then proceed with recovery

## Quick Start

### 1. Create a Backup

```bash
# Close Telegram and turn on Airplane Mode first!

# Backup the entire Telegram data directory
cp -R ~/Library/Group\ Containers/6N38VWS5BX.ru.keepcoder.Telegram/appstore ~/telegram_backup_$(date +%Y%m%d)/
```

### 2. List All Chats

```bash
python3 recover.py list --database ~/telegram_backup_*/postbox/db/db_sqlite
```

This will show all chats with names and usernames.

### 3. Extract a Specific Chat

```bash
# By name
python3 recover.py extract \
  --database ~/telegram_backup_*/postbox/db/db_sqlite \
  --name "John Doe" \
  --with-media

# By username
python3 recover.py extract \
  --database ~/telegram_backup_*/postbox/db/db_sqlite \
  --username "johndoe" \
  --with-media

# By peer ID
python3 recover.py extract \
  --database ~/telegram_backup_*/postbox/db/db_sqlite \
  --peer-id 123456789 \
  --with-media
```

### 4. Full Recovery Pipeline

```bash
python3 recover.py full \
  --backup ~/telegram_backup_20260103 \
  --name "John Doe"
```

## Output

The tool creates an `output/` directory with:

```
output/
├── messages_complete.json          # All messages with complete data (36 MB typical)
├── messages_readable.txt           # Human-readable text format
├── media_index.json                # Maps messages to media files
├── media/                          # Extracted media files
│   ├── photos/                     # Photos organized by date
│   ├── videos/                     # Videos organized by date
│   ├── voice/                      # Voice messages
│   └── files/                      # Documents and other files
└── manifest.json                   # Recovery metadata
```

### Message Format

```json
{
  "id": 84079,
  "timestamp": 1755379671,
  "datetime": "2025-08-16T22:27:51",
  "date": "2025-08-16",
  "direction": "received",
  "author": {
    "firstName": "John",
    "lastName": "Doe",
    "username": "johndoe"
  },
  "text": "Message content here",
  "flags": ["Incoming"],
  "tags": ["Photo", "Video"],
  "embeddedMedia": [...],
  "attributes": [...]
}
```

## How It Works

1. **Decrypts the database** using the `.tempkeyEncrypted` file with default password `"no-matter-key"`
2. **Parses SQLCipher database** to extract encrypted data
3. **Decodes Telegram's Postbox format** to read message structures
4. **Extracts all message data** including text, media references, and metadata
5. **Maps media files** from the backup directory to messages
6. **Organizes output** into JSON and human-readable formats

## Technical Details

### Database Encryption

Telegram uses SQLCipher (AES-256) to encrypt the local database. The encryption key is stored in `.tempkeyEncrypted`, which is itself encrypted with a default password.

**Decryption process:**
1. SHA512 hash of `"no-matter-key"` → AES key + IV
2. AES-CBC decryption of `.tempkeyEncrypted` → database key + salt
3. SQLCipher decryption with key + salt → plaintext database

### Database Structure

- **t2**: Peer information (contacts, channels, groups)
- **t6**: Referenced media files
- **t7**: Messages in Postbox binary format
- **t0**: Metadata

### Message Format

Messages are stored in Telegram's proprietary "Postbox" format:
- Binary packed structure
- Type hashes using MurmurHash3
- Nested objects with Int32, Int64, String, Bytes types
- Flags for message state (Incoming, Sent, Failed, etc.)
- Tags for content type (Photo, Video, File, etc.)

## Advanced Usage

### Script Modules

You can use individual scripts programmatically:

```python
from scripts.decrypt_database import decrypt_database
from scripts.extract_messages import extract_chat_messages
from scripts.list_chats import list_all_chats

# Decrypt database
plaintext_db = decrypt_database('path/to/db_sqlite', 'path/to/.tempkeyEncrypted')

# List chats
chats = list_all_chats(plaintext_db)

# Extract specific chat
messages = extract_chat_messages(
    database=plaintext_db,
    peer_id=123456789,
    output_dir='./output'
)
```

### Custom Filters

```python
# Filter messages by date
messages = [m for m in all_messages if m['date'] >= '2024-01-01']

# Get only photos
photos = [m for m in all_messages if 'Photo' in m.get('tags', [])]

# Search for text
results = [m for m in all_messages if 'search term' in m['text'].lower()]
```

## Troubleshooting

### "File is not a database" error

**Solution:** The database is encrypted. Make sure you have the `.tempkeyEncrypted` file in the same directory.

### "No relevant keys found"

**Solution:** This is expected. The tool will decrypt the `.tempkeyEncrypted` file automatically.

### "Media files not found"

**Cause:** Media files were never downloaded to local cache or were cleared.

**Solution:** Only media that exists in the backup can be recovered. Check `~/telegram_backup_*/postbox/media/` for available files.

### Script crashes or hangs

**Solution:** The database might be corrupted or the backup incomplete. Try:
1. Creating a fresh backup
2. Checking that Telegram was closed during backup
3. Ensuring the backup directory is complete

## Security Implications

### Vulnerabilities

- **Default password**: Telegram uses a hardcoded password for temp key encryption
- **Local persistence**: Deleted chats remain in local cache
- **Physical access**: Anyone with access to your Mac can decrypt the database

### Protection

- **Enable FileVault**: Encrypts your entire disk
- **Use strong Mac password**: Protects the Data Protection keychain
- **Clear cache regularly**: Removes old data from local storage
- **Re-enable SIP**: After any debugging, run `csrutil enable` in Recovery Mode

## Limitations

- **macOS only**: Different encryption on Windows/Linux
- **App Store version only**: Direct download version uses different authentication
- **Local cache required**: Can't recover data that was never cached
- **No deleted media**: If media was never downloaded, it can't be recovered

## Credits

Based on research by:
- **stek29** - Original decryption script ([GitHub Gist](https://gist.github.com/stek29/8a7ac0e673818917525ec4031d77a713))
- SQLCipher documentation
- Telegram's open-source client code

## License

MIT License - See LICENSE file for details

## Disclaimer

This tool is for **personal data recovery only**. Only use it on your own Telegram account with data you have legal rights to access.

The authors are not responsible for:
- Any misuse of this tool
- Data loss or corruption
- Legal issues arising from improper use
- Any damage to your system

**Use at your own risk.**

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the blog post for detailed walkthrough
3. Open an issue on GitHub

---

**Last updated:** January 2026
