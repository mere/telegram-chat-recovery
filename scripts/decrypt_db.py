#!/usr/bin/env python3
"""
Decrypt Telegram macOS database using .tempkeyEncrypted file
Based on: https://gist.github.com/stek29/8a7ac0e673818917525ec4031d77a713
"""

import struct
import mmh3
import binascii

try:
    from Cryptodome.Hash import SHA512
    from Cryptodome.Cipher import AES
except ImportError:
    try:
        from Crypto.Hash import SHA512
        from Crypto.Cipher import AES
    except ImportError:
        from Cryptodomex.Hash import SHA512
        from Cryptodomex.Cipher import AES


DEFAULT_PASSWORD = 'no-matter-key'


def murmur(d):
    """Murmur hash used by Telegram"""
    # seed -137723950 is from telegram, hex(-137723950 & 0xffffffff)
    return mmh3.hash(d, seed=0xf7ca7fd2)


def tempkey_kdf(password):
    """Key derivation function for tempkey"""
    h = SHA512.new()
    h.update(password.encode('utf-8'))
    digest = h.digest()
    key, iv = digest[0:32], digest[-16:]
    return key, iv


def tempkey_parse(dataEnc, pwd):
    """Parse and decrypt the tempkeyEncrypted file"""
    aesKey, aesIV = tempkey_kdf(pwd)
    cipher = AES.new(key=aesKey, iv=aesIV, mode=AES.MODE_CBC)
    data = cipher.decrypt(dataEnc)

    dbKey = data[0:32]
    dbSalt = data[32:48]
    dbHash = struct.unpack('<i', data[48:52])[0]
    dbPad = data[52:]
    
    if len(dbPad) != 12 or any(dbPad):
        print('WARN: dbPad not 12 zeros')

    calcHash = murmur(dbKey+dbSalt)
    if dbHash != calcHash:
        raise Exception(f'Hash mismatch: {dbHash} != {calcHash}')

    return dbKey, dbSalt


def tempkey_pragma(dbKey, dbSalt):
    """Generate SQLCipher PRAGMA key statement"""
    key = binascii.hexlify(dbKey+dbSalt).decode('utf-8')
    return f"PRAGMA key=\"x'{key}'\";"


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python decrypt_db.py <path_to_.tempkeyEncrypted>")
        sys.exit(1)
    
    tempkey_file = sys.argv[1]
    
    print(f"Reading {tempkey_file}...")
    with open(tempkey_file, 'rb') as f:
        tempkeyEnc = f.read()
    
    print(f"Decrypting with password '{DEFAULT_PASSWORD}'...")
    dbKey, dbSalt = tempkey_parse(tempkeyEnc, DEFAULT_PASSWORD)
    
    print("\n" + "="*70)
    print("SQLCipher decryption key found!")
    print("="*70)
    print("\nTo decrypt your database, run these commands in sqlcipher:\n")
    print("$ sqlcipher db_sqlite")
    print()
    print("PRAGMA cipher_plaintext_header_size=32;")
    print("PRAGMA cipher_default_plaintext_header_size=32;")
    print(tempkey_pragma(dbKey, dbSalt))
    print()
    print("PRAGMA user_version; -- should return 4")
    print()
    print("-- Export to unencrypted database:")
    print("ATTACH DATABASE 'plaintext.db' AS plaintext KEY '';")
    print("SELECT sqlcipher_export('plaintext');")
    print("DETACH DATABASE plaintext;")
    print()
    print("="*70)


if __name__ == '__main__':
    main()
