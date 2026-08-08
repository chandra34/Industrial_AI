"""
Symmetric encryption utilities for securely storing connector credentials.
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the CONNECTOR_SECRET environment variable."""
    secret = os.getenv("CONNECTOR_SECRET", "default-change-me-in-production")
    # Derive a 32-byte key from the secret string using SHA-256, then base64 encode for Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext password string. Returns a Fernet token string."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_password(token: str) -> str:
    """Decrypt a Fernet token string back to plaintext."""
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode()).decode()
