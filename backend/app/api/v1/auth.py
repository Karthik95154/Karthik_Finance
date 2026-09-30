import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from datetime import datetime, timedelta, timezone
from app.core.security import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    hash_password,
    hash_invitation_token,
    verify_password,
    generate_otp,
    hash_otp,
    verify_otp_hash,
    mask_email,
    validate_password_complexity,
)
from app.db.database import get_db
from app.db.models import User, Tenant, UserInvitation
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


class TokenRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    dev_role: Optional[str] = "FINANCE_USER"
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
    """Public signup is disabled. Rejects attempts with HTTP 403 Forbidden."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public registration is disabled. Only users explicitly invited by an Administrator can access Sakshi Finance.",
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

    # Auto-generate & send OTP if unverified and no active OTP exists
    if not already_verified and (not invitation.otp_hash or not invitation.otp_expires_at or invitation.otp_expires_at <= now):
        raw_otp = generate_otp()
        invitation.otp_hash = hash_otp(raw_otp)
        invitation.otp_expires_at = now + timedelta(minutes=10)
        invitation.otp_attempts = 0
        invitation.otp_last_sent_at = now
        invitation.status = "OTP_VERIFICATION_PENDING"

        await db.commit()
        await db.refresh(invitation)

        # Deliver OTP via SMTP in background
        sent, err = await email_service.send_otp_email(invitation.email, raw_otp, expires_in_minutes=10)
        if sent:
            invitation.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED"
            otp_sent = True
        else:
            invitation.email_delivery_status = "DELIVERY_FAILED"
        await db.commit()

    return ValidateInviteResponse(
        email=invitation.email,
        masked_email=mask_email(invitation.email),
        role=invitation.role,
        tenant_id=invitation.tenant_id,
        status="VALID",
        otp_verified=already_verified,
        otp_sent=otp_sent,
    )


@router.post("/accept-invite/send-otp")
async def send_invite_otp(
    payload: SendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generates a new 6-digit OTP, invalidates previous OTP, applies rate limiting, and emails the invited email."""
    raw_token = payload.token.strip() if payload.token else ""
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation token is required.")

    token_hash = hash_invitation_token(raw_token)
    query = select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid.")

    if invitation.status == "REVOKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked. Please contact your administrator.")

    if invitation.status == "ACCEPTED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used.")

    if invitation.status == "LOCKED" or invitation.otp_attempts >= 5:
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

    # Server-side Rate Limiting: Minimum 30 seconds interval between resends
    if invitation.otp_last_sent_at:
        seconds_since_last = (now - invitation.otp_last_sent_at).total_seconds()
        if seconds_since_last < 30:
            wait_time = int(30 - seconds_since_last)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {wait_time} seconds before requesting another verification code.",
            )

    raw_otp = generate_otp()
    invitation.otp_hash = hash_otp(raw_otp)
    invitation.otp_expires_at = now + timedelta(minutes=10)
    invitation.otp_attempts = 0
    invitation.otp_last_sent_at = now
    invitation.otp_verified_at = None
    invitation.status = "OTP_VERIFICATION_PENDING"

    await db.commit()
    await db.refresh(invitation)

    email_sent, email_err = await email_service.send_otp_email(invitation.email, raw_otp, expires_in_minutes=10)
    invitation.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED" if email_sent else "DELIVERY_FAILED"
    await db.commit()

    return {
        "success": True,
        "email_sent": email_sent,
        "message": f"A new verification code has been sent to {mask_email(invitation.email)}.",
        "masked_email": mask_email(invitation.email),
    }


@router.post("/accept-invite/verify-otp", response_model=VerifyOtpResponse)
async def verify_invite_otp(
    payload: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verifies supplied 6-digit OTP against stored hash, enforcing attempt limits and single-use invalidation."""
    raw_token = payload.token.strip() if payload.token else ""
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation token is required.")

    if not payload.otp or not payload.otp.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code is required.")

    token_hash = hash_invitation_token(raw_token)
    query = select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid.")

    if invitation.status == "REVOKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked. Please contact your administrator.")

    if invitation.status == "ACCEPTED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used.")

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now or invitation.status == "EXPIRED":
        invitation.status = "EXPIRED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired. Please contact your administrator for a new invitation.",
        )

    # Lockout check (Max 5 attempts)
    if invitation.status == "LOCKED" or invitation.otp_attempts >= 5:
        invitation.status = "LOCKED"
        invitation.locked_at = invitation.locked_at or now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification is temporarily locked. Please contact your administrator.",
        )

    # Check OTP expiration
    if not invitation.otp_expires_at or invitation.otp_expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or has expired.",
        )

    # Verify Hash
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

    # Success: mark email verified and invalidate single-use OTP hash
    invitation.status = "EMAIL_VERIFIED"
    invitation.otp_verified_at = now
    invitation.otp_hash = None  # Single-use enforcement
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

    if invitation.status == "REVOKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked. Please contact your administrator.")

    if invitation.status == "ACCEPTED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used.")

    if invitation.status == "LOCKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification is temporarily locked. Please contact your administrator.")

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now or invitation.status == "EXPIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired. Please contact your administrator for a new invitation.",
        )

    # SECURITY BOUNDARY: Require backend confirmed OTP verification
    if invitation.status != "EMAIL_VERIFIED" or not invitation.otp_verified_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address must be verified via OTP before account creation.",
        )

    # Check 30-minute verification session TTL
    if (now - invitation.otp_verified_at).total_seconds() > 1800:
        invitation.status = "OTP_VERIFICATION_PENDING"
        invitation.otp_verified_at = None
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification session has expired. Please verify your email again.",
        )

    # Source of truth: Email and Role come ONLY from original UserInvitation
    clean_email = invitation.email.strip().lower()
    assigned_role = invitation.role

    # Check for existing user account
    user_query = select(User).where(User.email == clean_email)
    res_user = await db.execute(user_query)
    existing_user = res_user.scalar_one_or_none()

    if existing_user:
        if existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )
        else:
            # Safely activate existing user
            existing_user.hashed_password = hash_password(payload.password)
            if payload.full_name and payload.full_name.strip():
                existing_user.full_name = payload.full_name.strip()
            existing_user.is_active = True
            existing_user.role = assigned_role
            existing_user.updated_at = now
            user = existing_user
    else:
        # Create new active User
        user = User(
            id=uuid.uuid4(),
            tenant_id=invitation.tenant_id,
            email=clean_email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name.strip() if payload.full_name else clean_email.split("@")[0].capitalize(),
            role=assigned_role,
            is_active=True,
        )
        db.add(user)

    # Mark invitation as ACCEPTED in the same transaction
    invitation.status = "ACCEPTED"
    invitation.accepted_at = now
    invitation.updated_at = now

    await db.commit()
    await db.refresh(user)

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


@router.post("/login", response_model=TokenResponse)
@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticates user with email and password, verifying account active status."""
    clean_email = payload.email.strip().lower()

    # Query user by email regardless of active flag first to differentiate invalid credentials vs inactive account
    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if user and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Please contact your administrator.",
        )

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

    must_change = getattr(user, "must_change_password", False)

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
        must_change_password=must_change,
    )

    auth_user = AuthenticatedUser(
        id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
        must_change_password=must_change,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        user=auth_user,
    )


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    is_valid, err_msg = validate_password_complexity(payload.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "Password does not meet complexity requirements.",
        )

    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    query = select(User).where(User.id == user_uuid, User.tenant_id == current_user.tenant_id)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)

    # Issue updated access token without must_change_password flag
    new_token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
        must_change_password=False,
    )

    updated_auth_user = AuthenticatedUser(
        id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
        must_change_password=False,
    )

    return {
        "message": "Password changed successfully.",
        "access_token": new_token,
        "user": updated_auth_user,
    }


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
