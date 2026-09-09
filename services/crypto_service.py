import os
import base64
import hashlib
import secrets
from typing import Tuple, Optional
from loguru import logger
from cryptography.fernet import Fernet, InvalidToken

class CryptoService:
    """
    Enterprise Data Security & Encryption Service:
    - Salted PBKDF2-HMAC-SHA256 password hashing with legacy SHA256 migration support.
    - AES-256 (Fernet) field-level PII encryption and decryption.
    """
    def __init__(self, iterations: int = 100_000, secret_key: Optional[str] = None) -> None:
        self.iterations = iterations
        raw_key = secret_key or os.environ.get("SECRET_KEY", "edubot_super_secret_pii_encryption_key_32bytes!")
        # Derive 32-byte key for Fernet AES-256
        key_bytes = hashlib.sha256(raw_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self.cipher = Fernet(fernet_key)

    def hash_password(self, password: str) -> str:
        """
        Hashes password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a random 16-byte salt.
        Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
        """
        salt = secrets.token_hex(16)
        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            self.iterations
        )
        return f"pbkdf2_sha256${self.iterations}${salt}${hash_bytes.hex()}"

    def verify_password(self, password: str, stored_hash: str) -> Tuple[bool, bool]:
        """
        Verifies a raw password against stored hash.
        Returns: (is_valid: bool, needs_upgrade: bool)
        """
        if not stored_hash:
            return False, False

        # 1. Check if PBKDF2 format
        if stored_hash.startswith("pbkdf2_sha256$"):
            try:
                parts = stored_hash.split("$")
                if len(parts) != 4:
                    return False, False
                _, iterations_str, salt, hash_hex = parts
                iterations = int(iterations_str)

                computed_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt.encode("utf-8"),
                    iterations
                ).hex()

                is_valid = secrets.compare_digest(computed_hash, hash_hex)
                needs_upgrade = iterations < self.iterations
                return is_valid, needs_upgrade
            except Exception as e:
                logger.error(f"Error verifying PBKDF2 password: {e}")
                return False, False

        # 2. Legacy SHA256 Fallback Check
        legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if secrets.compare_digest(legacy_hash, stored_hash):
            logger.info("Verified legacy SHA256 password. Upgrading to salted PBKDF2.")
            return True, True  # Valid password, needs upgrade to PBKDF2!

        return False, False

    def encrypt_pii(self, plain_text: Optional[str]) -> Optional[str]:
        """Encrypts sensitive PII string using AES-256 Fernet cipher."""
        if not plain_text:
            return plain_text
        try:
            encrypted_bytes = self.cipher.encrypt(plain_text.encode("utf-8"))
            return f"enc${encrypted_bytes.decode('utf-8')}"
        except Exception as e:
            logger.error(f"Failed to encrypt PII field: {e}")
            return plain_text

    def decrypt_pii(self, encrypted_text: Optional[str]) -> Optional[str]:
        """Decrypts AES-256 Fernet encrypted PII string."""
        if not encrypted_text or not isinstance(encrypted_text, str):
            return encrypted_text
        if not encrypted_text.startswith("enc$"):
            return encrypted_text  # Unencrypted legacy data
        try:
            raw_cipher = encrypted_text[4:]
            decrypted_bytes = self.cipher.decrypt(raw_cipher.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            logger.warning("Failed to decrypt PII: Invalid encryption key or corrupted payload.")
            return encrypted_text
        except Exception as e:
            logger.error(f"Error decrypting PII field: {e}")
            return encrypted_text

crypto_service = CryptoService()
