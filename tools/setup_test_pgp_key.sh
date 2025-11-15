#!/bin/bash
# Setup Test PGP Key for Development
# This script generates a test PGP keypair and adds it to .env

set -e

echo "=================================="
echo "PGP Test Key Setup for Development"
echo "=================================="
echo ""

# Check if gpg is installed
if ! command -v gpg &> /dev/null; then
    echo "❌ Error: gpg not found. Please install GnuPG first:"
    echo ""
    echo "  macOS:   brew install gnupg"
    echo "  Ubuntu:  sudo apt install gnupg"
    echo "  Arch:    sudo pacman -S gnupg"
    echo ""
    exit 1
fi

# Configuration
KEY_NAME="Test Bot Admin"
KEY_EMAIL="admin@testbot.local"
KEY_COMMENT="Test Key - DO NOT USE IN PRODUCTION"
KEY_EXPIRES="0"  # Never expires

# Generate key parameters file
echo "📝 Generating key parameters..."
cat > /tmp/pgp_key_params <<EOF
Key-Type: RSA
Key-Length: 2048
Subkey-Type: RSA
Subkey-Length: 2048
Name-Real: ${KEY_NAME}
Name-Comment: ${KEY_COMMENT}
Name-Email: ${KEY_EMAIL}
Expire-Date: ${KEY_EXPIRES}
%no-protection
%commit
EOF

# Generate key
echo "🔑 Generating PGP keypair (this may take a moment)..."
gpg --batch --generate-key /tmp/pgp_key_params 2>/dev/null

# Clean up params file
rm /tmp/pgp_key_params

# Get key ID
KEY_ID=$(gpg --list-keys --with-colons "${KEY_EMAIL}" 2>/dev/null | grep '^pub' | cut -d':' -f5)

if [ -z "$KEY_ID" ]; then
    echo "❌ Error: Failed to generate key"
    exit 1
fi

echo "✅ Key generated successfully!"
echo "   Key ID: ${KEY_ID}"
echo ""

# Export public key
echo "📤 Exporting public key..."
PUBLIC_KEY=$(gpg --armor --export "${KEY_EMAIL}" 2>/dev/null)

if [ -z "$PUBLIC_KEY" ]; then
    echo "❌ Error: Failed to export public key"
    exit 1
fi

# Base64 encode the public key
PUBLIC_KEY_BASE64=$(echo "$PUBLIC_KEY" | base64)

# Show public key
echo "✅ Public key exported!"
echo ""
echo "=================================="
echo "Public Key (ASCII-armored):"
echo "=================================="
echo "$PUBLIC_KEY"
echo ""

# Update .env file
ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  Warning: .env file not found. Please create it manually."
    echo ""
    echo "Add this line to your .env file:"
    echo ""
    echo "PGP_PUBLIC_KEY_BASE64=\"${PUBLIC_KEY_BASE64}\""
    echo ""
else
    # Check if key already exists in .env
    if grep -q "^PGP_PUBLIC_KEY_BASE64=" "$ENV_FILE"; then
        # Update existing key
        sed -i.bak "s|^PGP_PUBLIC_KEY_BASE64=.*|PGP_PUBLIC_KEY_BASE64=\"${PUBLIC_KEY_BASE64}\"|" "$ENV_FILE"
        echo "✅ Updated PGP_PUBLIC_KEY_BASE64 in $ENV_FILE"
        echo "   (Backup saved as ${ENV_FILE}.bak)"
    else
        # Add new key
        echo "" >> "$ENV_FILE"
        echo "# PGP Shipping Address Encryption" >> "$ENV_FILE"
        echo "PGP_PUBLIC_KEY_BASE64=\"${PUBLIC_KEY_BASE64}\"" >> "$ENV_FILE"
        echo "✅ Added PGP_PUBLIC_KEY_BASE64 to $ENV_FILE"
    fi
    echo ""
fi

# Export private key for testing/decryption
PRIVATE_KEY_FILE="tools/test_pgp_private_key.asc"
echo "🔐 Exporting private key for testing..."
gpg --armor --export-secret-keys "${KEY_EMAIL}" > "$PRIVATE_KEY_FILE" 2>/dev/null

echo "✅ Private key saved to: $PRIVATE_KEY_FILE"
echo "   ⚠️  Keep this file secret! DO NOT commit to git!"
echo ""

# Add to .gitignore
if [ -f ".gitignore" ]; then
    if ! grep -q "test_pgp_private_key.asc" ".gitignore"; then
        echo "tools/test_pgp_private_key.asc" >> .gitignore
        echo "✅ Added test_pgp_private_key.asc to .gitignore"
    fi
fi

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Restart your bot to load the new PGP key"
echo "2. Test encryption via Mini App"
echo "3. Use tools/test_decrypt_address.py to decrypt addresses"
echo ""
echo "⚠️  IMPORTANT: This is a TEST key. In production:"
echo "   - Use a secure key generated on an offline machine"
echo "   - Store private key in a secure location (not in repo)"
echo "   - Use proper key management practices"
echo ""
