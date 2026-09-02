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
)
from app.db.database import get_db
from app.db.models import User, Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenRequest(BaseModel):
    email: EmailStr
    # Optional parameters strictly available ONLY in development mode
    dev_role: Optional[str] = "FINANCE"
    dev_tenant_id: Optional[str] = "default-tenant-001"
    dev_name: Optional[str] = "Finance User"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUser


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Issues a verified JWT access token.
    
    SECURITY POLICY:
    - In PRODUCTION (settings.ENABLE_DEV_AUTH is False):
      Identity, tenant_id, and role are strictly queried from the database.
      Client cannot supply arbitrary roles or tenants.
    - In DEVELOPMENT (settings.ENABLE_DEV_AUTH is True):
      Convenient local token generation is enabled for testing.
    """
    clean_email = payload.email.strip().lower()

    if not settings.ENABLE_DEV_AUTH:
        # PRODUCTION AUTHENTICATION: Must match existing verified user in DB
        query = select(User).where(User.email == clean_email, User.is_active == True)
        res = await db.execute(query)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials: User not found or inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

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
    else:
        # Lookup user in DB or use dev parameters
        user = None
        try:
            query = select(User).where(User.email == clean_email)
            res = await db.execute(query)
            user = res.scalar_one_or_none()
        except Exception as db_err:
            logger.warning(f"Development auth: DB query skipped ({db_err}), generating dev token.")

        role = payload.dev_role.upper() if payload.dev_role else "FINANCE"
        tenant_id = payload.dev_tenant_id or settings.DEFAULT_TENANT_ID
        full_name = payload.dev_name or "Development User"
        user_id = str(user.id) if user else str(uuid.uuid4())

        if role not in ("ADMIN", "FINANCE", "VIEWER", "CUSTOMER"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dev_role '{role}'. Must be ADMIN, FINANCE, VIEWER, or CUSTOMER.",
            )

        token = create_access_token(
            user_id=user_id,
            email=clean_email,
            tenant_id=tenant_id,
            role=role,
            full_name=full_name,
        )

        auth_user = AuthenticatedUser(
            id=user_id,
            email=clean_email,
            tenant_id=tenant_id,
            role=role,
            full_name=full_name,
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
