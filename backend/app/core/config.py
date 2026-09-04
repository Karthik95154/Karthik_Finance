import os
from typing import Any, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "Finance Web Application"
    API_V1_STR: str = "/api/v1"
    ENCRYPTION_KEY: str = ""

    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
    ]
    FRONTEND_URL: str = "http://localhost:3002"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            val = v.strip()
            # If wrapped in quotes, strip them
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1].strip()
            if val.startswith("[") and val.endswith("]"):
                import json
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    # Fallback: strip brackets and split by comma
                    val = val[1:-1]
            # Split comma-separated values and clean extra quotes
            items = []
            for item in val.split(","):
                cleaned = item.strip().strip("'\"").strip()
                if cleaned:
                    items.append(cleaned)
            return items
        elif isinstance(v, (list, tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]
        return v

    # Supabase Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip()
            if val.startswith("postgresql+psycopg2://"):
                val = val.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
            elif val.startswith("postgresql://"):
                val = val.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif val.startswith("postgres://"):
                val = val.replace("postgres://", "postgresql+asyncpg://", 1)

            # Supabase pooler: port 5432 is session mode (strictly capped at 15 clients).
            # Switch to port 6543 (transaction pooler) which safely supports thousands of concurrent connections.
            if "pooler.supabase.com:5432" in val:
                val = val.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543", 1)

            return val
        return v

    # Supabase Storage
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY: str = "placeholder-key"
    SUPABASE_STORAGE_BUCKET: str = "finance-invoices"

    # Environment
    ENVIRONMENT: str = "development"

    # Multi-Tenancy & Security
    DEFAULT_TENANT_ID: str = "default-tenant-001"
    TOKEN_ENCRYPTION_KEY: str = ""
    AUTH_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    AUTH_TOKEN_EXPIRE_MINUTES: int = 1440
    ENABLE_DEV_AUTH: bool = True

    def model_post_init(self, __context) -> None:
        if self.FRONTEND_URL:
            clean_fe = self.FRONTEND_URL.rstrip("/")
            if clean_fe not in self.CORS_ORIGINS:
                self.CORS_ORIGINS.append(clean_fe)

        if self.ENVIRONMENT in ("production", "staging"):
            if not self.AUTH_SECRET_KEY:
                raise ValueError(f"CRITICAL SECURITY ERROR: 'AUTH_SECRET_KEY' environment variable must be set in {self.ENVIRONMENT} mode.")
            if not self.TOKEN_ENCRYPTION_KEY:
                raise ValueError(f"CRITICAL SECURITY ERROR: 'TOKEN_ENCRYPTION_KEY' environment variable must be set in {self.ENVIRONMENT} mode.")
            if self.ENVIRONMENT == "production":
                self.ENABLE_DEV_AUTH = False
        else:
            # Safe local fallback for development/testing if not specified in .env
            if not self.AUTH_SECRET_KEY:
                self.AUTH_SECRET_KEY = "sakshi-dev-jwt-secret-local-only-not-for-production"
            if not self.TOKEN_ENCRYPTION_KEY:
                self.TOKEN_ENCRYPTION_KEY = "sakshi-dev-token-encryption-key-32b-local"

    # Zoho Books Integration
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REDIRECT_URI: str = "http://localhost:8000/api/v1/zoho/callback"
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.in"
    ZOHO_BOOKS_API_BASE_URL: str = "https://www.zohoapis.in/books/v3"

    # Colab / AI Inference Endpoints
    # Primary variables with backward-compatible fallbacks
    QWEN_VL_SERVICE_URL: str = ""
    QWEN_COA_SERVICE_URL: str = ""
    QWEN_TDS_SERVICE_URL: str = ""

    # Legacy variables
    COLAB_API_URL: str = "https://physiognomically-sane-dexter.ngrok-free.dev"
    COLAB_ACCOUNTING_API_URL: str = "https://parcel-curtsy-retiring.ngrok-free.dev"
    COLAB_TDS_API_URL: str = ""
    INFERENCE_TIMEOUT: float = 900.0  # seconds (15 minutes)

    # Groq AI Financial Document Classifier
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    @property
    def vl_service_url(self) -> str:
        url = self.QWEN_VL_SERVICE_URL or self.COLAB_API_URL or ""
        return url.strip().rstrip("/")

    @property
    def coa_service_url(self) -> str:
        url = self.QWEN_COA_SERVICE_URL or self.COLAB_ACCOUNTING_API_URL or ""
        return url.strip().rstrip("/")

    @property
    def tds_service_url(self) -> str:
        url = self.QWEN_TDS_SERVICE_URL or self.COLAB_TDS_API_URL or ""
        return url.strip().rstrip("/")

    # File Constraints
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
    ]


settings = Settings()
