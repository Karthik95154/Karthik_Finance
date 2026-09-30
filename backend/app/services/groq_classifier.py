import json
import logging
import re
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

class InvoiceOrigin(str, Enum):
    INDIAN = "INDIAN"
    FOREIGN = "FOREIGN"
    UNKNOWN = "UNKNOWN"

class DocumentClassificationResult(BaseModel):
    financial_relevance: FinancialRelevance
    document_type: DocumentType
    invoice_origin: InvoiceOrigin = Field(default=InvoiceOrigin.INDIAN)
    currency: str = Field(default="INR")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

def get_unknown_fallback(reason: str) -> DocumentClassificationResult:
    return DocumentClassificationResult(
        financial_relevance=FinancialRelevance.UNKNOWN,
        document_type=DocumentType.UNKNOWN,
        invoice_origin=InvoiceOrigin.INDIAN,
        currency="INR",
        confidence=0.0,
        reason=reason
    )


def refine_classification(result: DocumentClassificationResult, context: Dict[str, Any]) -> DocumentClassificationResult:
    """
    Applies deterministic heuristics to correct any VLM classification edge cases:
    - If vendor is an Indian domestic company with domestic state GSTIN (01-38) and billed in INR -> strictly INDIAN
    - If vendor has OIDAR / Non-Resident GSTIN (starting with 99), or foreign currency ($/€/£/SGD), or foreign address -> FOREIGN
    """
    doc_text = (context.get("doc_text") or "").strip()
    if not doc_text:
        return result

    text_lower = doc_text.lower()

    # Check for Indian domestic GSTIN (state codes 01 to 38, i.e., not 99)
    # e.g., 27AAGCG4576J1Z6 (Google Cloud India Pvt Ltd, Mumbai)
    domestic_gst_match = re.search(r"\b(0[1-9]|[1-2][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", doc_text)
    has_inr_currency = ("₹" in doc_text or "total in inr" in text_lower or "in inr" in text_lower or "inr " in text_lower or "rs." in text_lower or "rupees" in text_lower)
    has_indian_pvt_ltd = ("india pvt ltd" in text_lower or "india private limited" in text_lower or "private limited" in text_lower)

    # 1. Check for OIDAR GSTIN (starts with 99, e.g. 9922SGP29007OSQ)
    has_oidar_gst = bool(re.search(r"\b99\d{2}[A-Z]{3,5}\d{3,5}", doc_text, re.IGNORECASE)) or "9922sgp" in text_lower

    # 2. Check for foreign currency indicators
    has_usd = ("$" in doc_text or "usd" in text_lower or "total due:" in text_lower and "$" in doc_text) and not has_inr_currency
    has_eur = ("€" in doc_text or "eur" in text_lower) and not has_inr_currency
    has_gbp = ("£" in doc_text or "gbp" in text_lower) and not has_inr_currency
    has_sgd = ("sgd" in text_lower or "s$" in doc_text) and not has_inr_currency

    # 3. Check for foreign vendor entities / countries
    foreign_vendor_indicators = [
        "singapore", "pte ltd", "pte. ltd.", "anson road", "079914",
        "united states", "delaware", "california", "san francisco", "seattle", "austin",
        "ireland", "dublin", "united kingdom", "london", "sydney", "australia", "germany", "dubai",
        "hubspot asia", "google asia pacific", "amazon web services, inc", "stripe payments europe",
        "figma, inc", "github, inc", "zoom video communications"
    ]
    has_foreign_entity = any(kw in text_lower for kw in foreign_vendor_indicators)

    # If it is clearly an Indian domestic entity with domestic GSTIN and INR billing (like Google Cloud India Pvt Ltd)
    if (domestic_gst_match or has_indian_pvt_ltd) and has_inr_currency and not has_oidar_gst and not has_usd:
        result.invoice_origin = InvoiceOrigin.INDIAN
        result.currency = "INR"
        return result

    if has_usd or has_eur or has_gbp or has_sgd or has_oidar_gst or (has_foreign_entity and "$" in doc_text):
        detected_currency = "USD"
        if has_eur:
            detected_currency = "EUR"
        elif has_gbp:
            detected_currency = "GBP"
        elif has_sgd:
            detected_currency = "SGD"
        elif has_usd or "$" in doc_text:
            detected_currency = "USD"

        result.invoice_origin = InvoiceOrigin.FOREIGN
        result.currency = detected_currency
        if result.financial_relevance == FinancialRelevance.UNKNOWN:
            result.financial_relevance = FinancialRelevance.FINANCIAL
            result.document_type = DocumentType.INVOICE
        result.reason = f"Foreign invoice detected via international vendor entity / currency / OIDAR GST: {result.reason}"

    return result


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
        "This includes Purchase Orders, Receipts, Bank Statements, Expense Vouchers, TDS Certificates, GRNs, Delivery Challans, Quotations, Resumes, etc.\n\n"
        "ORIGIN & CURRENCY CLASSIFICATION (INDIAN vs FOREIGN):\n"
        "- CRITICAL RULE: Origin is determined SOLELY by the ISSUING SELLER/VENDOR (the company at the top sending the bill), NOT the buyer/customer (even if customer has an Indian address or Indian GSTIN).\n"
        "- FOREIGN INVOICE: Set invoice_origin = FOREIGN if ANY of the following are true:\n"
        "  * The issuing vendor is located outside India (e.g. Singapore, USA, Ireland, UK, Europe, Australia, Dubai - e.g. HubSpot Asia Pte Ltd, Google Asia Pacific, AWS Inc, Zoom, Meta, Stripe, GitHub, Figma, Adobe, OpenAI, Atlassian).\n"
        "  * The invoice is billed in a foreign currency like USD ($), EUR (€), GBP (£), SGD (S$), AED, AUD, CAD, etc. (set currency = USD/EUR/SGD/etc.).\n"
        "  * The vendor has an OIDAR / Non-Resident GSTIN starting with state code 99 (e.g. 9922SGP29007OSQ, 9917USA...).\n"
        "- INDIAN INVOICE: Set invoice_origin = INDIAN (currency = INR) ONLY when the ISSUING SELLER itself is an Indian domestic company located inside India, having domestic state GSTIN (state code 01-38, e.g. 29, 36, 27, 07) and billed in INR (₹ / Rs / INR).\n\n"
        "If the document image is unreadable or completely blank, set financial_relevance = UNKNOWN and document_type = UNKNOWN.\n\n"
        "Respond ONLY with a JSON object conforming to the following structure:\n"
        "{\n"
        '  "financial_relevance": "FINANCIAL | NOT_FINANCIAL | UNKNOWN",\n'
        '  "document_type": "INVOICE | CREDIT_NOTE | DEBIT_NOTE | TECHNICAL_DOCUMENT | GENERAL_DOCUMENT | UNKNOWN",\n'
        '  "invoice_origin": "INDIAN | FOREIGN",\n'
        '  "currency": "INR | USD | EUR | GBP | SGD | AED | etc.",\n'
        '  "confidence": 0.95,\n'
        '  "reason": "Brief explanation describing document type and whether it is Indian or Foreign with visible evidence (e.g. Singapore vendor HubSpot billed in USD vs Indian vendor in INR)"\n'
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
            temperature=0.0,
            max_tokens=300,
        )
        
        content = chat_completion.choices[0].message.content
        if not content:
            return get_unknown_fallback("Groq Vision API returned empty content.")
            
        data = json.loads(content)
        # Validate against Pydantic model
        result = DocumentClassificationResult(**data)
        # Refine with text/heuristic analysis
        return refine_classification(result, context)
        
    except Exception as e:
        logger.error(f"Groq Vision API call or validation failed: {e}")
        return refine_classification(get_unknown_fallback(f"Classification failed: {e}"), context)

