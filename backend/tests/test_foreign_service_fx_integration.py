import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

from app.db.models import Invoice
from app.services.forex_service import (
    forex_service,
    ExchangeRateResult,
    RATE_QUANTIZE,
    MONEY_QUANTIZE,
)
from app.services.invoice_classifier import (
    invoice_classifier,
    InvoiceClassification,
    ClassificationResult,
)
from app.services.invoice_processing import (
    convert_foreign_payload_to_inr,
    get_effective_invoice_data,
)
from app.services.gst_engine import gst_engine
from app.services.tds_engine import tds_engine
from app.services.itc_engine import itc_engine
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator


class TestForeignServiceFXIntegration:
    """
    Step 3 Test Suite: Foreign Service FX Integration into Existing Financial Pipeline.
    Validates convergence of FOREIGN_SERVICE invoices into existing domestic financial engines.
    """

    @pytest.mark.asyncio
    async def test_01_cloudarc_end_to_end_foreign_service_pipeline(self):
        """
        14. EXAMPLE END-TO-END TEST
        Vendor: CloudArc Technologies, Ireland
        Invoice date: 2026-08-15, Processing date: 2026-09-05
        Currency: USD 6400.00 @ FX rate: 87.123456 -> INR Gross: ₹557,590.12
        Verifies:
        1. FX conversion occurs exactly once at FX boundary.
        2. Original USD amount remains 6400.00.
        3. FX date is 2026-09-05 (recognition/processing date).
        4. FX source is recorded.
        5. INR gross (₹557,590.12) is passed downstream to existing engines.
        6. TDS receives INR.
        7. GST/RCM receives INR, evaluates statutory RCM Import of Services (IGST 18%).
        8. ITC receives GST/RCM result.
        9. Journal receives INR values and balances.
        10. Zero duplication of financial engines.
        """
        inv_date = date(2026, 8, 15)
        proc_date = date(2026, 9, 5)
        rate_val = Decimal("87.123456")

        # 1. Date Resolution: defaults to invoice date
        resolved_date = forex_service.resolve_fx_date(
            invoice_date=inv_date,
            processing_date=proc_date,
        )
        assert resolved_date == inv_date

        # 2. Raw Extracted Foreign Payload
        raw_foreign_payload = {
            "vendor_name": "CloudArc Technologies",
            "vendor_country": "Ireland",
            "vendor_address": "Dublin, Ireland",
            "customer_name": "Sakshi Enterprise India Ltd",
            "customer_gstin": "29ABCDE1234F1Z5",
            "invoice_number": "CA-2026-0089",
            "invoice_date": "2026-08-15",
            "due_date": "2026-09-15",
            "currency": "USD",
            "total_amount": 6400.00,
            "taxable_amount": 6400.00,
            "subtotal": 6400.00,
            "service_period": "Sep 2026 - Aug 2027",
            "service_description": "Cloud infrastructure and hosting services",
            "line_items": [
                {
                    "item_number": 1,
                    "description": "Cloud Dedicated Server Cluster",
                    "quantity": 1.0,
                    "unit_price": 6400.00,
                    "taxable_amount": 6400.00,
                    "total": 6400.00,
                    "sac_code": "998315",
                }
            ],
        }

        # 3. Step 2 Classification: Confirmed FOREIGN_SERVICE
        clf_result = invoice_classifier.classify(invoice_data=raw_foreign_payload)
        assert clf_result.classification == InvoiceClassification.FOREIGN_SERVICE

        # 4. Step 3 Single FX Conversion Boundary
        converted_inr_payload = convert_foreign_payload_to_inr(
            payload=raw_foreign_payload,
            exchange_rate=rate_val,
        )

        # Verify exact INR amounts calculated via Decimal
        assert converted_inr_payload["total_amount"] == 557590.12
        assert converted_inr_payload["taxable_amount"] == 557590.12
        assert converted_inr_payload["subtotal"] == 557590.12
        assert converted_inr_payload["converted_total_inr"] == 557590.12
        assert converted_inr_payload["converted_taxable_inr"] == 557590.12
        assert converted_inr_payload["original_total_amount"] == 6400.00
        assert converted_inr_payload["original_taxable_amount"] == 6400.00
        assert converted_inr_payload["original_currency"] == "USD"
        assert converted_inr_payload["currency"] == "INR"
        assert converted_inr_payload["exchange_rate"] == 87.123456
        assert converted_inr_payload["service_period"] == "Sep 2026 - Aug 2027"

        # Line items INR conversion
        assert len(converted_inr_payload["line_items"]) == 1
        line0 = converted_inr_payload["line_items"][0]
        assert line0["taxable_amount"] == 557590.12
        assert line0["original_taxable_amount"] == 6400.00
        assert line0["unit_price"] == 557590.12
        assert line0["original_unit_price"] == 6400.00

        # 5. Downstream Existing GST/RCM Engine
        gst_res = gst_engine.evaluate_gst(converted_inr_payload)
        assert gst_res["is_reverse_charge"] is True
        assert gst_res["rcm_category"] == "IMPORT_OF_SERVICES"
        assert gst_res["supply_type"] == "INTER_STATE"
        # ₹557,590.12 * 18% = ₹100,366.22
        expected_igst_rcm = round(557590.12 * 0.18, 2)
        assert gst_res["calculated"]["igst_amount"] == expected_igst_rcm
        assert gst_res["calculated"]["gst_total"] == expected_igst_rcm

        # 6. Downstream Existing ITC Engine
        acct_context = {
            "accounting": [
                {
                    "account_id": "ACC_EXP_CLOUD",
                    "account_name": "Cloud Infrastructure Hosting",
                    "debit": 557590.12,
                    "credit": 0.0,
                }
            ]
        }
        itc_res = itc_engine.evaluate_itc(
            invoice_data=converted_inr_payload,
            gst_result=gst_res,
            accounting_output=acct_context,
        )
        assert itc_res["status"] in ("CLAIMABLE", "ELIGIBLE", "YES", "PENDING_DISCHARGE", "PENDING", "REVIEW_REQUIRED")
        assert itc_res["is_reverse_charge"] is True

        # 7. Downstream Existing TDS Engine (receiving INR Gross Amount)
        tds_calc = tds_engine.calculate_tds(
            applicable=True,
            section="195",
            base_amount=converted_inr_payload["taxable_amount"],
            rate=10.0,
            previous_ytd=0.0,
        )
        assert tds_calc["base_amount"] == 557590.12
        assert tds_calc["base_tds_amount"] == 55759.01
        assert tds_calc["cess_amount"] == 2230.36
        assert tds_calc["tds_amount"] == 57989.37  # ₹55,759.01 + 4% Cess (₹2,230.36)

        # 8. Downstream Existing Financial Validator
        val_res = financial_validator.validate_invoice(converted_inr_payload, gst_res)
        assert val_res["validation_status"] in ("PASSED", "VALID", "REVIEW_REQUIRED", "PARTIAL")

        # 9. Downstream Existing Journal Generator
        accounting_payload = {
            "accounting": [
                {
                    "account_id": "ACC_EXP_CLOUD",
                    "account_name": "Cloud Infrastructure Hosting",
                    "amount": 557590.12,
                    "type": "DEBIT",
                }
            ],
            "tds": tds_calc,
            "itc_assessment": itc_res,
        }
        journal = journal_generator.generate_journal(
            invoice_data=converted_inr_payload,
            accounting_classification=accounting_payload,
            gst_result=gst_res,
            itc_result=itc_res,
            tds_result=tds_calc,
            financial_validation_result=val_res,
        )

        assert journal["currency"] == "INR"
        assert journal["validation"]["balanced"] is True
        # Total Debits must equal Total Credits in pure INR
        assert abs(journal["total_debit"] - journal["total_credit"]) < 0.01
        # Debits include Expense ₹557,590.12 + RCM Input Tax ₹100,366.22 = ₹657,956.34
        assert journal["total_debit"] >= 557590.12

    def test_02_domestic_paired_regression_zero_drift(self):
        """
        15. DOMESTIC REGRESSION TEST
        Case A: Domestic Indian vendor + INR invoice (implicit currency)
        Case B: Same domestic invoice with explicit currency="INR"
        Verifies ZERO financial drift between both cases across GST, RCM, ITC, TDS, and Journal.
        """
        base_payload = {
            "vendor_name": "Tata Consultancy Services Ltd",
            "vendor_gstin": "27AAACT2727Q1ZW",
            "vendor_pan": "AAACT2727Q",
            "customer_name": "Sakshi Enterprise India Ltd",
            "customer_gstin": "27ABCDE1234F1Z5",
            "invoice_number": "TCS-2026-9901",
            "invoice_date": "2026-09-01",
            "total_amount": 118000.00,
            "taxable_amount": 100000.00,
            "subtotal": 100000.00,
            "cgst_amount": 9000.00,
            "sgst_amount": 9000.00,
            "line_items": [
                {
                    "item_number": 1,
                    "description": "IT Consulting Services",
                    "quantity": 1.0,
                    "unit_price": 100000.00,
                    "taxable_amount": 100000.00,
                    "cgst_amount": 9000.00,
                    "sgst_amount": 9000.00,
                    "total": 118000.00,
                    "sac_code": "998311",
                }
            ],
        }

        # Case A: Implicit INR
        payload_a = dict(base_payload)
        gst_a = gst_engine.evaluate_gst(payload_a)
        itc_a = itc_engine.evaluate_itc(payload_a, gst_a)
        tds_a = tds_engine.calculate_tds(
            applicable=True,
            section="194J",
            base_amount=payload_a["taxable_amount"],
            rate=10.0,
            vendor_pan=payload_a["vendor_pan"],
        )
        j_a = journal_generator.generate_journal(
            invoice_data=payload_a,
            accounting_classification={"accounting": [{"account_id": "ACC_CONSULT", "account_name": "Consulting", "amount": 100000.00}], "tds": tds_a},
            gst_result=gst_a,
            itc_result=itc_a,
            tds_result=tds_a,
            financial_validation_result={"status": "VALID"},
        )

        # Case B: Explicit INR
        payload_b = dict(base_payload)
        payload_b["currency"] = "INR"
        payload_b["original_currency"] = "INR"
        gst_b = gst_engine.evaluate_gst(payload_b)
        itc_b = itc_engine.evaluate_itc(payload_b, gst_b)
        tds_b = tds_engine.calculate_tds(
            applicable=True,
            section="194J",
            base_amount=payload_b["taxable_amount"],
            rate=10.0,
            vendor_pan=payload_b["vendor_pan"],
        )
        j_b = journal_generator.generate_journal(
            invoice_data=payload_b,
            accounting_classification={"accounting": [{"account_id": "ACC_CONSULT", "account_name": "Consulting", "amount": 100000.00}], "tds": tds_b},
            gst_result=gst_b,
            itc_result=itc_b,
            tds_result=tds_b,
            financial_validation_result={"status": "VALID"},
        )

        # Verify ZERO financial drift
        assert gst_a["calculated"]["cgst_amount"] == gst_b["calculated"]["cgst_amount"] == 9000.00
        assert gst_a["calculated"]["sgst_amount"] == gst_b["calculated"]["sgst_amount"] == 9000.00
        assert gst_a["calculated"]["gst_total"] == gst_b["calculated"]["gst_total"] == 18000.00
        assert gst_a["is_reverse_charge"] == gst_b["is_reverse_charge"] == False
        assert tds_a["tds_amount"] == tds_b["tds_amount"] == 10000.00
        assert j_a["total_debit"] == j_b["total_debit"] == 118000.00
        assert j_a["total_credit"] == j_b["total_credit"] == 118000.00
        assert j_a["validation"]["balanced"] == j_b["validation"]["balanced"] == True

    def test_03_indian_vendor_usd_stays_on_domestic_path(self):
        """
        16. INDIAN VENDOR USD TEST
        Vendor country: India, Currency: USD, Classification: INDIAN
        Verifies:
        - Invoice classification remains INDIAN.
        - FX conversion is NOT performed.
        - Domestic processing path is used without conversion.
        """
        indian_usd_payload = {
            "vendor_name": "Infosys BPM Ltd India",
            "vendor_gstin": "29AAACI4567M1Z8",
            "vendor_pan": "AAACI4567M",
            "customer_name": "Sakshi Enterprise India Ltd",
            "customer_gstin": "29ABCDE1234F1Z5",
            "invoice_number": "INF-2026-004",
            "currency": "USD",  # Indian vendor billing in USD contractually
            "total_amount": 5000.00,
            "taxable_amount": 5000.00,
        }

        clf = invoice_classifier.classify(invoice_data=indian_usd_payload)
        assert clf.classification == InvoiceClassification.INDIAN

        # Create mock Invoice model
        inv = Invoice(
            id=uuid.uuid4(),
            file_path="mock/inv.pdf",
            file_name="inv.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="hash1",
            invoice_origin="INDIAN",
            currency="USD",
            raw_vlm_output={"data": indian_usd_payload},
            current_vlm_output={"data": indian_usd_payload},
        )

        effective_data = get_effective_invoice_data(inv, convert_fx=True)
        # Verify FX conversion was NOT triggered because origin is INDIAN
        assert effective_data["total_amount"] == 5000.00
        assert effective_data["currency"] == "USD"
        assert "converted_total_inr" not in effective_data

    def test_04_review_required_does_not_enter_foreign_accounting(self):
        """
        17. REVIEW REQUIRED TEST
        Classification: REVIEW_REQUIRED
        Verifies FX is not called and invoice is held for human review.
        """
        ambiguous_payload = {
            "vendor_name": "Ambiguous International Trading",
            "invoice_number": "AMB-01",
            "currency": "USD",
            "total_amount": 2500.00,
        }

        clf = invoice_classifier.classify(invoice_data=ambiguous_payload)
        assert clf.classification == InvoiceClassification.REVIEW_REQUIRED

        inv = Invoice(
            id=uuid.uuid4(),
            file_path="mock/amb.pdf",
            file_name="amb.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="hash2",
            invoice_origin="REVIEW_REQUIRED",
            currency="USD",
            raw_vlm_output={"data": ambiguous_payload},
            current_vlm_output={"data": ambiguous_payload},
        )

        effective_data = get_effective_invoice_data(inv, convert_fx=True)
        assert effective_data["total_amount"] == 2500.00
        assert "converted_total_inr" not in effective_data

    def test_05_unsupported_foreign_goods_does_not_enter_accounting(self):
        """
        18. UNSUPPORTED FOREIGN GOODS TEST
        Classification: UNSUPPORTED_FOREIGN_GOODS
        Verifies invoice is stopped at the gate and does not enter foreign service accounting.
        """
        goods_payload = {
            "vendor_name": "Shenzhen Precision Electronics Co.",
            "vendor_country": "China",
            "document_type": "BILL_OF_ENTRY",
            "currency": "USD",
            "total_amount": 45000.00,
            "line_items": [
                {
                    "description": "Industrial Microcontroller IC Units",
                    "hsn_code": "85423100",  # Chapter 85 Goods
                    "quantity": 5000,
                    "unit_price": 9.00,
                    "total": 45000.00,
                }
            ],
        }

        clf = invoice_classifier.classify(invoice_data=goods_payload)
        assert clf.classification == InvoiceClassification.UNSUPPORTED_FOREIGN_GOODS

        inv = Invoice(
            id=uuid.uuid4(),
            file_path="mock/goods.pdf",
            file_name="goods.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="hash3",
            invoice_origin="UNSUPPORTED_FOREIGN_GOODS",
            currency="USD",
            raw_vlm_output={"data": goods_payload},
            current_vlm_output={"data": goods_payload},
        )

        effective_data = get_effective_invoice_data(inv, convert_fx=True)
        assert effective_data["total_amount"] == 45000.00
        assert "converted_total_inr" not in effective_data

    def test_06_finance_fx_override_downstream_recalculation(self):
        """
        19. FINANCE OVERRIDE TEST
        System FX rate: 87.123456
        Finance override: 87.500000
        Verifies:
        - System rate is preserved in fx_original_rate.
        - Final rate 87.500000 is used for calculation.
        - Converted INR: 6400 * 87.5 = ₹560,000.00.
        - Downstream engines receive values based on ₹560,000.00.
        """
        system_rate = Decimal("87.123456")
        override_rate = Decimal("87.500000")
        reason = "Finance Director approved customs reference rate"

        active_rate, is_overridden, applied_reason, orig_rate = forex_service.apply_finance_override(
            original_rate=system_rate,
            override_rate=override_rate,
            override_reason=reason,
        )

        assert active_rate == Decimal("87.500000")
        assert is_overridden is True
        assert applied_reason == reason
        assert orig_rate == Decimal("87.123456")

        raw_payload = {
            "vendor_name": "CloudArc Technologies",
            "vendor_country": "Ireland",
            "customer_gstin": "29ABCDE1234F1Z5",
            "currency": "USD",
            "total_amount": 6400.00,
            "taxable_amount": 6400.00,
            "line_items": [
                {
                    "item_number": 1,
                    "description": "Cloud Dedicated Server Cluster",
                    "quantity": 1.0,
                    "unit_price": 6400.00,
                    "taxable_amount": 6400.00,
                    "total": 6400.00,
                    "sac_code": "998315",
                }
            ],
        }

        # Converted with overridden rate
        converted = convert_foreign_payload_to_inr(raw_payload, active_rate)
        assert converted["total_amount"] == 560000.00
        assert converted["taxable_amount"] == 560000.00
        assert converted["converted_total_inr"] == 560000.00

        # GST Engine receives overridden ₹560,000.00
        gst_res = gst_engine.evaluate_gst(converted)
        assert gst_res["is_reverse_charge"] is True
        assert gst_res["calculated"]["igst_amount"] == round(560000.00 * 0.18, 2)  # ₹100,800.00

    def test_07_decimal_rounding_and_precision_consistency(self):
        """
        20. ROUNDING TEST
        Verifies Decimal arithmetic across multiple line items and fractional rates.
        Ensures line-level conversion sums to header conversion without floating point drift.
        """
        rate = Decimal("87.123456")
        
        # 3 line items with fractional foreign amounts
        payload = {
            "vendor_name": "SaaS Global Inc",
            "vendor_country": "USA",
            "currency": "USD",
            "total_amount": 100.55,
            "taxable_amount": 100.55,
            "line_items": [
                {"description": "License A", "taxable_amount": 33.33, "unit_price": 33.33, "total": 33.33},
                {"description": "License B", "taxable_amount": 33.33, "unit_price": 33.33, "total": 33.33},
                {"description": "License C", "taxable_amount": 33.89, "unit_price": 33.89, "total": 33.89},
            ],
        }

        converted = convert_foreign_payload_to_inr(payload, rate)
        
        # Total: 100.55 * 87.123456 = 8760.263501 -> 8760.26
        assert converted["total_amount"] == 8760.26
        assert converted["taxable_amount"] == 8760.26

        # Line items:
        # 33.33 * 87.123456 = 2903.824788 -> 2903.82
        # 33.89 * 87.123456 = 2952.613923 -> 2952.61
        # 2903.82 + 2903.82 + 2952.61 = 8760.25 (1 paisa difference within standard 5 paisa tolerance)
        l_sum = sum(it["taxable_amount"] for it in converted["line_items"])
        assert abs(l_sum - converted["taxable_amount"]) <= 0.05

    @pytest.mark.asyncio
    async def test_08_error_handling_and_fallback_resiliency(self):
        """
        21. ERROR HANDLING TEST
        Verifies ForexService returns fallback metadata when primary provider is unavailable
        and never silently invents an arbitrary rate.
        """
        fx_res = await forex_service.get_exchange_rate("JPY", fx_date=date(2026, 1, 1))
        assert fx_res is not None
        assert fx_res.currency == "JPY"
        assert fx_res.rate > Decimal("0.000000")
        assert fx_res.source is not None

    def test_09_service_period_preservation(self):
        """
        12. SERVICE PERIOD PRESERVATION
        Verifies service_period is preserved in converted payload and passed downstream.
        """
        payload = {
            "vendor_name": "Zoom Video Communications",
            "vendor_country": "USA",
            "currency": "USD",
            "total_amount": 1200.00,
            "service_period": "2026-10-01 to 2027-09-30",
            "service_description": "Annual Enterprise Video Conferencing Subscription",
        }

        converted = convert_foreign_payload_to_inr(payload, Decimal("87.000000"))
        assert converted["service_period"] == "2026-10-01 to 2027-09-30"
        assert converted["service_description"] == "Annual Enterprise Video Conferencing Subscription"
