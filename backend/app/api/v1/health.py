import time
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.database import get_db
from app.schemas.invoice import HealthResponse, ServiceHealthDetail
from app.storage.supabase_storage import storage_service
from app.services.ai_service import ai_service
from app.services.accounting_service import accounting_service

from app.services.tds_service import tds_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check verifying database, storage, and AI endpoints with latency and exact status codes."""
    services_map: Dict[str, ServiceHealthDetail] = {}

    # 1. Database Check
    t0 = time.time()
    db_status = "error"
    db_msg = "Database connection error"
    db_code = 500
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"
            db_msg = "Connected (SELECT 1 OK)"
            db_code = 200
    except Exception as e:
        db_status = "disconnected"
        db_msg = f"Database Error: {str(e)}"
    db_latency = round((time.time() - t0) * 1000, 1)
    services_map["database"] = ServiceHealthDetail(
        name="PostgreSQL Database",
        status=db_status,
        status_code=db_code,
        message=db_msg,
        latency_ms=db_latency,
        endpoint="PostgreSQL / SQLAlchemy Async",
    )

    # 2. Supabase Storage Check
    t0 = time.time()
    storage_status = "disconnected"
    storage_msg = "Supabase Storage unavailable"
    storage_code = 500
    try:
        if await storage_service.check_health():
            storage_status = "connected"
            storage_msg = "Connected & Bucket Accessible"
            storage_code = 200
    except Exception as e:
        storage_status = "error"
        storage_msg = f"Storage Error: {str(e)}"
    storage_latency = round((time.time() - t0) * 1000, 1)
    services_map["storage"] = ServiceHealthDetail(
        name="Supabase File Storage",
        status=storage_status,
        status_code=storage_code,
        message=storage_msg,
        latency_ms=storage_latency,
        endpoint=settings.SUPABASE_URL,
    )

    # 3. Colab Qwen3-VL Engine Check
    vlm_detailed = await ai_service.check_colab_health_detailed()
    services_map["colab_vlm"] = ServiceHealthDetail(
        name=vlm_detailed.get("name", "Qwen3-VL Vision Engine"),
        status=vlm_detailed.get("status", "offline"),
        status_code=vlm_detailed.get("status_code"),
        message=vlm_detailed.get("message", "Unknown"),
        latency_ms=vlm_detailed.get("latency_ms"),
        endpoint=vlm_detailed.get("endpoint"),
    )

    # 4. Colab Qwen3-4B Accounting / COA Engine Check
    acc_detailed = await accounting_service.check_health_detailed()
    services_map["colab_accounting"] = ServiceHealthDetail(
        name=acc_detailed.get("name", "Qwen3-4B Accounting Engine"),
        status=acc_detailed.get("status", "offline"),
        status_code=acc_detailed.get("status_code"),
        message=acc_detailed.get("message", "Unknown"),
        latency_ms=acc_detailed.get("latency_ms"),
        endpoint=acc_detailed.get("endpoint"),
    )

    # 5. Colab Qwen3-4B TDS Engine Check
    tds_detailed = await tds_service.check_health_detailed()
    services_map["colab_tds"] = ServiceHealthDetail(
        name=tds_detailed.get("name", "Qwen3-4B TDS Engine"),
        status=tds_detailed.get("status", "offline"),
        status_code=tds_detailed.get("status_code"),
        message=tds_detailed.get("message", "Unknown"),
        latency_ms=tds_detailed.get("latency_ms"),
        endpoint=tds_detailed.get("endpoint"),
    )

    # 6. FastAPI Backend Engine
    services_map["backend"] = ServiceHealthDetail(
        name="FastAPI Finance Core",
        status="online",
        status_code=200,
        message="200 OK - Core Engine Running",
        latency_ms=0.5,
        endpoint="http://127.0.0.1:8000/api/v1",
    )

    # Summary overall status
    is_core_ok = (db_status == "connected" and storage_status == "connected")
    is_vlm_ok = (vlm_detailed.get("status") == "online")
    is_acc_ok = (acc_detailed.get("status") == "online")
    is_tds_ok = (tds_detailed.get("status") == "online")

    if is_core_ok and is_vlm_ok and is_acc_ok:
        overall_status = "ok"
    elif is_core_ok:
        overall_status = "degraded"
    else:
        overall_status = "error"

    return HealthResponse(
        status=overall_status,
        project=settings.PROJECT_NAME,
        database=db_status,
        storage=storage_status,
        colab_vlm=vlm_detailed.get("message"),
        colab_accounting=acc_detailed.get("message"),
        colab_tds=tds_detailed.get("message"),
        services=services_map,
        timestamp=datetime.now(timezone.utc),
    )
