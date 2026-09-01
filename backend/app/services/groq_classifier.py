import json
import logging
from enum import Enum
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

class FinancialRelevance(str, Enum):
    FINANCIAL = "FINANCIAL"
    NOT_FINANCIAL = "NOT_FINANCIAL"
    UNKNOWN = "UNKNOWN"

class DocumentType(str, Enum):
    INVOICE = "INVOICE"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"
    TECHNICAL_DOCUMENT = "TECHNICAL_DOCUMENT"
    GENERAL_DOCUMENT = "GENERAL_DOCUMENT"
    UNKNOWN = "UNKNOWN"

class DocumentClassificationResult(BaseModel):
    financial_relevance: FinancialRelevance
    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

def get_unknown_fallback(reason: str) -> DocumentClassificationResult:
    return DocumentClassificationResult(
        financial_relevance=FinancialRelevance.UNKNOWN,
        document_type=DocumentType.UNKNOWN,
        confidence=0.0,
        reason=reason
    )

def classify_document(context: Dict[str, Any]) -> DocumentClassificationResult:
    """
    Classifies a document based ONLY on its visual image content using Groq Vision API (qwen/qwen3.8-27b).
    Does NOT use email subject, body, or filenames.
    
    STRICT RULE:
    Only INVOICE, CREDIT_NOTE, and DEBIT_NOTE qualify as FINANCIAL relevance for Sakshi Finance.
    All other documents (Purchase Orders, Receipts, Bank Statements, TDS Certificates, GRNs, Quotations, Resumes, Greeting Cards)
    MUST be classified with financial_relevance = NOT_FINANCIAL.
    """
    image_urls: List[str] = context.get("image_urls") or []

    if not image_urls:
        return get_unknown_fallback("No document image pages rendered for visual classification.")

    api_key = getattr(settings, "GROQ_API_KEY", None)
    model = getattr(settings, "GROQ_MODEL", "qwen/qwen3.8-27b")

    if not api_key:
        logger.warning("GROQ_API_KEY is not configured.")
        return get_unknown_fallback("Classification skipped: GROQ_API_KEY is not configured.")

    try:
        import groq
        client = groq.Groq(api_key=api_key)
    except ImportError:
        logger.error("groq package is not installed.")
        return get_unknown_fallback("Classification skipped: groq package not installed.")
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return get_unknown_fallback(f"Classification skipped: Groq client initialization failed. {e}")

    system_prompt = (
        "You are an expert visual document classifier for Sakshi Finance. "
        "You must classify the document ONLY based on its actual visual document image content provided below. "
        "Do NOT infer the document type from filenames, email subjects, or external metadata. "
        "CRITICAL CLASSIFICATION RULE FOR SAKSHI FINANCE:\n"
        "Sakshi Finance ONLY accepts the following THREE document types into its Finance Inbox:\n"
        "1. INVOICE / Tax Invoice / Retail Bill (set financial_relevance = FINANCIAL and document_type = INVOICE)\n"
        "2. CREDIT_NOTE (set financial_relevance = FINANCIAL and document_type = CREDIT_NOTE)\n"
        "3. DEBIT_NOTE (set financial_relevance = FINANCIAL and document_type = DEBIT_NOTE)\n\n"
        "ALL OTHER DOCUMENTS MUST BE CLASSIFIED WITH financial_relevance = NOT_FINANCIAL.\n"
        "This includes:\n"
        "- Purchase Orders\n"
        "- Receipts / Payment Receipts\n"
        "- Bank Statements\n"
        "- Expense Documents / Vouchers\n"
        "- TDS Certificates\n"
        "- Goods Receipt Notes (GRNs)\n"
        "- Delivery Challans\n"
        "- Quotations / Proforma Invoices\n"
        "- Resumes, Greeting Cards, Posters, Diagrams, Software Screenshots\n"
        "For all non-invoice/non-credit-note/non-debit-note items, set financial_relevance = NOT_FINANCIAL and document_type = GENERAL_DOCUMENT (or TECHNICAL_DOCUMENT for technical code/plans).\n\n"
        "If the document image is unreadable or completely blank, set financial_relevance = UNKNOWN and document_type = UNKNOWN.\n\n"
        "Respond ONLY with a JSON object conforming to the following structure:\n"
        "{\n"
        '  "financial_relevance": "FINANCIAL | NOT_FINANCIAL | UNKNOWN",\n'
        '  "document_type": "INVOICE | CREDIT_NOTE | DEBIT_NOTE | TECHNICAL_DOCUMENT | GENERAL_DOCUMENT | UNKNOWN",\n'
        '  "confidence": 0.95,\n'
        '  "reason": "Brief explanation based strictly on visible document image details"\n'
        "}"
    )

    # Build user message content array with text prompt and vision image_url objects
    user_content: List[Dict[str, Any]] = [
        {"type": "text", "text": "Classify this document based ONLY on its visual image content."}
    ]

    for img_url in image_urls:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": img_url}
        })

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model=model,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        content = chat_completion.choices[0].message.content
        if not content:
            return get_unknown_fallback("Groq Vision API returned empty content.")
            
        data = json.loads(content)
        # Validate against Pydantic model
        result = DocumentClassificationResult(**data)
        return result
        
    except Exception as e:
        logger.error(f"Groq Vision API call or validation failed: {e}")
        return get_unknown_fallback(f"Classification failed: {e}")
