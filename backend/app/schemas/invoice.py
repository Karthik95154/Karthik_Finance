from datetime import datetime, date
from decimal import Decimal
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


class PeriodDecisionRequest(BaseModel):
    decision: str  # CONTINUE or CANCEL


class ClassificationOverrideRequest(BaseModel):
    classification: str  # INDIAN, FOREIGN_SERVICE, REVIEW_REQUIRED, UNSUPPORTED_FOREIGN_GOODS
    reason: str


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
    period_category: Optional[str] = None
    period_decision: Optional[str] = "NOT_REQUIRED"
    period_message: Optional[str] = None
    invoice_date: Optional[str] = None
    updated_at: Optional[datetime] = None
    # Classification & Foreign Currency / FX fields
    invoice_origin: Optional[str] = "INDIAN"
    currency: Optional[str] = "INR"
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    classification_source: Optional[str] = "SYSTEM"
    classification_override: Optional[str] = None
    classification_override_reason: Optional[str] = None
    classified_by: Optional[str] = None
    classified_at: Optional[datetime] = None
    original_currency: Optional[str] = "INR"
    original_total_amount: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    exchange_rate_date: Optional[date] = None
    exchange_rate_source: Optional[str] = None
    converted_total_inr: Optional[Decimal] = None
    fx_rate_overridden: Optional[bool] = False


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[str] = "default-tenant-001"
    owner_user_id: Optional[UUID] = None
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    file_hash: str
    status: str
    accounting_status: Optional[str] = None
    approval_status: Optional[str] = "PENDING_REVIEW"
    export_status: Optional[str] = "NOT_EXPORTED"
    period_category: Optional[str] = None
    period_decision: Optional[str] = "NOT_REQUIRED"
    invoice_type: Optional[str] = "VENDOR_INVOICE"
    zoho_bill_id: Optional[str] = None
    zoho_bill_number: Optional[str] = None
    exported_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    accounting_confidence: Optional[float] = None
    posting_date: Optional[date] = None
    period_resolution: Optional[str] = "NONE"
    period_resolution_reason: Optional[str] = None
    period_resolved_by: Optional[str] = None
    period_resolved_at: Optional[datetime] = None
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
    invoice_origin: Optional[str] = "INDIAN"
    currency: Optional[str] = "INR"
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    classification_model: Optional[str] = None
    classification_source: Optional[str] = "SYSTEM"
    classification_override: Optional[str] = None
    classification_override_reason: Optional[str] = None
    classified_by: Optional[str] = None
    classified_at: Optional[datetime] = None
    
    # Foreign Currency & FX Fields (Step 1 Foundation)
    original_currency: Optional[str] = "INR"
    original_total_amount: Optional[Decimal] = None
    original_taxable_amount: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    exchange_rate_date: Optional[date] = None
    exchange_rate_source: Optional[str] = None
    converted_total_inr: Optional[Decimal] = None
    converted_taxable_inr: Optional[Decimal] = None
    fx_rate_overridden: Optional[bool] = False
    fx_override_reason: Optional[str] = None
    fx_original_rate: Optional[Decimal] = None

    created_at: datetime
    updated_at: datetime


class InvoiceUpdateRequest(BaseModel):
    current_vlm_output: Optional[Dict[str, Any]] = None
    current_accounting_output: Optional[Dict[str, Any]] = None
    gst_result: Optional[Dict[str, Any]] = None
    itc_result: Optional[Dict[str, Any]] = None
    financial_validation_result: Optional[Dict[str, Any]] = None
    journal_entry: Optional[Dict[str, Any]] = None
    
    # Optional classification overrides
    classification_override: Optional[str] = None
    classification_override_reason: Optional[str] = None

    # Optional FX overrides
    exchange_rate: Optional[Decimal] = None
    exchange_rate_date: Optional[date] = None
    exchange_rate_source: Optional[str] = None
    converted_total_inr: Optional[Decimal] = None
    converted_taxable_inr: Optional[Decimal] = None
    fx_rate_overridden: Optional[bool] = None
    fx_override_reason: Optional[str] = None
    fx_original_rate: Optional[Decimal] = None


class InvoiceListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[str] = "default-tenant-001"
    owner_user_id: Optional[UUID] = None
    file_name: str
    file_size: int
    mime_type: str
    status: str
    accounting_status: Optional[str] = None
    approval_status: Optional[str] = "PENDING_REVIEW"
    export_status: Optional[str] = "NOT_EXPORTED"
    financial_relevance: Optional[str] = None
    document_type: Optional[str] = None
    invoice_origin: Optional[str] = "INDIAN"
    currency: Optional[str] = "INR"
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    classification_source: Optional[str] = "SYSTEM"
    classification_override: Optional[str] = None
    classification_override_reason: Optional[str] = None
    zoho_bill_id: Optional[str] = None
    zoho_bill_number: Optional[str] = None
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    
    # Foreign Currency & FX Summary Fields
    original_currency: Optional[str] = "INR"
    original_total_amount: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    exchange_rate_date: Optional[date] = None
    converted_total_inr: Optional[Decimal] = None
    fx_rate_overridden: Optional[bool] = False

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
    colab_tds: Optional[str] = None
    services: Optional[Dict[str, ServiceHealthDetail]] = None
    timestamp: datetime
