"""
Unit Tests for EncryptionService

Tests the generic encryption service in isolation (no database dependencies).
"""

import pytest
from services.encryption import EncryptionService


class TestAESEncryption:
    """Test AES-256-GCM encryption/decryption"""

    def test_encrypt_decrypt_round_trip(self):
        """Test that encryption and decryption produce original plaintext"""
        plaintext = "123 Main Street, City, ZIP 12345"
        salt_component = "order_123"
        secret = "test_secret_min_32_chars_required_for_security!"

        # Encrypt
        ciphertext, nonce, tag = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component=salt_component,
            secret=secret
        )

        # Verify encrypted data is different from plaintext
        assert ciphertext != plaintext.encode()
        assert len(nonce) == 12  # GCM standard nonce size
        assert len(tag) == 16  # GCM authentication tag size

        # Decrypt
        decrypted = EncryptionService.decrypt_aes_gcm(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            salt_component=salt_component,
            secret=secret
        )

        # Verify round-trip
        assert decrypted == plaintext

    def test_different_salt_produces_different_ciphertext(self):
        """Test that different salt components produce different ciphertexts"""
        plaintext = "Same address"
        secret = "test_secret_min_32_chars_required_for_security!"

        ciphertext1, nonce1, tag1 = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component="order_1",
            secret=secret
        )

        ciphertext2, nonce2, tag2 = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component="order_2",
            secret=secret
        )

        # Different salt should produce different ciphertext
        assert ciphertext1 != ciphertext2

    def test_same_salt_is_deterministic_key_derivation(self):
        """Test that same salt produces same key (but different ciphertext due to random nonce)"""
        plaintext = "Test address"
        salt = "order_123"
        secret = "test_secret_min_32_chars_required_for_security!"

        # Derive key twice with same salt
        key1 = EncryptionService._derive_aes_key(salt, secret)
        key2 = EncryptionService._derive_aes_key(salt, secret)

        # Keys should be identical (deterministic derivation)
        assert key1 == key2
        assert len(key1) == 32  # 256-bit key

    def test_decrypt_with_wrong_salt_fails(self):
        """Test that decryption with wrong salt fails"""
        plaintext = "Secret address"
        secret = "test_secret_min_32_chars_required_for_security!"

        ciphertext, nonce, tag = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component="order_123",
            secret=secret
        )

        # Attempt decryption with wrong salt
        with pytest.raises(Exception):  # Decryption failure
            EncryptionService.decrypt_aes_gcm(
                ciphertext=ciphertext,
                nonce=nonce,
                tag=tag,
                salt_component="order_999",  # Wrong salt
                secret=secret
            )

    def test_decrypt_with_tampered_tag_fails(self):
        """Test that decryption with tampered tag fails (authentication)"""
        plaintext = "Important address"
        salt = "order_123"
        secret = "test_secret_min_32_chars_required_for_security!"

        ciphertext, nonce, tag = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component=salt,
            secret=secret
        )

        # Tamper with tag
        tampered_tag = b'\x00' * 16

        # Decryption should fail (authentication error)
        with pytest.raises(Exception):
            EncryptionService.decrypt_aes_gcm(
                ciphertext=ciphertext,
                nonce=nonce,
                tag=tampered_tag,
                salt_component=salt,
                secret=secret
            )

    def test_encrypt_empty_plaintext_raises_error(self):
        """Test that empty plaintext raises ValueError"""
        with pytest.raises(ValueError, match="Plaintext cannot be empty"):
            EncryptionService.encrypt_aes_gcm(
                plaintext="",
                salt_component="order_123",
                secret="test_secret_min_32_chars_required_for_security!"
            )

    def test_encrypt_with_empty_secret_raises_error(self):
        """Test that empty secret raises ValueError"""
        with pytest.raises(ValueError, match="Encryption secret cannot be empty"):
            EncryptionService.encrypt_aes_gcm(
                plaintext="Test address",
                salt_component="order_123",
                secret=""
            )

    def test_unicode_characters(self):
        """Test encryption of unicode characters (German umlauts, emojis)"""
        plaintext = "Hauptstraße 123, München 80331 🏠"
        salt = "order_456"
        secret = "test_secret_min_32_chars_required_for_security!"

        ciphertext, nonce, tag = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component=salt,
            secret=secret
        )

        decrypted = EncryptionService.decrypt_aes_gcm(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            salt_component=salt,
            secret=secret
        )

        assert decrypted == plaintext


class TestPGPEncoding:
    """Test PGP message encoding/decoding (storage only, no actual PGP crypto)"""

    def test_encode_decode_round_trip(self):
        """Test that PGP message encoding and decoding produce original message"""
        pgp_message = """-----BEGIN PGP MESSAGE-----
Version: OpenPGP.js v4.10.10

wcBMA1234567890ABCQH/1234567890abcdefghijklmnop==
=ABCD
-----END PGP MESSAGE-----"""

        # Encode
        encoded = EncryptionService.encode_pgp(pgp_message)

        # Verify encoded is bytes
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0

        # Decode
        decoded = EncryptionService.decode_pgp(encoded)

        # Verify round-trip
        assert decoded == pgp_message

    def test_pgp_unicode_characters(self):
        """Test PGP encoding with unicode PGP message"""
        pgp_message = "-----BEGIN PGP MESSAGE-----\nÜnicode Test 🔐\n-----END PGP MESSAGE-----"

        encoded = EncryptionService.encode_pgp(pgp_message)
        decoded = EncryptionService.decode_pgp(encoded)

        assert decoded == pgp_message


class TestValidationHelpers:
    """Test validation helper methods"""

    def test_validate_encryption_mode_valid(self):
        """Test validation of valid encryption modes"""
        assert EncryptionService.validate_encryption_mode('aes') is True
        assert EncryptionService.validate_encryption_mode('pgp') is True

    def test_validate_encryption_mode_invalid(self):
        """Test validation of invalid encryption modes"""
        assert EncryptionService.validate_encryption_mode('rsa') is False
        assert EncryptionService.validate_encryption_mode('') is False
        assert EncryptionService.validate_encryption_mode('AES') is False  # Case-sensitive

    def test_is_pgp_available(self, monkeypatch):
        """Test PGP availability check based on config"""
        import config

        # Test when PGP is available
        monkeypatch.setattr(config, 'PGP_PUBLIC_KEY_BASE64', 'dummy_key_base64')
        assert EncryptionService.is_pgp_available() is True

        # Test when PGP is not available
        monkeypatch.setattr(config, 'PGP_PUBLIC_KEY_BASE64', '')
        assert EncryptionService.is_pgp_available() is False

        monkeypatch.setattr(config, 'PGP_PUBLIC_KEY_BASE64', None)
        assert EncryptionService.is_pgp_available() is False


class TestSecurity:
    """Test security properties of encryption"""

    def test_different_nonces_for_same_plaintext(self):
        """Test that encrypting same plaintext twice produces different nonces (randomness)"""
        plaintext = "Same address"
        salt = "order_123"
        secret = "test_secret_min_32_chars_required_for_security!"

        ciphertext1, nonce1, tag1 = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component=salt,
            secret=secret
        )

        ciphertext2, nonce2, tag2 = EncryptionService.encrypt_aes_gcm(
            plaintext=plaintext,
            salt_component=salt,
            secret=secret
        )

        # Nonces should be different (random generation)
        assert nonce1 != nonce2
        # Ciphertexts should be different (due to different nonces)
        assert ciphertext1 != ciphertext2

    def test_pbkdf2_iterations(self):
        """Test that PBKDF2 uses sufficient iterations (100000+)"""
        # This is a design test - verify code uses OWASP recommendation
        # Check the _derive_aes_key method in EncryptionService
        import inspect
        source = inspect.getsource(EncryptionService._derive_aes_key)
        assert "iterations=100000" in source, "PBKDF2 should use 100000+ iterations"