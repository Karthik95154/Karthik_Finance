import base64
from typing import Dict, Any
from cryptography.fernet import Fernet
from app.core.config import settings

def get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable is missing.")
    try:
        # Check if the key is valid url-safe base64 and 32 bytes after decoding
        decoded = base64.urlsafe_b64decode(key.encode("utf-8"))
        if len(decoded) != 32:
            raise ValueError("ENCRYPTION_KEY must be a 32-byte key url-safe base64 encoded.")
        return Fernet(key.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY configuration: {str(e)}")

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
