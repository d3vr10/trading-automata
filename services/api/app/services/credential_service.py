"""Broker credential encryption/decryption using Fernet symmetric encryption."""

from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.fernet_key.encode())


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a broker credential for database storage."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a broker credential from database storage."""
    return _fernet.decrypt(ciphertext.encode()).decode()
