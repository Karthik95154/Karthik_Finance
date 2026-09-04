import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    ALLOWED_ROLES,
)
from app.db.database import get_db
from app.db.models import User, Tenant
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserProfileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup_user(
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Registers a new user account with secure password hashing (PBKDF2-HMAC-SHA256).
    
    Security Controls:
    - Enforces password confirmation match and minimum length.
    - Prevents duplicate registration for existing emails.
    - Restricts public signup to standard non-privileged roles (DATA_REVIEWER / FINANCE).
    - Prevents arbitrary tenant spoofing.
    """
    clean_email = payload.email.strip().lower()

    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    # Check for existing email in database
    existing_query = select(User).where(User.email == clean_email)
    existing_res = await db.execute(existing_query)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # Ensure default tenant exists
    tenant_id = settings.DEFAULT_TENANT_ID
    t_query = select(Tenant).where(Tenant.id == tenant_id)
    t_res = await db.execute(t_query)
    tenant = t_res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            id=tenant_id,
            name="Default Organization",
            slug="default-org",
        )
        db.add(tenant)
        await db.commit()

    # Public signups default to standard operational role (DATA_REVIEWER)
    assigned_role = "DATA_REVIEWER"
    pwd_hash = hash_password(payload.password)
    user_id = uuid.uuid4()

    new_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=clean_email,
        password_hash=pwd_hash,
        full_name=payload.full_name.strip(),
        role=assigned_role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Issue JWT token
    token = create_access_token(
        user_id=str(new_user.id),
        email=new_user.email,
        tenant_id=new_user.tenant_id,
        role=new_user.role,
        full_name=new_user.full_name,
    )

    profile = UserProfileResponse(
        id=str(new_user.id),
        email=new_user.email,
        full_name=new_user.full_name,
        role=new_user.role,
        tenant_id=new_user.tenant_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticates a user with email and password, issuing a signed JWT access token.
    """
    clean_email = payload.email.strip().lower()

    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact your administrator.",
        )

    if not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
    )

    profile = UserProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


class LegacyTokenRequest(LoginRequest):
    password: Optional[str] = ""
    dev_role: Optional[str] = "FINANCE"
    dev_tenant_id: Optional[str] = "default-tenant-001"
    dev_name: Optional[str] = "Finance User"


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    payload: LegacyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Backward-compatible token authentication endpoint.
    If password is provided, verifies against the database.
    """
    clean_email = payload.email.strip().lower()

    if payload.password:
        return await login_user(LoginRequest(email=payload.email, password=payload.password), db=db)

    # In production without password, reject
    if settings.ENVIRONMENT in ("production", "staging") and not settings.ENABLE_DEV_AUTH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is required for production authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In dev mode fallback
    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    role = payload.dev_role.upper() if payload.dev_role else (user.role if user else "FINANCE")
    tenant_id = payload.dev_tenant_id or (user.tenant_id if user else settings.DEFAULT_TENANT_ID)
    full_name = payload.dev_name or (user.full_name if user else "Development User")
    user_id = str(user.id) if user else str(uuid.uuid4())

    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid dev_role '{role}'.",
        )

    token = create_access_token(
        user_id=user_id,
        email=clean_email,
        tenant_id=tenant_id,
        role=role,
        full_name=full_name,
    )

    profile = UserProfileResponse(
        id=user_id,
        email=clean_email,
        full_name=full_name,
        role=role,
        tenant_id=tenant_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Returns the authenticated user identity and role from the verified JWT context."""
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
    )


@router.post("/logout")
async def logout_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Logs out the authenticated user.
    """
    return {
        "status": "success",
        "message": f"User {current_user.email} logged out successfully.",
    }


@router.post("/dev-switch-role", response_model=UserProfileResponse)
async def dev_switch_role(role: str = "FINANCE"):
    """Switches the active development user role."""
    clean_role = role.strip().upper()
    if clean_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of {ALLOWED_ROLES}.",
        )
    from app.core.security import set_dev_role
    set_dev_role(clean_role)
    return UserProfileResponse(
        id="dev-user-001",
        email="customer@sakshi.ai" if clean_role == "CUSTOMER" else "finance@sakshi.ai",
        tenant_id=settings.DEFAULT_TENANT_ID,
        role=clean_role,
        full_name="Dev Customer" if clean_role == "CUSTOMER" else ("Dev Admin" if clean_role == "ADMIN" else "Dev Finance"),
    )
