import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.db.models import User, Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    dev_role: Optional[str] = "FINANCE"
    dev_tenant_id: Optional[str] = "default-tenant-001"
    dev_name: Optional[str] = "Finance User"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUser


@router.post("/signup", response_model=TokenResponse)
async def signup_user(
    payload: SignUpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Registers a new user with email and hashed password."""
    clean_email = payload.email.strip().lower()
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    # Check for existing email
    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    existing_user = res.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered.",
        )

    tenant_id = settings.DEFAULT_TENANT_ID
    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(id=tenant_id, name="Default Tenant", slug=f"tenant-{tenant_id}")
        db.add(tenant)
        await db.flush()

    new_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=clean_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name or clean_email.split("@")[0].capitalize(),
        role="FINANCE",
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(
        user_id=str(new_user.id),
        email=new_user.email,
        tenant_id=new_user.tenant_id,
        role=new_user.role,
        full_name=new_user.full_name,
    )

    auth_user = AuthenticatedUser(
        id=str(new_user.id),
        email=new_user.email,
        tenant_id=new_user.tenant_id,
        role=new_user.role,
        full_name=new_user.full_name,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        user=auth_user,
    )


@router.post("/login", response_model=TokenResponse)
@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticates user with email and password, issuing a verified JWT."""
    clean_email = payload.email.strip().lower()

    query = select(User).where(User.email == clean_email, User.is_active == True)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    # Password validation
    if payload.password:
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # Dev fallback if password omitted during dev testing
        if not settings.ENABLE_DEV_AUTH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not user:
        # Development fallback user provisioning
        tenant_id = payload.dev_tenant_id or settings.DEFAULT_TENANT_ID
        role = payload.dev_role.upper() if payload.dev_role else "FINANCE"
        full_name = payload.dev_name or clean_email.split("@")[0].capitalize()

        tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(id=tenant_id, name="Default Tenant", slug=f"tenant-{tenant_id}")
            db.add(tenant)
            await db.flush()

        new_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email=clean_email,
            hashed_password=hash_password(payload.password) if payload.password else None,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        user = new_user

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
    )

    auth_user = AuthenticatedUser(
        id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        user=auth_user,
    )


@router.get("/me", response_model=AuthenticatedUser)
async def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Returns the authenticated user identity and role from the verified JWT."""
    return current_user


@router.post("/dev-switch-role", response_model=AuthenticatedUser)
async def dev_switch_role(role: str = "FINANCE"):
    """Switches the active development user role between ADMIN, FINANCE, and VIEWER."""
    clean_role = role.strip().upper()
    if clean_role not in ("ADMIN", "FINANCE", "VIEWER", "CUSTOMER"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be ADMIN, FINANCE, VIEWER, or CUSTOMER.",
        )
    from app.core.security import set_dev_role
    set_dev_role(clean_role)
    return AuthenticatedUser(
        id="dev-user-001",
        email="customer@sakshi.ai" if clean_role == "CUSTOMER" else "finance@sakshi.ai",
        tenant_id=settings.DEFAULT_TENANT_ID,
        role=clean_role,
        full_name="Dev Customer" if clean_role == "CUSTOMER" else ("Dev Admin" if clean_role == "ADMIN" else "Dev Finance"),
    )
