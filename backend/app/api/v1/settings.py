import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import Integration
from app.core.security import AuthenticatedUser, get_current_user
from app.core.security_util import encrypt_data
from app.services.imap_service import imap_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings/integrations", tags=["Integration Settings"])


class IMAPConfigureRequest(BaseModel):
    imap_server: str = Field(..., example="imap.gmail.com")
    imap_port: int = Field(993, example=993)
    email_address: str = Field(..., example="user@gmail.com")
    password: str = Field(..., example="Google App Password")


def mask_password(config: Dict[str, Any]) -> Dict[str, Any]:
    if not config:
        return {}
    masked = config.copy()
    if "password" in masked:
        masked["password"] = "••••••••••••••••"
    return masked


@router.get("/imap_email")
async def get_imap_settings(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves current user's email integration status and configuration (password masked)."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        user_filter = (Integration.user_id == user_uuid)
    except (ValueError, TypeError):
        user_filter = (Integration.id == f"imap_email_{current_user.id}")

    query = select(Integration).where(user_filter).order_by(Integration.created_at.desc())
    result = await db.execute(query)
    integration = result.scalars().first()

    if not integration or integration.status != "connected" or not integration.config:
        return {
            "id": "imap_email",
            "status": "disconnected",
            "config": None,
            "last_synced_at": None,
        }

    return {
        "id": integration.id,
        "status": integration.status,
        "config": mask_password(integration.config or {}),
        "last_synced_at": integration.last_synced_at,
    }


@router.post("/imap_email/configure")
async def configure_imap_settings(
    payload: IMAPConfigureRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validates connection and saves user's IMAP configuration securely."""
    try:
        user_uuid = uuid.UUID(current_user.id)
    except (ValueError, TypeError):
        user_uuid = None

    integration_key = f"imap_email_{current_user.id}"

    # Find existing config for this user
    query = select(Integration).where(
        or_(
            Integration.id == integration_key,
            Integration.user_id == user_uuid,
        )
    )
    result = await db.execute(query)
    integration = result.scalars().first()

    existing_config = (integration.config or {}) if integration else {}
    password = payload.password

    # Handle masked password submission (if they did not change password but hit save)
    if password == "••••••••••••••••" or password == "":
        if not existing_config.get("password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required to configure connection.",
            )
        # Use existing encrypted password
        encrypted_pwd = existing_config["password"]
    else:
        # Encrypt the new password
        try:
            encrypted_pwd = encrypt_data(password)
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption configuration error. Missing or invalid ENCRYPTION_KEY.",
            )

    config_data = {
        "imap_server": payload.imap_server.strip(),
        "imap_port": payload.imap_port,
        "email_address": payload.email_address.strip(),
        "password": encrypted_pwd,
    }

    # Validate IMAP connection using imap_service
    try:
        # Decrypted dict is passed to verification helper
        decrypted_dict = config_data.copy()
        from app.core.security_util import decrypt_data
        decrypted_dict["password"] = decrypt_data(encrypted_pwd)
        await imap_service.validate_connection(decrypted_dict)
    except Exception as e:
        logger.error(f"IMAP Connection validation failed for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to authenticate with the email server. Please verify the IMAP server, port, email address, and App Password.",
        )

    # Save to database bound to user_id
    if not integration:
        integration = Integration(
            id=integration_key,
            user_id=user_uuid,
            status="connected",
            config=config_data,
        )
        db.add(integration)
    else:
        integration.user_id = user_uuid
        integration.config = config_data
        integration.status = "connected"

    await db.commit()
    await db.refresh(integration)

    return {
        "success": True,
        "status": integration.status,
        "config": mask_password(integration.config),
    }


@router.post("/imap_email/disconnect")
async def disconnect_imap_settings(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clears configuration and disconnects user's IMAP integration."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        user_filter = or_(Integration.user_id == user_uuid, Integration.id == f"imap_email_{current_user.id}")
    except (ValueError, TypeError):
        user_filter = (Integration.user_id.is_(None))

    query = select(Integration).where(user_filter)
    result = await db.execute(query)
    integrations = result.scalars().all()

    for integration in integrations:
        integration.config = None
        integration.status = "disconnected"

    await db.commit()
    return {"success": True, "status": "disconnected"}
