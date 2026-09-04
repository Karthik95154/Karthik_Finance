import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import Integration, EmailConnection
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
    """Retrieves current user's active email connection (password masked)."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        filter_clause = or_(EmailConnection.user_id == user_uuid, EmailConnection.user_id_str == str(current_user.id))
    except (ValueError, TypeError):
        filter_clause = (EmailConnection.user_id_str == str(current_user.id))

    query = select(EmailConnection).where(filter_clause, EmailConnection.is_active == True)
    result = await db.execute(query)
    conn = result.scalars().first()

    if not conn:
        return {
            "id": f"email_conn_{current_user.id}",
            "status": "disconnected",
            "config": None,
            "last_synced_at": None,
        }

    config = {
        "imap_server": conn.imap_host,
        "imap_port": conn.imap_port,
        "email_address": conn.email_address,
        "password": conn.encrypted_password,
    }

    return {
        "id": str(conn.id),
        "status": "connected" if conn.is_active else "disconnected",
        "config": mask_password(config),
        "last_synced_at": conn.last_synced_at,
    }


@router.post("/imap_email/configure")
async def configure_imap_settings(
    payload: IMAPConfigureRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Configures or updates current user's single active EmailConnection."""
    try:
        user_uuid = uuid.UUID(current_user.id)
    except (ValueError, TypeError):
        user_uuid = None

    try:
        filter_clause = or_(
            (EmailConnection.user_id == user_uuid) if user_uuid else False,
            EmailConnection.user_id_str == str(current_user.id)
        )
    except Exception:
        filter_clause = (EmailConnection.user_id_str == str(current_user.id))

    target_email = payload.email_address.strip().lower()

    # Check if ANOTHER user account is ALREADY actively connected to this email address
    query_others = select(EmailConnection).where(EmailConnection.is_active == True)
    res_others = await db.execute(query_others)
    active_connections = res_others.scalars().all()
    for active_conn in active_connections:
        is_owner = False
        if user_uuid and active_conn.user_id == user_uuid:
            is_owner = True
        elif active_conn.user_id_str == str(current_user.id):
            is_owner = True

        if not is_owner and active_conn.email_address.strip().lower() == target_email:
            logger.warning(f"REJECTED: User {current_user.id} tried to connect {target_email} which is already connected by user {active_conn.user_id_str or active_conn.user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This email account ({target_email}) is already connected to another user account. Connection rejected.",
            )

    # Look up current user's existing connection
    query = select(EmailConnection).where(filter_clause)
    result = await db.execute(query)
    existing_conn = result.scalars().first()

    password = payload.password
    # Handle masked password submission if updating existing config
    if password == "••••••••••••••••" or password == "":
        if not existing_conn or not existing_conn.encrypted_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required to configure connection.",
            )
        encrypted_pwd = existing_conn.encrypted_password
    else:
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
        decrypted_dict = config_data.copy()
        from app.core.security_util import decrypt_data
        decrypted_dict["password"] = decrypt_data(encrypted_pwd)
        await imap_service.validate_connection(decrypted_dict)
    except Exception as e:
        logger.error(f"IMAP Connection validation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to authenticate with the email server. Please verify the IMAP server, port, email address, and App Password.",
        )

    # Update existing user connection or create new EmailConnection record
    if existing_conn:
        existing_conn.user_id = user_uuid
        existing_conn.user_id_str = str(current_user.id)
        existing_conn.email_address = payload.email_address.strip()
        existing_conn.encrypted_password = encrypted_pwd
        existing_conn.imap_host = payload.imap_server.strip()
        existing_conn.imap_port = payload.imap_port
        existing_conn.is_active = True
        conn_record = existing_conn
    else:
        conn_record = EmailConnection(
            user_id=user_uuid,
            user_id_str=str(current_user.id),
            email_address=payload.email_address.strip(),
            encrypted_password=encrypted_pwd,
            imap_host=payload.imap_server.strip(),
            imap_port=payload.imap_port,
            is_active=True,
        )
        db.add(conn_record)

    await db.commit()
    await db.refresh(conn_record)

    return {
        "success": True,
        "status": "connected",
        "config": mask_password(config_data),
    }


@router.post("/imap_email/disconnect")
async def disconnect_imap_settings(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnects the current user's email connection."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        filter_clause = or_(EmailConnection.user_id == user_uuid, EmailConnection.user_id_str == str(current_user.id))
    except (ValueError, TypeError):
        filter_clause = (EmailConnection.user_id_str == str(current_user.id))

    query = select(EmailConnection).where(filter_clause)
    result = await db.execute(query)
    connections = result.scalars().all()

    for conn in connections:
        conn.is_active = False

    await db.commit()
    return {"success": True, "status": "disconnected"}
