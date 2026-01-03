#!/usr/bin/env python3
"""
Decrypt Telegram database using SQLCipher with extracted key
"""
import os
import sys
import subprocess
import shutil

def decrypt_database(encrypted_db_path, key_hex, output_path='plaintext.db'):
    """
    Decrypt Telegram database using SQLCipher
    
    Args:
        encrypted_db_path: Path to encrypted db_sqlite file
        key_hex: Hexadecimal key string (without x'' wrapper)
        output_path: Path for decrypted database output
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Check if sqlcipher is installed
    if not shutil.which('sqlcipher'):
        print("Error: sqlcipher is not installed")
        print("Install with: brew install sqlcipher (macOS) or apt-get install sqlcipher3 (Linux)")
        return False
    
    # Check if encrypted database exists
    if not os.path.exists(encrypted_db_path):
        print(f"Error: Encrypted database not found at {encrypted_db_path}")
        return False
    
    # Ensure key is in correct format
    if key_hex.startswith("x'") and key_hex.endswith("'"):
        key_hex = key_hex[2:-1]
    
    # Create SQL commands to decrypt
    sql_commands = f"""
PRAGMA key="x'{key_hex}'";
ATTACH DATABASE '{output_path}' AS plaintext KEY '';
SELECT sqlcipher_export('plaintext');
DETACH DATABASE plaintext;
"""
    
    try:
        # Run sqlcipher to decrypt
        print(f"Decrypting {encrypted_db_path}...")
        process = subprocess.Popen(
            ['sqlcipher', encrypted_db_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=sql_commands)
        
        if process.returncode != 0:
            print(f"Error during decryption: {stderr}")
            return False
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Decryption successful!")
            print(f"  Output: {output_path}")
            print(f"  Size: {file_size / 1024 / 1024:.2f} MB")
            return True
        else:
            print("Error: Decrypted database was not created")
            return False
            
    except Exception as e:
        print(f"Error during decryption: {e}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python decrypt_database.py <encrypted_db_path> <key_hex> [output_path]")
        print("\nExample:")
        print("  python decrypt_database.py db_sqlite a97995e4eb1f... plaintext.db")
        sys.exit(1)
    
    encrypted_db_path = sys.argv[1]
    key_hex = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else 'plaintext.db'
    
    success = decrypt_database(encrypted_db_path, key_hex, output_path)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
