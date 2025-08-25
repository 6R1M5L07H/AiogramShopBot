import logging
import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
from typing import Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting private keys using AES-256-GCM encryption
    with PBKDF2 key derivation and unique salts per key.
    """
    
    # Use 256-bit AES key
    KEY_LENGTH = 32
    # Salt length for PBKDF2
    SALT_LENGTH = 16
    # Nonce length for AESGCM
    NONCE_LENGTH = 12
    # PBKDF2 iterations for key derivation
    PBKDF2_ITERATIONS = 120000  # Increased for better security
    
    @staticmethod
    def _get_master_key() -> bytes:
        """
        Get the master encryption key from environment variable.
        In production, this should be stored securely (e.g., AWS KMS, HashiCorp Vault)
        """
        master_key_b64 = os.getenv('ENCRYPTION_MASTER_KEY')
        if not master_key_b64:
            raise ValueError("ENCRYPTION_MASTER_KEY environment variable not set")
        
        try:
            return base64.b64decode(master_key_b64)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_MASTER_KEY format: {e}")
    
    @staticmethod
    def _derive_key(master_key: bytes, salt: bytes) -> bytes:
        """
        Derive encryption key from master key using PBKDF2
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=EncryptionService.KEY_LENGTH,
            salt=salt,
            iterations=EncryptionService.PBKDF2_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(master_key)
    
    @staticmethod
    def generate_encryption_key() -> str:
        """
        Generate a new master encryption key for first-time setup.
        This should be called only once and stored securely.
        """
        key = secrets.token_bytes(EncryptionService.KEY_LENGTH)
        return base64.b64encode(key).decode('utf-8')
    
    @staticmethod
    def encrypt_private_key(private_key: str, order_id: int) -> Tuple[str, str]:
        """
        Encrypt a private key using AES-256-GCM with unique salt.
        
        Args:
            private_key: The private key to encrypt
            order_id: Order ID for audit logging
            
        Returns:
            Tuple of (encrypted_private_key_b64, salt_b64)
        """
        try:
            if not private_key:
                raise ValueError("Private key cannot be empty")
            
            # Generate unique salt and nonce
            salt = secrets.token_bytes(EncryptionService.SALT_LENGTH)
            nonce = secrets.token_bytes(EncryptionService.NONCE_LENGTH)
            
            # Get master key and derive encryption key
            master_key = EncryptionService._get_master_key()
            derived_key = EncryptionService._derive_key(master_key, salt)
            
            # Create AESGCM cipher
            aesgcm = AESGCM(derived_key)
            
            # Encrypt the private key
            encrypted_data = aesgcm.encrypt(nonce, private_key.encode('utf-8'), None)
            
            # Combine nonce + encrypted data for storage
            combined_data = nonce + encrypted_data
            
            # Base64 encode for database storage
            encrypted_b64 = base64.b64encode(combined_data).decode('utf-8')
            salt_b64 = base64.b64encode(salt).decode('utf-8')
            
            # Audit log
            logger.info(f"Private key encrypted for order {order_id} at {datetime.utcnow()}")
            
            return encrypted_b64, salt_b64
            
        except Exception as e:
            logger.error(f"Error encrypting private key for order {order_id}: {str(e)}")
            raise
    
    @staticmethod
    def decrypt_private_key(encrypted_private_key_b64: str, salt_b64: str, order_id: int, 
                          admin_id: Optional[int] = None) -> str:
        """
        Decrypt a private key using AES-256-GCM.
        
        Args:
            encrypted_private_key_b64: Base64 encoded encrypted private key
            salt_b64: Base64 encoded salt
            order_id: Order ID for audit logging
            admin_id: Admin ID requesting decryption (for audit)
            
        Returns:
            Decrypted private key
        """
        try:
            if not encrypted_private_key_b64 or not salt_b64:
                raise ValueError("Encrypted private key and salt cannot be empty")
            
            # Decode base64 data
            combined_data = base64.b64decode(encrypted_private_key_b64)
            salt = base64.b64decode(salt_b64)
            
            # Extract nonce and encrypted data
            nonce = combined_data[:EncryptionService.NONCE_LENGTH]
            encrypted_data = combined_data[EncryptionService.NONCE_LENGTH:]
            
            # Get master key and derive decryption key
            master_key = EncryptionService._get_master_key()
            derived_key = EncryptionService._derive_key(master_key, salt)
            
            # Create AESGCM cipher
            aesgcm = AESGCM(derived_key)
            
            # Decrypt the private key
            decrypted_data = aesgcm.decrypt(nonce, encrypted_data, None)
            private_key = decrypted_data.decode('utf-8')
            
            # Audit log
            admin_info = f" by admin {admin_id}" if admin_id else ""
            logger.warning(f"Private key decrypted for order {order_id} at {datetime.utcnow()}{admin_info}")
            
            return private_key
            
        except Exception as e:
            logger.error(f"Error decrypting private key for order {order_id}: {str(e)}")
            raise
    
    @staticmethod
    def rotate_private_key_encryption(old_encrypted_key_b64: str, old_salt_b64: str, 
                                    order_id: int) -> Tuple[str, str]:
        """
        Rotate encryption of a private key (decrypt with old key, encrypt with new salt).
        Used for key rotation or when master key is changed.
        
        Args:
            old_encrypted_key_b64: Current encrypted private key
            old_salt_b64: Current salt
            order_id: Order ID for audit logging
            
        Returns:
            Tuple of (new_encrypted_private_key_b64, new_salt_b64)
        """
        try:
            # Decrypt with old parameters
            private_key = EncryptionService.decrypt_private_key(
                old_encrypted_key_b64, old_salt_b64, order_id
            )
            
            # Re-encrypt with new salt
            new_encrypted_key_b64, new_salt_b64 = EncryptionService.encrypt_private_key(
                private_key, order_id
            )
            
            logger.info(f"Private key encryption rotated for order {order_id} at {datetime.utcnow()}")
            
            return new_encrypted_key_b64, new_salt_b64
            
        except Exception as e:
            logger.error(f"Error rotating private key encryption for order {order_id}: {str(e)}")
            raise
    
    @staticmethod
    def verify_encryption_setup() -> bool:
        """
        Verify that encryption is properly configured by testing encrypt/decrypt cycle.
        """
        try:
            test_data = "test_private_key_12345"
            encrypted, salt = EncryptionService.encrypt_private_key(test_data, 0)
            decrypted = EncryptionService.decrypt_private_key(encrypted, salt, 0)
            
            return decrypted == test_data
            
        except Exception as e:
            logger.error(f"Encryption setup verification failed: {str(e)}")
            return False