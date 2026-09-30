import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.settings import router as settings_router
from app.api.v1.inbox import router as inbox_router
from app.api.v1.zoho import router as zoho_router
from app.api.v1.hitl import router as hitl_router
from app.api.v1.review import router as review_router
from app.api.v1.admin import router as admin_router
from app.api.v1.forex import router as forex_router
from app.core.config import settings
from app.services.email_scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME} backend...")
    async def init_db():
        try:
            from app.db.database import engine, Base
            import app.db.models
            from sqlalchemy import text
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                
                # Ensure newly added columns exist on invoices table
                migration_columns = [
                    ("user_id", "UUID REFERENCES users(id) ON DELETE SET NULL"),
                    ("financial_relevance", "VARCHAR(50)"),
                    ("document_type", "VARCHAR(50)"),
                    ("classification_confidence", "FLOAT"),
                    ("classification_reason", "TEXT"),
                    ("classification_model", "VARCHAR(100)"),
                    ("email_subject", "VARCHAR(255)"),
                    ("email_sender", "VARCHAR(255)"),
                    ("email_received_at", "TIMESTAMP WITH TIME ZONE"),
                    ("email_message_id", "VARCHAR(255)"),
                    ("confidence_score", "FLOAT"),
                    ("accounting_confidence", "FLOAT"),
                    ("zoho_bill_id", "VARCHAR(100)"),
                    ("zoho_bill_number", "VARCHAR(100)"),
                    ("exported_at", "TIMESTAMP WITH TIME ZONE"),
                    ("locked_at", "TIMESTAMP WITH TIME ZONE"),
                    ("error_message", "TEXT"),
                    ("invoice_type", "VARCHAR(50) DEFAULT 'VENDOR_INVOICE'"),
                    ("raw_vlm_output", "JSONB"),
                    ("current_vlm_output", "JSONB"),
                    ("accounting_output", "JSONB"),
                    ("current_accounting_output", "JSONB"),
                    ("gst_result", "JSONB"),
                    ("itc_result", "JSONB"),
                    ("financial_validation_result", "JSONB"),
                    ("journal_entry", "JSONB"),
                    ("period_category", "VARCHAR(50)"),
                    ("period_decision", "VARCHAR(50) DEFAULT 'NOT_REQUIRED'"),
                    ("posting_date", "DATE"),
                    ("period_resolution", "VARCHAR(50) DEFAULT 'NONE'"),
                    ("period_resolution_reason", "TEXT"),
                    ("period_resolved_by", "VARCHAR(255)"),
                    ("period_resolved_at", "TIMESTAMP WITH TIME ZONE"),
                    ("invoice_origin", "VARCHAR(50) DEFAULT 'INDIAN'"),
                    ("currency", "VARCHAR(10) DEFAULT 'INR'"),
                    ("classification_source", "VARCHAR(50) DEFAULT 'SYSTEM'"),
                    ("classification_override", "VARCHAR(50)"),
                    ("classification_override_reason", "TEXT"),
                    ("classified_by", "VARCHAR(100)"),
                    ("classified_at", "TIMESTAMP WITH TIME ZONE"),
                    ("original_currency", "VARCHAR(10) DEFAULT 'INR'"),
                    ("original_total_amount", "NUMERIC(15, 2)"),
                    ("original_taxable_amount", "NUMERIC(15, 2)"),
                    ("exchange_rate", "NUMERIC(15, 6) DEFAULT 1.000000"),
                    ("exchange_rate_date", "DATE"),
                    ("exchange_rate_source", "VARCHAR(100) DEFAULT 'SYSTEM_DEFAULT'"),
                    ("converted_total_inr", "NUMERIC(15, 2)"),
                    ("converted_taxable_inr", "NUMERIC(15, 2)"),
                    ("fx_rate_overridden", "BOOLEAN DEFAULT FALSE"),
                    ("fx_override_reason", "TEXT"),
                    ("fx_original_rate", "NUMERIC(15, 6)"),
                ]
                for col, col_type in migration_columns:
                    try:
                        await conn.execute(text(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                    except Exception:
                        pass

                try:
                    await conn.execute(text("ALTER TABLE integrations ALTER COLUMN id TYPE VARCHAR(255);"))
                except Exception:
                    pass

                invitation_columns = [
                    ("email_delivery_status", "VARCHAR(50) DEFAULT 'PENDING'"),
                    ("otp_hash", "VARCHAR(255)"),
                    ("otp_expires_at", "TIMESTAMP WITH TIME ZONE"),
                    ("otp_attempts", "INTEGER DEFAULT 0"),
                    ("otp_last_sent_at", "TIMESTAMP WITH TIME ZONE"),
                    ("otp_verified_at", "TIMESTAMP WITH TIME ZONE"),
                    ("locked_at", "TIMESTAMP WITH TIME ZONE"),
                ]
                for col, col_type in invitation_columns:
                    try:
                        await conn.execute(text(f"ALTER TABLE user_invitations ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                    except Exception:
                        pass
                try:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;"))
                except Exception:
                    pass
                try:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);"))
                except Exception:
                    pass

                try:
                    await conn.execute(text("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;"))
                except Exception:
                    pass
                try:
                    await conn.execute(text("ALTER TABLE zoho_connections ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;"))
                    await conn.execute(text("ALTER TABLE zoho_connections DROP CONSTRAINT IF EXISTS zoho_connections_tenant_id_key;"))
                    await conn.execute(text("DROP INDEX IF EXISTS ix_zoho_connections_tenant_id;"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_zoho_connections_tenant_id ON zoho_connections(tenant_id);"))
                except Exception:
                    pass
                try:
                    await conn.execute(text("ALTER TABLE email_connections ADD COLUMN IF NOT EXISTS user_id_str VARCHAR(100);"))
                except Exception:
                    pass
                # Incremental polling state columns (idempotent — safe on existing deployments)
                try:
                    await conn.execute(text("ALTER TABLE email_connections ADD COLUMN IF NOT EXISTS last_successful_poll_at TIMESTAMP WITH TIME ZONE;"))
                except Exception:
                    pass
                try:
                    await conn.execute(text("ALTER TABLE email_connections ADD COLUMN IF NOT EXISTS automatic_polling_enabled BOOLEAN NOT NULL DEFAULT FALSE;"))
                except Exception:
                    pass
                try:
                    await conn.execute(text("ALTER TABLE email_connections ADD COLUMN IF NOT EXISTS is_polling BOOLEAN NOT NULL DEFAULT FALSE;"))
                except Exception:
                    pass

            # Admin Bootstrap Check & worknaruto10@gmail.com Admin enforcement
            try:
                from app.db.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select
                    from app.db.models import User
                    
                    naruto_res = await session.execute(select(User).where(User.email == "worknaruto10@gmail.com"))
                    naruto_user = naruto_res.scalar_one_or_none()
                    if naruto_user:
                        if naruto_user.role != "ADMIN" or not naruto_user.is_active:
                            naruto_user.role = "ADMIN"
                            naruto_user.is_active = True
                            await session.commit()
                            logger.info("[ADMIN BOOTSTRAP] Enforced role=ADMIN for worknaruto10@gmail.com")
                    else:
                        admin_res = await session.execute(select(User).where(User.role == "ADMIN", User.is_active == True))
                        existing_admin = admin_res.scalar_one_or_none()
                        if not existing_admin:
                            first_user_res = await session.execute(select(User).order_by(User.created_at.asc()))
                            first_user = first_user_res.scalar_one_or_none()
                            if first_user:
                                first_user.role = "ADMIN"
                                await session.commit()
                                logger.info(f"[ADMIN BOOTSTRAP] Promoted existing account '{first_user.email}' to ADMIN.")
            except Exception as admin_boot_err:
                logger.warning(f"Admin bootstrap warning: {admin_boot_err}")

            logger.info("Database tables and columns initialized / verified successfully.")
        except Exception as exc:
            logger.warning(f"Database table verification error: {exc}")

    try:
        await asyncio.wait_for(init_db(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Database initialization timed out during startup; continuing server startup in background...")
        asyncio.create_task(init_db())
    except Exception as exc:
        logger.warning(f"Startup DB task error: {exc}")

    # Start the daily 7AM automatic email polling scheduler
    try:
        start_scheduler()
    except Exception as sched_exc:
        logger.warning(f"Email scheduler failed to start: {sched_exc}")

    yield

    # Graceful shutdown
    stop_scheduler()
    logger.info(f"Shutting down {settings.PROJECT_NAME} backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?/?$|https://.*\.github\.dev|https://.*\.devtunnels\.ms",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routes
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(invoices_router, prefix=settings.API_V1_STR)
app.include_router(settings_router, prefix=settings.API_V1_STR)
app.include_router(inbox_router, prefix=settings.API_V1_STR)
app.include_router(zoho_router, prefix=settings.API_V1_STR)
app.include_router(forex_router, prefix=settings.API_V1_STR)
app.include_router(hitl_router, prefix=settings.API_V1_STR)
app.include_router(review_router, prefix=settings.API_V1_STR)


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health",
    }


@app.get("/health")
async def health_root():
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "detail_health": f"{settings.API_V1_STR}/health",
    }


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", settings.PORT))
    host = os.getenv("HOST", settings.HOST)
    logger.info(f"Binding and starting server on {host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
    )
