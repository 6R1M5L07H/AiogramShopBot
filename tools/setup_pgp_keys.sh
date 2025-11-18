#!/bin/bash
#
# Setup script for generating PGP keypair for shipping address encryption.
#
# This script generates:
# - PGP public key (for client-side encryption in Telegram Mini App)
# - PGP private key (for admin-side decryption)
#
# Usage:
#   bash tools/setup_pgp_keys.sh
#
# Output:
#   - pgp_public.asc (public key - goes to .env as PGP_PUBLIC_KEY_BASE64)
#   - pgp_private.asc (private key - KEEP SECURE, use for decryption)
#

set -e

echo "========================================"
echo "PGP Keypair Generation for Shipping Encryption"
echo "========================================"
echo

# Check if gpg is installed
if ! command -v gpg &> /dev/null; then
    echo "ERROR: gpg not found. Please install GnuPG:"
    echo "  - macOS: brew install gnupg"
    echo "  - Ubuntu/Debian: sudo apt-get install gnupg"
    echo "  - Fedora: sudo dnf install gnupg"
    exit 1
fi

# Prompt for name and email
read -p "Enter name for key (e.g., 'Shop Bot Admin'): " KEY_NAME
read -p "Enter email for key (e.g., 'admin@example.com'): " KEY_EMAIL

# Prompt for passphrase
echo
echo "Enter passphrase for private key (leave empty for no passphrase):"
read -s PASSPHRASE
echo

# Generate key with batch mode
echo "Generating 4096-bit RSA keypair..."

gpg --batch --gen-key <<EOF
%no-protection
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: $KEY_NAME
Name-Email: $KEY_EMAIL
Expire-Date: 0
%commit
EOF

# Export public key
KEY_ID=$(gpg --list-keys --with-colons "$KEY_EMAIL" | awk -F: '/^pub:/ {print $5}')
gpg --armor --export "$KEY_ID" > pgp_public.asc

# Export private key
if [ -n "$PASSPHRASE" ]; then
    echo "$PASSPHRASE" | gpg --batch --yes --pinentry-mode loopback --passphrase-fd 0 \
        --armor --export-secret-keys "$KEY_ID" > pgp_private.asc
else
    gpg --batch --yes --armor --export-secret-keys "$KEY_ID" > pgp_private.asc
fi

# Encode public key to base64 (single line)
PUBLIC_KEY_BASE64=$(cat pgp_public.asc | base64 | tr -d '\n')
PRIVATE_KEY_BASE64=$(cat pgp_private.asc | base64 | tr -d '\n')

echo
echo "========================================"
echo "SUCCESS! PGP Keypair Generated"
echo "========================================"
echo
echo "Key ID: $KEY_ID"
echo "Files created:"
echo "  - pgp_public.asc (public key)"
echo "  - pgp_private.asc (private key - KEEP SECURE!)"
echo
echo "========================================"
echo "Configuration for .env"
echo "========================================"
echo
echo "Add this to your .env file:"
echo
echo "# PGP Encryption for Shipping Addresses"
echo "PGP_PUBLIC_KEY_BASE64=\"$PUBLIC_KEY_BASE64\""
echo "BOT_DOMAIN=\"your-domain.com\"  # Replace with your actual domain"
echo
echo "========================================"
echo "Admin Decryption Configuration"
echo "========================================"
echo
echo "For admin decryption tool, use ONE of these options:"
echo
echo "Option 1: Environment variable (base64)"
echo "export PGP_PRIVATE_KEY_BASE64=\"$PRIVATE_KEY_BASE64\""
if [ -n "$PASSPHRASE" ]; then
    echo "export PGP_PRIVATE_KEY_PASSPHRASE=\"$PASSPHRASE\""
fi
echo
echo "Option 2: File path"
echo "export PGP_PRIVATE_KEY_PATH=\"$(pwd)/pgp_private.asc\""
if [ -n "$PASSPHRASE" ]; then
    echo "export PGP_PRIVATE_KEY_PASSPHRASE=\"$PASSPHRASE\""
fi
echo
echo "========================================"
echo "SECURITY WARNING"
echo "========================================"
echo
echo "1. NEVER commit pgp_private.asc to git!"
echo "2. Store private key in secure location (password manager, vault)"
echo "3. Only authorized admins should have access to private key"
echo "4. Consider using a hardware security key for production"
echo
echo "Add to .gitignore:"
echo "  pgp_private.asc"
echo "  pgp_public.asc"
echo