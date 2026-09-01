from datetime import datetime
from uuid import UUID
from typing import Optional, Any, Dict, List
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
    approval_status: Optional[str] = "PENDING_REVIEW"
    export_status: Optional[str] = "NOT_EXPORTED"
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    accounting_confidence: Optional[float] = None
    updated_at: datetime


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[str] = "default-tenant-001"
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    file_hash: str
    status: str
    accounting_status: Optional[str] = None
    approval_status: Optional[str] = "PENDING_REVIEW"
    export_status: Optional[str] = "NOT_EXPORTED"
    invoice_type: Optional[str] = "VENDOR_INVOICE"
    zoho_bill_id: Optional[str] = None
    zoho_bill_number: Optional[str] = None
    exported_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    accounting_confidence: Optional[float] = None
    raw_vlm_output: Optional[Dict[str, Any]] = None
    current_vlm_output: Optional[Dict[str, Any]] = None
    accounting_output: Optional[Dict[str, Any]] = None
    current_accounting_output: Optional[Dict[str, Any]] = None
    gst_result: Optional[Dict[str, Any]] = None
    itc_result: Optional[Dict[str, Any]] = None
    financial_validation_result: Optional[Dict[str, Any]] = None
    journal_entry: Optional[Dict[str, Any]] = None
    financial_relevance: Optional[str] = None
    document_type: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    classification_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InvoiceUpdateRequest(BaseModel):
    current_vlm_output: Optional[Dict[str, Any]] = None
    current_accounting_output: Optional[Dict[str, Any]] = None
    gst_result: Optional[Dict[str, Any]] = None
    itc_result: Optional[Dict[str, Any]] = None
    financial_validation_result: Optional[Dict[str, Any]] = None
    journal_entry: Optional[Dict[str, Any]] = None


class InvoiceListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[str] = "default-tenant-001"
    file_name: str
    file_size: int
    mime_type: str
    status: str
    accounting_status: Optional[str] = None
    approval_status: Optional[str] = "PENDING_REVIEW"
    export_status: Optional[str] = "NOT_EXPORTED"
    financial_relevance: Optional[str] = None
    document_type: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    classification_model: Optional[str] = None
    zoho_bill_id: Optional[str] = None
    zoho_bill_number: Optional[str] = None
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class ServiceHealthDetail(BaseModel):
    name: str
    status: str  # "online" | "404_error" | "offline" | "connected" | "disconnected" | "degraded" | "error" | "timeout"
    status_code: Optional[int] = None
    message: str
    latency_ms: Optional[float] = None
    endpoint: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    project: str
    database: str
    storage: str
    colab_vlm: Optional[str] = None
    colab_accounting: Optional[str] = None
    services: Optional[Dict[str, ServiceHealthDetail]] = None
    timestamp: datetime
