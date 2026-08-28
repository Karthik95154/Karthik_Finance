import os
from typing import List
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

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]

    # Supabase Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"

    # Supabase Storage
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY: str = "placeholder-key"
    SUPABASE_STORAGE_BUCKET: str = "finance-invoices"

    # Colab Inference Endpoints
    COLAB_API_URL: str = "https://physiognomically-sane-dexter.ngrok-free.dev"
    COLAB_ACCOUNTING_API_URL: str = "https://parcel-curtsy-retiring.ngrok-free.dev"
    INFERENCE_TIMEOUT: float = 900.0  # seconds (15 minutes)

    # File Constraints
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
    ]


settings = Settings()
