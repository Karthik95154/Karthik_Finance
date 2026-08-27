from datetime import datetime
from uuid import UUID
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class InvoiceUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID
    file_name: str
    file_size: int
    mime_type: str
    file_hash: str
    status: str
    created_at: datetime


class InvoiceStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID
    status: str
    accounting_status: Optional[str] = None
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    accounting_confidence: Optional[float] = None
    updated_at: datetime


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    file_hash: str
    status: str
    accounting_status: Optional[str] = None
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    accounting_confidence: Optional[float] = None
    raw_vlm_output: Optional[Dict[str, Any]] = None
    current_vlm_output: Optional[Dict[str, Any]] = None
    accounting_output: Optional[Dict[str, Any]] = None
    current_accounting_output: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class InvoiceUpdateRequest(BaseModel):
    current_vlm_output: Optional[Dict[str, Any]] = None
    current_accounting_output: Optional[Dict[str, Any]] = None


class InvoiceListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_size: int
    mime_type: str
    status: str
    accounting_status: Optional[str] = None
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    project: str
    database: str
    storage: str
    colab_vlm: Optional[str] = None
    colab_accounting: Optional[str] = None
    timestamp: datetime
