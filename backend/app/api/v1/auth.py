import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from datetime import datetime, timedelta, timezone
from app.core.security import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    ALLOWED_ROLES,
    hash_invitation_token,
    generate_otp,
    hash_otp,
    verify_otp_hash,
    mask_email,
    validate_password_complexity,
)
from app.db.database import get_db
from app.db.models import User, Tenant, UserInvitation
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserProfileResponse
from app.services.email_service import email_service
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: Optional[str] = None


class ValidateInviteResponse(BaseModel):
    email: str
    masked_email: str
    role: str
    tenant_id: str
    status: str = "VALID"
    otp_verified: bool = False
    otp_sent: bool = False


class SendOtpRequest(BaseModel):
    token: str


class VerifyOtpRequest(BaseModel):
    token: str
    otp: str


class VerifyOtpResponse(BaseModel):
    success: bool = True
    message: str
    email_verified: bool = True


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup_user(
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Registers a new corporate user, provisions default tenant if necessary,
    and returns a valid JWT authentication token.
    """
    clean_email = payload.email.strip().lower()

    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password confirmation does not match the provided password.",
        )

    # Check existing user
    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    existing_user = res.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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

    if not user:
        t_query = select(Tenant).where(Tenant.id == tenant_id)
        t_res = await db.execute(t_query)
        tenant_obj = t_res.scalar_one_or_none()
        if not tenant_obj:
            tenant_obj = Tenant(
                id=tenant_id,
                name=f"Org {tenant_id}",
                slug=f"org-{tenant_id.lower()}",
            )
            db.add(tenant_obj)
            await db.flush()

        new_uuid = uuid.uuid4()
        user = User(
            id=new_uuid,
            tenant_id=tenant_id,
            email=clean_email,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception:
            await db.rollback()
            query = select(User).where(User.email == clean_email)
            res = await db.execute(query)
            user = res.scalar_one_or_none()

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


@router.get("/accept-invite/validate", response_model=ValidateInviteResponse)
async def validate_invitation_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Validates an invitation token, initiates OTP verification dispatch if unverified, and returns metadata."""
    if not token or not token.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation token is required.")

    token_hash = hash_invitation_token(token.strip())
    query = select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid.")

    if invitation.status == "REVOKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked. Please contact your administrator.")

    if invitation.status == "ACCEPTED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used.")

    if invitation.status == "LOCKED" or (invitation.otp_attempts and invitation.otp_attempts >= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification is temporarily locked. Please contact your administrator.",
        )

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now or invitation.status == "EXPIRED":
        invitation.status = "EXPIRED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired. Please contact your administrator for a new invitation.",
        )

    otp_sent = False
    already_verified = bool(invitation.status == "EMAIL_VERIFIED" and invitation.otp_verified_at)

    if not already_verified and not invitation.otp_hash:
        raw_otp = generate_otp()
        invitation.otp_hash = hash_otp(raw_otp)
        invitation.otp_expires_at = now + timedelta(minutes=15)
        invitation.otp_attempts = 0
        invitation.otp_last_sent_at = now
        invitation.status = "OTP_VERIFICATION_PENDING"
        await db.commit()

        email_res = await email_service.send_verification_otp(
            to_email=invitation.email,
            otp=raw_otp,
            recipient_name=invitation.email.split("@")[0],
        )
        is_success = bool(email_res.get("success")) if isinstance(email_res, dict) else (bool(email_res[0]) if isinstance(email_res, (tuple, list)) else bool(email_res))
        invitation.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED" if is_success else "DELIVERY_FAILED"
        await db.commit()
        otp_sent = True

    return ValidateInviteResponse(
        email=invitation.email,
        masked_email=mask_email(invitation.email),
        role=invitation.role,
        tenant_id=invitation.tenant_id,
        status="VALID",
        otp_verified=already_verified,
        otp_sent=otp_sent or bool(invitation.otp_last_sent_at),
    )


@router.post("/accept-invite/send-otp")
async def resend_invitation_otp(
    payload: SendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generates and emails a new 6-digit OTP code to the invited user's email address."""
    raw_token = payload.token.strip() if payload.token else ""
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation token is required.")

    token_hash = hash_invitation_token(raw_token)
    query = select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid.")

    if invitation.status in ("REVOKED", "ACCEPTED", "LOCKED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot send verification code for this invitation.")

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now:
        invitation.status = "EXPIRED"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired.")

    # Rate Limit Check: 30s cooldown
    if invitation.otp_last_sent_at:
        last_sent = invitation.otp_last_sent_at
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed = (now - last_sent).total_seconds()
        if elapsed < 30:
            remaining = max(1, 30 - int(elapsed))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting a new verification code.",
            )

    raw_otp = generate_otp()
    invitation.otp_hash = hash_otp(raw_otp)
    invitation.otp_expires_at = now + timedelta(minutes=15)
    invitation.otp_attempts = 0
    invitation.otp_last_sent_at = now
    invitation.status = "OTP_VERIFICATION_PENDING"
    await db.commit()

    email_res = await email_service.send_verification_otp(
        to_email=invitation.email,
        otp=raw_otp,
        recipient_name=invitation.email.split("@")[0],
    )
    is_success = bool(email_res.get("success")) if isinstance(email_res, dict) else (bool(email_res[0]) if isinstance(email_res, (tuple, list)) else bool(email_res))
    invitation.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED" if is_success else "DELIVERY_FAILED"
    await db.commit()

    return {
        "success": True,
        "message": f"Verification code sent to {mask_email(invitation.email)}",
        "email_delivery_status": invitation.email_delivery_status,
    }


@router.post("/accept-invite/verify-otp", response_model=VerifyOtpResponse)
async def verify_invitation_otp(
    payload: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verifies the submitted 6-digit OTP against the invitation record."""
    raw_token = payload.token.strip() if payload.token else ""
    if not raw_token or not payload.otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token and verification code are required.")

    token_hash = hash_invitation_token(raw_token)
    query = select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid.")

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now or invitation.status == "EXPIRED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired.")

    if invitation.status == "LOCKED" or (invitation.otp_attempts and invitation.otp_attempts >= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification is temporarily locked. Please contact your administrator.",
        )

    if not invitation.otp_expires_at or invitation.otp_expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or has expired.",
        )

    is_valid = verify_otp_hash(payload.otp, invitation.otp_hash)
    if not is_valid:
        invitation.otp_attempts += 1
        if invitation.otp_attempts >= 5:
            invitation.status = "LOCKED"
            invitation.locked_at = now
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification is temporarily locked. Please contact your administrator.",
            )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or has expired.",
        )

    invitation.status = "EMAIL_VERIFIED"
    invitation.otp_verified_at = now
    invitation.otp_hash = None
    await db.commit()

    return VerifyOtpResponse(
        success=True,
        message="Email ownership verified successfully. You may now create your password.",
        email_verified=True,
    )


@router.post("/accept-invite", response_model=TokenResponse)
async def accept_invitation(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accepts a valid, verified invitation, creates and activates the user account, and issues an access token."""
    raw_token = payload.token.strip() if payload.token else ""
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation token is required.")

    if not payload.password or len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    token_hash = hash_invitation_token(raw_token)
    query = select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid.")

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now or invitation.status == "EXPIRED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired.")

    if invitation.status != "EMAIL_VERIFIED" and not invitation.otp_verified_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address must be verified via OTP before creating account.",
        )

    # Check existing user
    user_query = select(User).where(User.email == invitation.email)
    user_res = await db.execute(user_query)
    user = user_res.scalar_one_or_none()

    if user:
        user.password_hash = hash_password(payload.password)
        user.is_active = True
        user.role = invitation.role
        if payload.full_name and payload.full_name.strip():
            user.full_name = payload.full_name.strip()
    else:
        user = User(
            id=uuid.uuid4(),
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name.strip() if payload.full_name else invitation.email.split("@")[0],
            role=invitation.role,
            is_active=True,
        )
        db.add(user)

    invitation.status = "ACCEPTED"
    invitation.accepted_at = now
    await db.commit()
    await db.refresh(user)

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


@router.post("/change-password")
async def change_user_password(
    payload: ChangePasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Changes the current authenticated user's password."""
    try:
        user_uuid = uuid.UUID(current_user.id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")

    query = select(User).where(User.id == user_uuid)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not user.password_hash or not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password does not match.")

    if not payload.new_password or len(payload.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 6 characters.")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    await db.commit()

    return {"success": True, "message": "Password changed successfully."}


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
    """Logs out the authenticated user."""
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
