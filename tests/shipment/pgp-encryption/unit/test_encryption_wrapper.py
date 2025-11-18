"""
Unit tests for EncryptionWrapper (PGP and AES-GCM encryption).

Tests encryption/decryption functionality for shipping addresses.
"""

import pytest
from services.encryption_wrapper import EncryptionWrapper


class TestAESGCMEncryption:
    """Test AES-256-GCM encryption/decryption."""

    def test_encrypt_aes_gcm_returns_bytes(self):
        """Test that AES-GCM encryption returns bytes."""
        plaintext = "John Doe\n123 Main St\n12345 Berlin"
        order_id = 42

        encrypted = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)

        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0

    def test_encrypt_aes_gcm_format(self):
        """Test that encrypted data has correct format: [ciphertext][nonce 12B][tag 16B]."""
        plaintext = "John Doe\n123 Main St\n12345 Berlin"
        order_id = 42

        encrypted = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)

        # Minimum size: at least 28 bytes (12 nonce + 16 tag)
        assert len(encrypted) >= 28

        # Verify structure by extracting components
        nonce = encrypted[-28:-16]
        tag = encrypted[-16:]
        ciphertext = encrypted[:-28]

        assert len(nonce) == 12
        assert len(tag) == 16
        assert len(ciphertext) > 0

    def test_decrypt_aes_gcm_success(self):
        """Test successful AES-GCM decryption."""
        plaintext = "John Doe\n123 Main St\n12345 Berlin"
        order_id = 42

        # Encrypt
        encrypted = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)

        # Decrypt
        decrypted = EncryptionWrapper.decrypt_aes_gcm(encrypted, order_id)

        assert decrypted == plaintext

    def test_decrypt_aes_gcm_different_order_id_fails(self):
        """Test that decryption with wrong order_id fails."""
        plaintext = "John Doe\n123 Main St\n12345 Berlin"
        order_id = 42
        wrong_order_id = 99

        encrypted = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)

        # Should raise exception due to authentication failure
        with pytest.raises(Exception):
            EncryptionWrapper.decrypt_aes_gcm(encrypted, wrong_order_id)

    def test_encrypt_aes_gcm_deterministic_false(self):
        """Test that encryption is non-deterministic (different nonces)."""
        plaintext = "John Doe\n123 Main St\n12345 Berlin"
        order_id = 42

        encrypted1 = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)
        encrypted2 = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)

        # Different nonces = different ciphertexts
        assert encrypted1 != encrypted2

    def test_encrypt_aes_gcm_unicode(self):
        """Test AES-GCM encryption with unicode characters."""
        plaintext = "Jürgen Müller\nStraße 123\n12345 München"
        order_id = 42

        encrypted = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)
        decrypted = EncryptionWrapper.decrypt_aes_gcm(encrypted, order_id)

        assert decrypted == plaintext

    def test_encrypt_aes_gcm_empty_string(self):
        """Test AES-GCM encryption with empty string."""
        plaintext = ""
        order_id = 42

        encrypted = EncryptionWrapper.encrypt_aes_gcm(plaintext, order_id)
        decrypted = EncryptionWrapper.decrypt_aes_gcm(encrypted, order_id)

        assert decrypted == plaintext


class TestPGPStorage:
    """Test PGP encrypted message storage."""

    def test_store_pgp_encrypted_returns_bytes(self):
        """Test that PGP storage returns bytes."""
        pgp_message = """-----BEGIN PGP MESSAGE-----

hQEMA1234567890ABCAQf/abcdefghijklmnopqrstuvwxyz
-----END PGP MESSAGE-----"""

        stored = EncryptionWrapper.store_pgp_encrypted(pgp_message)

        assert isinstance(stored, bytes)

    def test_store_pgp_encrypted_utf8_encoding(self):
        """Test that PGP storage uses UTF-8 encoding."""
        pgp_message = """-----BEGIN PGP MESSAGE-----

hQEMA1234567890ABCAQf/abcdefghijklmnopqrstuvwxyz
-----END PGP MESSAGE-----"""

        stored = EncryptionWrapper.store_pgp_encrypted(pgp_message)

        # Should be simple UTF-8 encoding
        assert stored == pgp_message.encode('utf-8')

    def test_store_pgp_encrypted_roundtrip(self):
        """Test that PGP message can be stored and retrieved."""
        pgp_message = """-----BEGIN PGP MESSAGE-----

hQEMA1234567890ABCAQf/abcdefghijklmnopqrstuvwxyz
-----END PGP MESSAGE-----"""

        stored = EncryptionWrapper.store_pgp_encrypted(pgp_message)
        retrieved = stored.decode('utf-8')

        assert retrieved == pgp_message
