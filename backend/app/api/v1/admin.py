import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    hash_invitation_token,
    require_roles,
)
from app.db.database import get_db
from app.db.models import User, UserInvitation
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Administration"])

# Depend strictly on ADMIN role
admin_required = require_roles(["ADMIN"])


# --- Schemas ---

class CreateUserPayload(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: Optional[str] = "FINANCE_USER"


class UserItemResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    must_change_password: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class CreateUserResponse(BaseModel):
    success: bool = True
    message: str
    user: UserItemResponse
    temporary_password: str


class InviteUserPayload(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: Optional[str] = "FINANCE_USER"


class InvitationItemResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    email_delivery_status: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None
    invitation_url: Optional[str] = None

    class Config:
        from_attributes = True


class InviteActionResponse(BaseModel):
    success: bool = True
    email_sent: bool = True
    message: str
    invitation: InvitationItemResponse
    invitation_url: str



# --- Endpoints ---

def generate_secure_temporary_password() -> str:
    """Generates a 12-character cryptographically secure temporary password (e.g. X7mQ-92Lp-K4tZ)."""
    p1 = secrets.token_hex(2).upper()
    p2 = secrets.token_hex(2).upper()
    p3 = secrets.token_hex(2).upper()
    return f"{p1}-{p2}-{p3}"


@router.post("/users", response_model=CreateUserResponse)
async def create_user_account(
    payload: CreateUserPayload,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """
    Direct Admin User Provisioning.
    Creates an active user account with a secure temporary password and must_change_password=True.
    Strictly restricted to ADMIN users.
    """
    clean_email = payload.email.strip().lower()

    if not email_service.validate_email_format(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address provided is invalid.",
        )

    # 1. Check if user already exists
    user_query = select(User).where(User.email == clean_email, User.tenant_id == admin.tenant_id)
    res = await db.execute(user_query)
    existing_user = res.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user account with this email address already exists.",
        )

    # Role check: Default to FINANCE_USER
    role_to_assign = payload.role.strip().upper() if payload.role else "FINANCE_USER"
    if role_to_assign not in ("ADMIN", "FINANCE_ADMIN", "FINANCE_USER", "FINANCE", "VIEWER"):
        role_to_assign = "FINANCE_USER"

    # Generate secure temporary password & hash it
    temp_password = generate_secure_temporary_password()
    from app.core.security import hash_password
    hashed_pwd = hash_password(temp_password)

    new_user = User(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        email=clean_email,
        password_hash=hashed_pwd,
        hashed_password=hashed_pwd,
        full_name=payload.full_name.strip() if payload.full_name else clean_email.split("@")[0].capitalize(),
        role=role_to_assign,
        is_active=True,
        must_change_password=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"[ADMIN CREATED USER] Admin '{admin.email}' created user account for '{clean_email}' with role '{role_to_assign}'.")

    return CreateUserResponse(
        success=True,
        message=f"User account created successfully for {clean_email}.",
        user=UserItemResponse(
            id=str(new_user.id),
            email=new_user.email,
            full_name=new_user.full_name,
            role=new_user.role,
            is_active=new_user.is_active,
            must_change_password=new_user.must_change_password,
            created_at=new_user.created_at,
        ),
        temporary_password=temp_password,
    )


@router.get("/users", response_model=List[UserItemResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Lists all users in the application for administration."""
    query = select(User).where(User.tenant_id == admin.tenant_id).order_by(User.created_at.desc())
    res = await db.execute(query)
    users = res.scalars().all()
    return [
        UserItemResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            must_change_password=getattr(u, "must_change_password", False),
            created_at=u.created_at,
        )
        for u in users
    ]


@router.get("/invitations", response_model=List[InvitationItemResponse])
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Lists all invitations in the tenant."""
    query = select(UserInvitation).where(UserInvitation.tenant_id == admin.tenant_id).order_by(UserInvitation.created_at.desc())
    res = await db.execute(query)
    invitations = res.scalars().all()

    now = datetime.now(timezone.utc)
    results = []
    for inv in invitations:
        # Auto-evaluate EXPIRED status if marked pending or creation stage past expiration
        curr_status = inv.status
        if curr_status in ("PENDING", "OTP_VERIFICATION_PENDING", "EMAIL_DELIVERY_ACCEPTED") and inv.expires_at <= now:
            curr_status = "EXPIRED"

        results.append(
            InvitationItemResponse(
                id=str(inv.id),
                email=inv.email,
                role=inv.role,
                status=curr_status,
                email_delivery_status=inv.email_delivery_status,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
                accepted_at=inv.accepted_at,
            )
        )
    return results


@router.post("/invitations", response_model=InviteActionResponse)
async def invite_user(
    payload: InviteUserPayload,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Creates a new invitation for a user, generates an invitation link, and emails the user."""
    clean_email = payload.email.strip().lower()

    # 0. Upfront Email Format Validation
    if not email_service.validate_email_format(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address provided is invalid.",
        )

    # 1. Check if user with this email already exists
    user_query = select(User).where(User.email == clean_email, User.tenant_id == admin.tenant_id)
    res = await db.execute(user_query)
    existing_user = res.scalar_one_or_none()
    if existing_user:
        if existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An inactive user account with this email already exists. Please reactivate the user.",
            )

    # 2. Check for existing non-accepted invitation
    inv_query = select(UserInvitation).where(
        UserInvitation.email == clean_email,
        UserInvitation.tenant_id == admin.tenant_id,
        UserInvitation.status != "ACCEPTED",
    )
    res_inv = await db.execute(inv_query)
    existing_inv = res_inv.scalar_one_or_none()

    # Generate secure random token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    role_to_assign = "FINANCE_USER"  # For first version, only FINANCE_USER allowed for invited users

    if existing_inv:
        existing_inv.token_hash = token_hash
        existing_inv.expires_at = expires_at
        existing_inv.status = "OTP_VERIFICATION_PENDING"
        existing_inv.role = role_to_assign
        existing_inv.otp_attempts = 0
        existing_inv.otp_hash = None
        existing_inv.otp_verified_at = None
        existing_inv.locked_at = None
        invitation = existing_inv
    else:
        invitation = UserInvitation(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            email=clean_email,
            role=role_to_assign,
            invited_by=uuid.UUID(admin.id) if admin.id and admin.id != "dev-user-001" else None,
            token_hash=token_hash,
            expires_at=expires_at,
            status="OTP_VERIFICATION_PENDING",
        )
        db.add(invitation)

    await db.commit()
    await db.refresh(invitation)

    # Construct invitation URL
    frontend_base = settings.FRONTEND_URL.rstrip("/")
    invitation_url = f"{frontend_base}/accept-invite?token={raw_token}"
    logger.info(f"[INVITATION CREATED] Target: {clean_email} | Link: {invitation_url}")

    # Send Automated Invitation Email
    email_sent, email_err = await email_service.send_invitation_email(
        recipient_email=clean_email,
        recipient_name=payload.full_name,
        invitation_url=invitation_url,
        expires_at=invitation.expires_at,
    )

    invitation.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED" if email_sent else "DELIVERY_FAILED"
    await db.commit()
    await db.refresh(invitation)

    if email_sent:
        response_msg = f"Invitation link generated and email accepted for delivery to {clean_email}. Mailbox verification pending OTP."
    else:
        response_msg = f"Invitation created for {clean_email}, but the email could not be delivered. {email_err or ''}".strip()

    return InviteActionResponse(
        success=True,
        email_sent=email_sent,
        message=response_msg,
        invitation=InvitationItemResponse(
            id=str(invitation.id),
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            email_delivery_status=invitation.email_delivery_status,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
        ),
        invitation_url=invitation_url,
    )


@router.post("/invitations/{invitation_id}/resend", response_model=InviteActionResponse)
async def resend_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Invalidates old invitation token, issues a new invitation link, and emails the user."""
    try:
        inv_uuid = uuid.UUID(invitation_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation ID format.")

    query = select(UserInvitation).where(
        UserInvitation.id == inv_uuid,
        UserInvitation.tenant_id == admin.tenant_id,
    )
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if invitation.status == "ACCEPTED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has already been accepted.")

    # Invalidate previous token & OTP state, generate new secure token
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hash_invitation_token(raw_token)
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    invitation.status = "OTP_VERIFICATION_PENDING"
    invitation.otp_attempts = 0
    invitation.otp_hash = None
    invitation.otp_verified_at = None
    invitation.locked_at = None
    invitation.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(invitation)

    frontend_base = settings.FRONTEND_URL.rstrip("/")
    invitation_url = f"{frontend_base}/accept-invite?token={raw_token}"
    logger.info(f"[INVITATION RESENT] Target: {invitation.email} | New Link: {invitation_url}")

    # Resend Automated Invitation Email
    email_sent, email_err = await email_service.send_invitation_email(
        recipient_email=invitation.email,
        recipient_name=None,
        invitation_url=invitation_url,
        expires_at=invitation.expires_at,
    )

    invitation.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED" if email_sent else "DELIVERY_FAILED"
    await db.commit()
    await db.refresh(invitation)

    if email_sent:
        response_msg = f"Invitation resent successfully to {invitation.email}."
    else:
        response_msg = f"Invitation link regenerated for {invitation.email}, but the email could not be sent."

    return InviteActionResponse(
        success=True,
        email_sent=email_sent,
        message=response_msg,
        invitation=InvitationItemResponse(
            id=str(invitation.id),
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            email_delivery_status=invitation.email_delivery_status,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
        ),
        invitation_url=invitation_url,
    )


@router.post("/invitations/{invitation_id}/revoke")
async def revoke_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Revokes a pending invitation."""
    try:
        inv_uuid = uuid.UUID(invitation_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation ID format.")

    query = select(UserInvitation).where(
        UserInvitation.id == inv_uuid,
        UserInvitation.tenant_id == admin.tenant_id,
    )
    res = await db.execute(query)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if invitation.status == "ACCEPTED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revoke an accepted invitation.")

    invitation.status = "REVOKED"
    invitation.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": f"Invitation for {invitation.email} has been revoked.", "id": str(invitation.id)}


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Deactivates a user account."""
    try:
        u_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    query = select(User).where(User.id == u_uuid, User.tenant_id == admin.tenant_id)
    res = await db.execute(query)
    target_user = res.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Protection: Prevent deactivating the last active ADMIN
    if target_user.role == "ADMIN" and target_user.is_active:
        admin_count_query = select(func.count(User.id)).where(
            User.tenant_id == admin.tenant_id,
            User.role == "ADMIN",
            User.is_active == True,
        )
        admin_count_res = await db.execute(admin_count_query)
        active_admins = admin_count_res.scalar() or 0
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one active administrator must remain.",
            )

    target_user.is_active = False
    target_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": f"User {target_user.email} has been deactivated.", "id": str(target_user.id), "is_active": False}


@router.patch("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(admin_required),
):
    """Reactivates an inactive user account."""
    try:
        u_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    query = select(User).where(User.id == u_uuid, User.tenant_id == admin.tenant_id)
    res = await db.execute(query)
    target_user = res.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    target_user.is_active = True
    target_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": f"User {target_user.email} has been reactivated.", "id": str(target_user.id), "is_active": True}
