#!/bin/bash
# Quick PGP address decryption tool
# Usage: ./decrypt_address.sh /path/to/private_key.asc "-----BEGIN PGP MESSAGE-----..."

set -e

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <private_key_path> <encrypted_message>"
    echo ""
    echo "Example:"
    echo "  $0 private_key.asc \"\$(cat encrypted.txt)\""
    exit 1
fi

PRIVATE_KEY="$1"
ENCRYPTED_MSG="$2"

if [ ! -f "$PRIVATE_KEY" ]; then
    echo "Error: Private key file not found: $PRIVATE_KEY"
    exit 1
fi

# Check if gpg is installed
if ! command -v gpg &> /dev/null; then
    echo "Error: gpg (GnuPG) is not installed"
    echo "Install with: brew install gnupg (macOS) or apt-get install gnupg (Linux)"
    exit 1
fi

echo "🔓 Decrypting PGP message..."
echo ""

# Decrypt the message
echo "$ENCRYPTED_MSG" | gpg --decrypt --quiet --batch --passphrase "" --pinentry-mode loopback 2>/dev/null

echo ""
echo "✅ Decryption complete"
