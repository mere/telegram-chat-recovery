# Documentation

## Architecture

The toolkit consists of several modular components:

1. **Key Extraction** (`decrypt_db.py`)
   - Decrypts `.tempkeyEncrypted` using hardcoded password
   - Uses SHA512 for key derivation
   - Validates with MurmurHash3

2. **Database Decryption** (`decrypt_database.py`)
   - Uses SQLCipher to decrypt the main database
   - Exports to plaintext SQLite format

3. **Chat Listing** (`list_chats.py`)
   - Parses peer table (t2)
   - Decodes Postbox format to extract names/usernames
   - Provides searchable chat list

4. **Message Extraction** (`extract_messages.py`)
   - Parses message table (t7)
   - Decodes complete message structure
   - Extracts text, media, attributes, forwarding info
   - Exports to JSON

5. **Media Indexing** (`create_media_index.py`)
   - Maps message IDs to media file paths
   - Identifies file types and sizes
   - Creates searchable media index

## Postbox Format

Telegram uses a custom binary format called "Postbox" for storing structured data.

### Key Components

- **Type Hashes**: MurmurHash3 of type names
- **Value Types**: Int32, Int64, String, Object, Array, etc.
- **Nested Objects**: Recursive structure with length prefixes

### Message Structure

Messages contain:
- Stable ID and version
- Flags (Incoming, Sent, etc.)
- Tags (Photo, Video, etc.)
- Text content
- Embedded media (with resource IDs)
- Attributes (links, mentions, formatting)
- Forwarding information
- Author metadata

## Database Schema

### Table t2: Peers
Key-value store where:
- Key: Peer ID (string)
- Value: Postbox-encoded peer data
  - `fn`: First name
  - `ln`: Last name
  - `un`: Username
  - `ph`: Phone number

### Table t7: Messages
Key-value store where:
- Key: Message index (binary)
  - Peer ID (8 bytes)
  - Namespace (4 bytes)
  - Timestamp (4 bytes)
  - Message ID (4 bytes)
- Value: Postbox-encoded message data

## Security Notes

### What's Protected
- Database encrypted with SQLCipher (AES-256)
- Memory protection prevents key extraction
- Deleted messages removed from servers

### What's Not Protected
- Local cache persists after server deletion
- Default password used for key encryption
- Anyone with physical access can decrypt

### Recommendations
- Enable disk encryption (FileVault)
- Use strong device passwords
- Regularly clear Telegram cache
- Be aware of local data persistence
