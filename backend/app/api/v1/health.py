from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.database import get_db
from app.schemas.invoice import HealthResponse
from app.storage.supabase_storage import storage_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check verifying database and storage connectivity."""
    db_status = "error"
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    storage_status = "disconnected"
    try:
        if await storage_service.check_health():
            storage_status = "connected"
    except Exception as e:
        storage_status = f"error: {str(e)}"

    from app.services.ai_service import ai_service
    colab_status = "unreachable"
    try:
        if await ai_service.check_colab_health():
            colab_status = "reachable"
    except Exception as e:
        colab_status = f"error: {str(e)}"

    from app.services.accounting_service import accounting_service
    colab_acc_status = "unreachable"
    try:
        if await accounting_service.check_health():
            colab_acc_status = "reachable"
    except Exception as e:
        colab_acc_status = f"error: {str(e)}"

    overall_status = (
        "ok"
        if db_status == "connected" and storage_status == "connected"
        else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        project=settings.PROJECT_NAME,
        database=db_status,
        storage=storage_status,
        colab_vlm=colab_status,
        colab_accounting=colab_acc_status,
        timestamp=datetime.now(timezone.utc),
    )
