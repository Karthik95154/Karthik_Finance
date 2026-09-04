import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet, InvalidToken
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# HTTPBearer security scheme
security_bearer = HTTPBearer(auto_error=False)


# ============================================================================
# Authenticated User Model
# ============================================================================

class AuthenticatedUser(BaseModel):
    id: str
    email: str
    tenant_id: str
    role: str  # "ADMIN", "FINANCE", "FINANCE_REVIEWER", "DATA_REVIEWER", "VIEWER", "CUSTOMER"
    full_name: Optional[str] = None


# ============================================================================
# JWT Token Functions (PyJWT with explicit algorithm enforcement)
# ============================================================================

def create_access_token(
    user_id: str,
    email: str,
    tenant_id: str,
    role: str = "FINANCE",
    full_name: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Encodes and signs a JWT token with explicit claims and algorithm (HS256).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "email": email.strip().lower(),
        "tenant_id": tenant_id.strip(),
        "role": role.strip().upper(),
        "full_name": full_name,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.AUTH_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Cryptographically verifies and decodes a JWT token.
    Enforces signature, expiration, and expected algorithm strictly.
    """
    try:
        payload = jwt.decode(
            token,
            settings.AUTH_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidAlgorithmError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token algorithm.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(err)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


DEV_ACTIVE_ROLE = "ADMIN"


def set_dev_role(new_role: str) -> None:
    global DEV_ACTIVE_ROLE
    DEV_ACTIVE_ROLE = new_role.upper()


# ============================================================================
# FastAPI Authentication & RBAC Dependencies
# ============================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency that extracts and validates the Bearer JWT token from the
    Authorization header. Returns verified AuthenticatedUser.
    In development mode with ENABLE_DEV_AUTH=True, falls back to default dev user.
    """
    if not credentials or not credentials.credentials:
        if settings.ENABLE_DEV_AUTH:
            return AuthenticatedUser(
                id="dev-user-001",
                email="finance@sakshi.ai",
                tenant_id=settings.DEFAULT_TENANT_ID,
                role=DEV_ACTIVE_ROLE,
                full_name="Dev Admin",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Bearer token in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    sub = payload.get("sub") or payload.get("user_id")
    email = payload.get("email")
    tenant_id = payload.get("tenant_id")
    role = (payload.get("role") or "VIEWER").upper()

    if not sub or not email or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: missing mandatory identity claims (sub, email, tenant_id).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if role not in ("ADMIN", "FINANCE", "FINANCE_REVIEWER", "DATA_REVIEWER", "VIEWER", "CUSTOMER"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid role '{role}' in token claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=str(sub),
        email=str(email),
        tenant_id=str(tenant_id),
        role=role,
        full_name=payload.get("full_name"),
    )


def require_roles(allowed_roles: List[str]):
    """
    FastAPI dependency factory enforcing Role-Based Access Control (RBAC).
    Rejects unauthorized roles with 403 Forbidden.
    """
    allowed_upper = [r.upper() for r in allowed_roles]

    async def role_dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if current_user.role not in allowed_upper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Role '{current_user.role}' is not authorized for this operation. Required: {allowed_roles}",
            )
        return current_user

    return role_dependency


async def get_current_tenant_id(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> str:
    """
    Resolves tenant context strictly from the authenticated and cryptographically
    verified JWT. Never trusts arbitrary client headers.
    """
    return current_user.tenant_id


# ============================================================================
# Fernet Token Encryption at Rest (for Zoho OAuth Access/Refresh Tokens)
# ============================================================================

def _derive_fernet_key(raw_key: str) -> bytes:
    if not raw_key:
        raw_key = "sakshi-default-secure-finance-encryption-key-32b"
    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("utf-8"))
        if len(decoded) == 32:
            return raw_key.encode("utf-8")
    except Exception:
        pass

    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet_instance() -> Fernet:
    key = _derive_fernet_key(settings.TOKEN_ENCRYPTION_KEY)
    return Fernet(key)


def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    fernet = get_fernet_instance()
    encrypted_bytes = fernet.encrypt(plain_text.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    fernet = get_fernet_instance()
    try:
        decrypted_bytes = fernet.decrypt(cipher_text.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as e:
        logger.error("Failed to decrypt token: Invalid encryption token or key mismatch.")
        raise ValueError("Decryption failed: Token is invalid or encrypted with a different key.") from e
