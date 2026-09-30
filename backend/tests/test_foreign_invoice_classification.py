import uuid
from decimal import Decimal
import pytest
from app.services.invoice_classifier import (
    InvoiceClassifier,
    InvoiceClassification,
    ClassificationResult,
    invoice_classifier,
)
from app.services.model_response_adapter import ModelResponseAdapter


def test_case_1_indian_vendor_inr_invoice():
    """
    CASE 1: Indian vendor + INR invoice -> INDIAN
    """
    data = {
        "vendor_name": "Infosys Limited",
        "vendor_country": "India",
        "vendor_address": "Electronics City, Hosur Road, Bengaluru, Karnataka 560100",
        "vendor_gstin": "29AABCI1234F1Z5",
        "vendor_pan": "AABCI1234F",
        "currency": "INR",
        "total_amount": 150000.00,
        "line_items": [
            {"description": "IT Consulting Services", "hsn_sac": "998311", "line_amount": 150000.00}
        ],
    }
    result = invoice_classifier.classify(data)
    assert result.classification == InvoiceClassification.INDIAN
    assert result.confidence >= 0.90
    assert "INDIAN" in result.reason.upper() or "DOMESTIC" in result.reason.upper()


def test_case_2_indian_vendor_usd_invoice_not_foreign_service():
    """
    CASE 2: Indian vendor + USD invoice -> must NOT automatically become FOREIGN_SERVICE
    Currency alone must never dictate foreign service status.
    """
    data = {
        "vendor_name": "Tata Consultancy Services Limited",
        "vendor_country": "India",
        "vendor_address": "TCS House, Raveline Street, Fort, Mumbai, Maharashtra 400001",
        "vendor_gstin": "27AAACT2727Q1ZW",
        "vendor_pan": "AAACT2727Q",
        "currency": "USD",
        "total_amount": 5000.00,
        "line_items": [
            {"description": "Software Development Export Services", "hsn_sac": "998314", "line_amount": 5000.00}
        ],
    }
    result = invoice_classifier.classify(data)
    # Must NOT be FOREIGN_SERVICE
    assert result.classification != InvoiceClassification.FOREIGN_SERVICE
    assert result.classification == InvoiceClassification.INDIAN
    assert result.currency == "USD"
    assert "foreign currency (USD)" in result.reason or "INDIAN" in result.reason.upper()


def test_case_3_foreign_vendor_usd_service_invoice():
    """
    CASE 3: Foreign vendor + USD service invoice -> FOREIGN_SERVICE
    """
    data = {
        "vendor_name": "Amazon Web Services, Inc.",
        "vendor_country": "United States",
        "vendor_address": "410 Terry Avenue North, Seattle, WA 98109-5210, USA",
        "vendor_tax_id": "91-1234567",
        "currency": "USD",
        "total_amount": 6400.00,
        "service_description": "Cloud Hosting and EC2 Compute Infrastructure",
        "line_items": [
            {"description": "AWS Cloud Compute Usage - September 2026", "line_amount": 6400.00}
        ],
        "bank_details": {
            "swift_bic": "CHASUS33XXX",
            "bank_name": "JPMorgan Chase Bank, N.A.",
        },
    }
    result = invoice_classifier.classify(data)
    assert result.classification == InvoiceClassification.FOREIGN_SERVICE
    assert result.confidence >= 0.90
    assert result.currency == "USD"
    assert "Foreign service invoice verified" in result.reason


def test_case_4_foreign_vendor_eur_service_invoice():
    """
    CASE 4: Foreign vendor + EUR service invoice -> FOREIGN_SERVICE
    """
    data = {
        "vendor_name": "Stripe Payments Europe, Limited",
        "vendor_country": "Ireland",
        "vendor_address": "The One Building, 1 Lower Grand Canal Street, Dublin 2, Ireland",
        "vendor_tax_id": "IE3206488LH",
        "currency": "EUR",
        "total_amount": 2500.00,
        "service_description": "Payment gateway processing fee and subscription",
        "line_items": [
            {"description": "SaaS Platform Monthly Subscription", "line_amount": 2500.00}
        ],
        "bank_details": {
            "iban": "IE29AIBK93115212345678",
            "swift_bic": "AIBKIE2D",
        },
    }
    result = invoice_classifier.classify(data)
    assert result.classification == InvoiceClassification.FOREIGN_SERVICE
    assert result.currency == "EUR"
    assert "Foreign service invoice verified" in result.reason


def test_case_5_foreign_vendor_service_description():
    """
    CASE 5: Foreign vendor + service description -> FOREIGN_SERVICE
    """
    data = {
        "vendor_name": "HubSpot Asia Pte. Ltd.",
        "vendor_country": "Singapore",
        "vendor_address": "Mapletree Anson, 60 Anson Road, Singapore 079914",
        "vendor_gstin": "9922SGP29007OSQ",  # OIDAR Non-Resident GSTIN
        "vendor_tax_id": "201424344E",
        "currency": "USD",
        "total_amount": 1200.00,
        "line_items": [
            {"description": "Marketing Hub Professional Annual Subscription (SAC 9983)", "line_amount": 1200.00}
        ],
    }
    result = invoice_classifier.classify(data)
    assert result.classification == InvoiceClassification.FOREIGN_SERVICE
    assert result.evidence.gstin_type == "OIDAR_99"


def test_case_6_foreign_goods_invoice_unsupported():
    """
    CASE 6: Foreign goods invoice -> UNSUPPORTED_FOREIGN_GOODS
    Physical goods imports must not enter the foreign service accounting pipeline.
    """
    data = {
        "vendor_name": "Shenzhen Electronics Manufacturing Corp.",
        "vendor_country": "China",
        "vendor_address": "Baoan District, Shenzhen, Guangdong, China",
        "currency": "USD",
        "total_amount": 45000.00,
        "line_items": [
            {
                "description": "Industrial PCB Hardware Units (HS Code 8534)",
                "hsn_code": "85340000",
                "quantity": 500,
                "unit_price": 90.00,
                "line_amount": 45000.00,
            }
        ],
    }
    raw_text = "BILL OF LADING: COSU61829384 PORT OF LOADING: SHANGHAI PORT OF DISCHARGE: NHAVA SHEVA FOB TERMS GROSS WEIGHT 1200 KG"
    result = invoice_classifier.classify(data, raw_document_text=raw_text)
    assert result.classification == InvoiceClassification.UNSUPPORTED_FOREIGN_GOODS
    assert "physical goods" in result.reason.lower() or "unsupported" in result.reason.lower()


def test_case_7_unknown_vendor_country():
    """
    CASE 7: Unknown vendor country -> REVIEW_REQUIRED
    When vendor location and corporate identity are missing, never guess.
    """
    data = {
        "vendor_name": "Apex Global Solutions",
        "vendor_country": None,
        "vendor_address": None,
        "vendor_gstin": None,
        "vendor_pan": None,
        "vendor_tax_id": None,
        "currency": "USD",
        "total_amount": 800.00,
        "line_items": [
            {"description": "Monthly Consulting", "line_amount": 800.00}
        ],
    }
    result = invoice_classifier.classify(data)
    assert result.classification == InvoiceClassification.REVIEW_REQUIRED
    assert "review required" in result.reason.lower() or "missing" in result.reason.lower() or "unavailable" in result.reason.lower()


def test_case_8_conflicting_evidence():
    """
    CASE 8: Conflicting evidence -> REVIEW_REQUIRED
    Example: Domestic Indian GSTIN but address/country explicitly states USA without branch entity context.
    """
    data = {
        "vendor_name": "Acme International LLC",
        "vendor_country": "United States",
        "vendor_address": "123 Market St, San Francisco, CA, USA",
        "vendor_gstin": "27AABCA1234F1Z5",  # Maharashtra domestic GSTIN
        "vendor_tax_id": "12-3456789",     # US EIN
        "currency": "USD",
        "total_amount": 1000.00,
        "line_items": [
            {"description": "Consulting Services", "line_amount": 1000.00}
        ],
    }
    result = invoice_classifier.classify(data)
    assert result.classification == InvoiceClassification.REVIEW_REQUIRED
    assert "conflicting" in result.reason.lower() or "contradiction" in result.reason.lower()


def test_case_9_manual_upload_and_email_use_same_classifier():
    """
    CASE 9: Manual upload and email use the same classifier
    Both entry paths normalize data via ModelResponseAdapter and execute invoice_classifier.classify.
    """
    sample_model_response = {
        "vendor_details": {
            "vendor_name": "Figma, Inc.",
            "vendor_country": "United States",
            "vendor_address": "767 Sansome Street, San Francisco, CA 94111",
            "vendor_tax_id": "45-2345678",
        },
        "invoice_details": {
            "invoice_number": "INV-FIGMA-9921",
            "invoice_date": "2026-09-15",
            "currency": "USD",
            "service_description": "Figma Enterprise Design SaaS Subscription",
        },
        "financial_details": {
            "subtotal": 3600.00,
            "total_amount": 3600.00,
        },
        "line_items": [
            {"description": "Figma Enterprise Tier Annual Subscription", "line_amount": 3600.00, "taxable_amount": 3600.00}
        ],
    }
    
    # 1. Normalize
    normalized = ModelResponseAdapter.normalize_model_response(sample_model_response)
    norm_data = normalized["normalized_data"]
    
    # Verify foreign extraction attributes captured
    assert norm_data["vendor_name"] == "Figma, Inc."
    assert norm_data["vendor_country"] == "United States"
    assert norm_data["vendor_tax_id"] == "45-2345678"
    assert norm_data["currency"] == "USD"
    assert norm_data["total_amount"] == 3600.00
    
    # 2. Run classifier
    classification = invoice_classifier.classify(norm_data)
    assert classification.classification == InvoiceClassification.FOREIGN_SERVICE
    assert classification.currency == "USD"


def test_case_10_finance_classification_override_preserves_audit():
    """
    CASE 10: Finance classification override preserves system classification and reason
    """
    system_result = ClassificationResult(
        classification=InvoiceClassification.REVIEW_REQUIRED,
        confidence=0.50,
        reason="Vendor country was missing in initial extraction.",
        currency="USD",
    )
    
    overridden = invoice_classifier.apply_classification_override(
        system_result=system_result,
        override_classification=InvoiceClassification.FOREIGN_SERVICE,
        override_reason="Finance confirmed vendor is US Delaware entity providing SaaS hosting.",
        user_id="finance_lead@sakshi.com",
    )
    
    # System classification is strictly preserved
    assert overridden.classification == InvoiceClassification.REVIEW_REQUIRED
    assert overridden.reason == "Vendor country was missing in initial extraction."
    
    # Override fields are captured
    assert overridden.classification_override == InvoiceClassification.FOREIGN_SERVICE
    assert overridden.classification_override_reason == "Finance confirmed vendor is US Delaware entity providing SaaS hosting."
    assert overridden.classified_by == "finance_lead@sakshi.com"
    assert overridden.classified_at is not None


def test_case_11_override_requires_reason():
    """
    Validates that classification override strictly requires an explicit reason.
    """
    system_result = ClassificationResult(
        classification=InvoiceClassification.FOREIGN_SERVICE,
        confidence=0.95,
        reason="Foreign vendor verified.",
        currency="USD",
    )
    with pytest.raises(ValueError, match="reason is required"):
        invoice_classifier.apply_classification_override(
            system_result=system_result,
            override_classification=InvoiceClassification.INDIAN,
            override_reason="",
        )
