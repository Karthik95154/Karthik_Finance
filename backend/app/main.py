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
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME} backend...")
    try:
        from app.db.database import engine, Base
        import app.db.models
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            # Ensure newly added columns exist on invoices table
            migration_columns = [
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
            ]
            for col, col_type in migration_columns:
                try:
                    await conn.execute(text(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                except Exception:
                    pass
        logger.info("Database tables and columns initialized / verified successfully.")
    except Exception as exc:
        logger.warning(f"Database table verification error: {exc}")
    yield
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
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.github\.dev|https://.*\.devtunnels\.ms",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routes
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(invoices_router, prefix=settings.API_V1_STR)
app.include_router(settings_router, prefix=settings.API_V1_STR)
app.include_router(inbox_router, prefix=settings.API_V1_STR)
app.include_router(zoho_router, prefix=settings.API_V1_STR)
app.include_router(hitl_router, prefix=settings.API_V1_STR)
app.include_router(review_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
