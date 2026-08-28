import base64
from typing import Dict, Any
from cryptography.fernet import Fernet
from app.core.config import settings

def get_fernet() -> Fernet:
    key = getattr(settings, "ENCRYPTION_KEY", None) or getattr(settings, "TOKEN_ENCRYPTION_KEY", None)
    if not key:
        # Fallback default 32-byte urlsafe base64 key for local/testing
        key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    try:
        # Check if the key is valid url-safe base64 and 32 bytes after decoding
        decoded = base64.urlsafe_b64decode(key.encode("utf-8"))
        if len(decoded) != 32:
            # Hash or pad to 32 bytes if not exact
            padded = base64.urlsafe_b64encode(key.encode("utf-8").ljust(32, b"0")[:32])
            return Fernet(padded)
        return Fernet(key.encode("utf-8"))
    except Exception:
        padded = base64.urlsafe_b64encode(key.encode("utf-8").ljust(32, b"0")[:32])
        return Fernet(padded)

def encrypt_data(plain_text: str) -> str:
    """Encrypts plain text into a secure token."""
    if not plain_text:
        return ""
    fernet = get_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_data(cipher_text: str) -> str:
    """Decrypts a secure token back to plain text."""
    if not cipher_text:
        return ""
    try:
        fernet = get_fernet()
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        # Return as-is if decryption fails
        return cipher_text

def encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not config:
        return {}
    encrypted = {}
    for k, v in config.items():
        if any(sec in k.lower() for sec in ["secret", "key", "token", "password"]):
            if v and not str(v).startswith("••••"):
                encrypted[k] = encrypt_data(str(v))
            else:
                encrypted[k] = v
        else:
            encrypted[k] = v
    return encrypted

def decrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not config:
        return {}
    decrypted = {}
    for k, v in config.items():
        if any(sec in k.lower() for sec in ["secret", "key", "token", "password"]):
            if v:
                decrypted[k] = decrypt_data(str(v))
            else:
                decrypted[k] = ""
        else:
            decrypted[k] = v
    return decrypted
