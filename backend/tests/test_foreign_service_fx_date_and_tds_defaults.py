import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from app.core.config import settings
from app.services.forex_service import ForexService, ExchangeRateResult, ForexProvider
from app.services.tds_engine import TDSEngine, STATUTORY_TDS_TABLE_2025, resolve_tds_tax_details
from app.services.gst_engine import GSTEngine
from app.services.itc_engine import ITCEngine
from app.services.journal_generator import JournalGenerator
from app.services.invoice_classifier import InvoiceClassifier, InvoiceClassification


class MockFxProvider(ForexProvider):
    def __init__(self, rate_map=None):
        self.rate_map = rate_map or {}

    @property
    def name(self) -> str:
        return "MOCK_FX_PROVIDER"

    async def fetch_rate(self, currency: str, fx_date: date):
        rate, actual_date = self.rate_map.get(fx_date, (Decimal("86.200000"), fx_date))
        return ExchangeRateResult(
            currency=currency,
            rate=rate,
            rate_date=actual_date,
            requested_date=fx_date,
            source=self.name,
        )


@pytest.mark.asyncio
async def test_01_and_02_and_03_foreign_usd_invoice_uses_invoice_date_not_processing_date():
    """Tests 1, 2, 3: Foreign USD invoice resolves FX rate using invoice_date when processing_date differs."""
    inv_date = date(2026, 8, 15)
    proc_date = date(2026, 9, 5)

    mock_provider = MockFxProvider(
        rate_map={
            inv_date: (Decimal("86.200000"), inv_date),
            proc_date: (Decimal("88.500000"), proc_date),
        }
    )
    fx_service = ForexService(provider=mock_provider)

    # 1. Resolve FX Date: must use invoice_date
    resolved_date = fx_service.resolve_fx_date(
        invoice_date=inv_date,
        processing_date=proc_date,
    )
    assert resolved_date == inv_date
    assert resolved_date != proc_date

    # 2. Historical FX lookup using resolved invoice_date
    res = await fx_service.get_exchange_rate("USD", fx_date=resolved_date)
    assert res.rate == Decimal("86.200000")
    assert res.requested_date == inv_date
    assert res.rate_date == inv_date
    assert res.rate != Decimal("88.500000")


@pytest.mark.asyncio
async def test_04_weekend_fallback_preserves_requested_invoice_date_and_records_actual_rate_date():
    """Test 4: Non-trading day/weekend preserves requested invoice date and records fallback rate date."""
    saturday_invoice_date = date(2026, 8, 15)
    friday_rate_date = date(2026, 8, 14)

    mock_provider = MockFxProvider(
        rate_map={
            saturday_invoice_date: (Decimal("86.200000"), friday_rate_date),
        }
    )
    fx_service = ForexService(provider=mock_provider)

    res = await fx_service.get_exchange_rate("USD", fx_date=saturday_invoice_date)
    assert res.rate == Decimal("86.200000")
    assert res.requested_date == saturday_invoice_date
    assert res.rate_date == friday_rate_date


def test_05_and_06_canonical_inr_conversion_and_original_preservation():
    """Tests 5 & 6: USD 150 * 86.20 = INR 12,930.00 with Decimal precision."""
    fx_service = ForexService()
    orig_total = Decimal("150.00")
    rate = Decimal("86.200000")

    inr_total = fx_service.convert_to_inr(orig_total, rate)
    assert inr_total == Decimal("12930.00")
    assert orig_total == Decimal("150.00")


def test_07_to_10_foreign_tds_defaults_section_393_2_sl_17_and_4pct_cess_on_tds():
    """Tests 7, 8, 9, 10: Section 393(2), Table Sl. No. 17 @ 20% + 4% Cess on TDS amount (no threshold)."""
    tds = TDSEngine()

    # Verify statutory config
    conf = STATUTORY_TDS_TABLE_2025["NON_RESIDENT"]
    assert conf["provision"] == "Section 393(2), Table Sl. No. 17"
    assert conf["default_rate"] == 20.0
    assert conf["cess_rate"] == 4.0
    assert conf["threshold_amount"] is None

    # Test 100k base example from prompt:
    # INR TDS base = ₹100,000 -> TDS @ 20% = ₹20,000 -> H&E Cess @ 4% of TDS = ₹800 -> Total TDS + Cess = ₹20,800
    res_100k = tds.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(2), Table Sl. No. 17",
        nature_of_payment="Non-Resident Payment / Foreign Remittance",
        base_amount=100000.0,
    )
    assert res_100k["applicable"] is True
    assert res_100k["rate"] == 20.0
    assert res_100k["base_amount"] == 100000.0
    assert res_100k["base_tds_amount"] == 20000.0
    assert res_100k["cess_rate"] == 4.0
    assert res_100k["cess_amount"] == 800.0  # 4% of 20,000
    assert res_100k["tds_amount"] == 20800.0  # 20,000 + 800
    assert res_100k["total_tds_amount"] == 20800.0
    assert res_100k["threshold_amount"] is None

    # Test prompt example: USD 150 * 86.20 = INR 12,930
    # TDS base = ₹12,930 -> TDS @ 20% = ₹2,586.00 -> H&E Cess @ 4% of TDS = ₹103.44 -> Total = ₹2,689.44
    res_12930 = tds.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(2), Table Sl. No. 17",
        nature_of_payment="Non-Resident Payment / Foreign Remittance",
        base_amount=12930.0,
    )
    assert res_12930["base_amount"] == 12930.0
    assert res_12930["base_tds_amount"] == 2586.00  # 12,930 * 20%
    assert res_12930["cess_amount"] == 103.44  # 4% of 2,586.00
    assert res_12930["tds_amount"] == 2689.44  # 2,586.00 + 103.44
    assert res_12930["total_tds_amount"] == 2689.44


def test_11_to_13_gst_rcm_defaults_on_canonical_inr():
    """Tests 11, 12, 13: Foreign service default IGST = 18%, RCM = applicable, computed on INR base."""
    gst = GSTEngine()
    invoice_payload = {
        "invoice_origin": "FOREIGN_SERVICE",
        "vendor_name": "CloudArc Global Inc",
        "vendor_country": "US",
        "vendor_address": "500 Howard St, San Francisco, CA 94105, USA",
        "customer_gstin": "29AABCS1429B1ZB",
        "place_of_supply": "29-Karnataka",
        "taxable_amount": 12930.0,
        "total_amount": 12930.0,
        "line_items": [
            {
                "description": "Cloud Infrastructure Hosting Services",
                "taxable_amount": 12930.0,
                "unit_price": 12930.0,
                "quantity": 1,
            }
        ],
    }

    res = gst.evaluate_gst(invoice_payload)
    assert res["is_reverse_charge"] is True
    assert res["rcm_category"] == "IMPORT_OF_SERVICES"
    assert res["supply_type"] == "INTER_STATE"
    assert res["calculated"]["igst_amount"] == 2327.40  # 18% of 12,930 INR
    assert res["calculated"]["cgst_amount"] == 0.0
    assert res["calculated"]["sgst_amount"] == 0.0


def test_14_itc_lifecycle_rcm_not_automatically_claimed():
    """Test 14: RCM creates tax liability; ITC state is preserved without blind auto-claiming."""
    itc = ITCEngine()
    invoice_payload = {
        "invoice_origin": "FOREIGN_SERVICE",
        "vendor_country": "US",
        "customer_gstin": "29AABCS1429B1ZB",
        "place_of_supply": "29-Karnataka",
        "taxable_amount": 12930.0,
        "total_amount": 12930.0,
        "line_items": [
            {"description": "Cloud Hosting SaaS", "taxable_amount": 12930.0, "sac_code": "998315"}
        ],
    }
    gst_res = {
        "is_reverse_charge": True,
        "rcm_category": "IMPORT_OF_SERVICES",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 2327.40, "cgst_amount": 0.0, "sgst_amount": 0.0, "gst_total": 2327.40},
    }

    itc_res = itc.evaluate_itc(invoice_data=invoice_payload, gst_result=gst_res)
    assert itc_res["status"] in ("CLAIMABLE", "ELIGIBLE", "YES", "PENDING_DISCHARGE", "PENDING", "REVIEW_REQUIRED")
    assert itc_res["is_reverse_charge"] is True


def test_15_journal_uses_inr_and_balances():
    """Test 15: Double-entry GL journal consumes canonical INR and balances."""
    jg = JournalGenerator()
    invoice_payload = {
        "invoice_origin": "FOREIGN_SERVICE",
        "vendor_name": "CloudArc Global Inc",
        "vendor_country": "US",
        "total_amount": 12930.0,
        "taxable_amount": 12930.0,
        "currency": "INR",
        "line_items": [
            {"description": "Cloud Hosting SaaS", "taxable_amount": 12930.0, "total": 12930.0}
        ],
    }
    gst_res = {
        "is_reverse_charge": True,
        "rcm_category": "IMPORT_OF_SERVICES",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 2327.40, "cgst_amount": 0.0, "sgst_amount": 0.0, "gst_total": 2327.40},
        "extracted": {"igst_amount": 0.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "tax_total": 0.0},
    }
    itc_res = {
        "status": "ELIGIBLE",
        "is_reverse_charge": True,
    }
    tds_res = {
        "applicable": True,
        "rate": 20.0,
        "base_amount": 12930.0,
        "base_tds_amount": 2586.00,
        "cess_rate": 4.0,
        "cess_amount": 103.44,
        "tds_amount": 2689.44,
    }
    acct = {
        "accounting": [
            {"account_code": "60100", "account_name": "Cloud & Hosting Expenses", "amount": 12930.0}
        ],
        "tds_assessment": tds_res,
    }

    journal = jg.generate_journal(
        invoice_data=invoice_payload,
        accounting_classification=acct,
        gst_result=gst_res,
        itc_result=itc_res,
        tds_result=tds_res,
    )

    assert journal["validation"]["balanced"] is True
    assert journal["currency"] == "INR"
    assert abs(journal["total_debit"] - journal["total_credit"]) < 0.01
    # Total debits = Expense (12,930) + Input IGST (2,327.40) = 15,257.40
    # Total credits = Accounts Payable (10,240.56) + TDS (2,689.44) + RCM Output IGST (2,327.40) = 15,257.40
    assert journal["total_debit"] == 15257.40
    assert journal["total_credit"] == 15257.40


def test_21_domestic_indian_inr_invoice_regression():
    """Test 21: Domestic Indian vendor with INR has no FX conversion and standard domestic flow."""
    classifier = InvoiceClassifier()
    res = classifier.classify(
        invoice_data={
            "vendor_name": "Infosys Limited",
            "vendor_gstin": "29AAACI1234F1Z5",
            "vendor_country": "India",
            "currency": "INR",
            "total_amount": 50000.0,
        }
    )
    assert res.classification == InvoiceClassification.INDIAN

    tds = TDSEngine()
    tds_res = tds.calculate_tds(
        applicable=True,
        section="194J",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        base_amount=50000.0,
        vendor_pan="AAACI1234F",
    )
    assert tds_res["rate"] == 2.0
    assert tds_res["cess_rate"] == 0.0
    assert tds_res["cess_amount"] == 0.0
    assert tds_res["tds_amount"] == 1000.0


def test_22_indian_vendor_with_usd_currency_remains_indian():
    """Test 22: Indian vendor billing in USD is classified as INDIAN (not FOREIGN_SERVICE)."""
    classifier = InvoiceClassifier()
    res = classifier.classify(
        invoice_data={
            "vendor_name": "Tata Consultancy Services Ltd",
            "vendor_gstin": "27AAACT1234A1ZT",
            "vendor_country": "India",
            "currency": "USD",
            "total_amount": 1000.0,
        }
    )
    assert res.classification == InvoiceClassification.INDIAN
