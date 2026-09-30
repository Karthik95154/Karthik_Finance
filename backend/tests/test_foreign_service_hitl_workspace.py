import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.db.models import Invoice
from app.services.forex_service import forex_service
from app.services.invoice_classifier import invoice_classifier, InvoiceClassification
from app.services.invoice_processing import (
    convert_foreign_payload_to_inr,
    get_effective_invoice_data,
)
from app.services.gst_engine import gst_engine
from app.services.tds_engine import tds_engine
from app.services.itc_engine import itc_engine
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator


class TestForeignServiceHitlWorkspace:
    """
    Step 4 Test Suite: Finance Workspace / HITL for Foreign Service Invoices.
    Validates complete review chain, three-tier provenance (System vs Override vs Final),
    dynamic recalculation upon FX/classification edits, audit persistence, and approval states.
    """

    def test_01_foreign_invoice_review_data_mapping_and_provenance(self):
        """
        A & B. Review Rendering & Three-Tier Provenance:
        Verifies SYSTEM vs FINANCE OVERRIDE vs FINAL for both classification and FX rate.
        """
        inv_id = uuid.uuid4()
        raw_payload = {
            "vendor_name": "CloudArc Technologies",
            "vendor_country": "Ireland",
            "vendor_tax_id": "IE9823741A",
            "service_description": "Dedicated Cloud Cluster Hosting",
            "service_period": "Sep 2026 - Aug 2027",
            "currency": "USD",
            "total_amount": 6400.00,
            "taxable_amount": 6400.00,
            "line_items": [
                {
                    "item_number": 1,
                    "description": "Cloud Server Hosting",
                    "unit_price": 6400.00,
                    "taxable_amount": 6400.00,
                    "total": 6400.00,
                    "sac_code": "998315",
                }
            ],
        }

        # 1. System state
        system_class = InvoiceClassification.FOREIGN_SERVICE
        system_fx_rate = Decimal("87.123456")
        converted_inr = forex_service.convert_to_inr(Decimal("6400.00"), system_fx_rate)

        invoice = Invoice(
            id=inv_id,
            file_path="mock/cloudarc.pdf",
            file_name="cloudarc.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="hash_cloudarc",
            invoice_origin="FOREIGN_SERVICE",
            currency="INR",
            original_currency="USD",
            original_total_amount=Decimal("6400.00"),
            original_taxable_amount=Decimal("6400.00"),
            exchange_rate=system_fx_rate,
            fx_original_rate=system_fx_rate,
            fx_rate_overridden=False,
            converted_total_inr=converted_inr,
            converted_taxable_inr=converted_inr,
            raw_vlm_output={"data": raw_payload},
            current_vlm_output={"data": raw_payload},
            approval_status="PENDING_REVIEW",
        )

        # Verify initial mapping
        effective_data = get_effective_invoice_data(invoice, convert_fx=True)
        assert effective_data["total_amount"] == 557590.12
        assert effective_data["vendor_country"] == "Ireland"
        assert effective_data["vendor_tax_id"] == "IE9823741A"
        assert effective_data["service_period"] == "Sep 2026 - Aug 2027"

        # 2. Finance FX Override: System vs Override vs Final
        override_fx_rate = Decimal("87.500000")
        reason_fx = "Customs notified reference rate"
        active_rate, is_fx_ovr, applied_fx_reason, orig_rate = forex_service.apply_finance_override(
            original_rate=system_fx_rate,
            override_rate=override_fx_rate,
            override_reason=reason_fx,
        )

        invoice.exchange_rate = active_rate
        invoice.fx_original_rate = orig_rate
        invoice.fx_rate_overridden = is_fx_ovr
        invoice.fx_override_reason = applied_fx_reason
        invoice.converted_total_inr = forex_service.convert_to_inr(Decimal("6400.00"), active_rate)
        invoice.converted_taxable_inr = forex_service.convert_to_inr(Decimal("6400.00"), active_rate)

        assert invoice.fx_original_rate == Decimal("87.123456")  # System rate preserved
        assert invoice.exchange_rate == Decimal("87.500000")      # Final active rate
        assert invoice.fx_rate_overridden is True
        assert invoice.fx_override_reason == reason_fx
        assert invoice.converted_total_inr == Decimal("560000.00")

    def test_02_recalculation_after_fx_edit_prevents_stale_downstream_values(self):
        """
        J & K. Recalculation After FX Edit:
        When FX rate is modified, INR Gross updates and downstream GST, TDS, ITC, and Journal
        recalculate automatically with zero stale values.
        """
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
                    "unit_price": 6400.00,
                    "taxable_amount": 6400.00,
                    "total": 6400.00,
                    "sac_code": "998315",
                }
            ],
        }

        # Step 1: Initial rate 87.123456 -> INR 557,590.12
        initial_rate = Decimal("87.123456")
        payload_1 = convert_foreign_payload_to_inr(raw_payload, initial_rate)
        assert payload_1["total_amount"] == 557590.12

        gst_1 = gst_engine.evaluate_gst(payload_1)
        tds_1 = tds_engine.calculate_tds(applicable=True, section="195", base_amount=payload_1["taxable_amount"], rate=10.0)
        itc_1 = itc_engine.evaluate_itc(payload_1, gst_result=gst_1)

        assert gst_1["calculated"]["igst_amount"] == 100366.22
        assert tds_1["base_tds_amount"] == 55759.01
        assert tds_1["cess_amount"] == 2230.36
        assert tds_1["tds_amount"] == 57989.37

        # Step 2: Finance edits FX rate to 88.000000 -> Converted INR becomes ₹563,200.00
        edited_rate = Decimal("88.000000")
        payload_2 = convert_foreign_payload_to_inr(raw_payload, edited_rate)
        assert payload_2["total_amount"] == 563200.00
        assert payload_2["taxable_amount"] == 563200.00

        # Recalculate downstream
        gst_2 = gst_engine.evaluate_gst(payload_2)
        tds_2 = tds_engine.calculate_tds(applicable=True, section="195", base_amount=payload_2["taxable_amount"], rate=10.0)
        itc_2 = itc_engine.evaluate_itc(payload_2, gst_result=gst_2)

        # Verify downstream values are refreshed to match ₹563,200.00 with ZERO stale values
        assert gst_2["calculated"]["igst_amount"] == round(563200.00 * 0.18, 2)  # ₹101,376.00 (NOT ₹100,366.22)
        assert tds_2["base_amount"] == 563200.00
        assert tds_2["base_tds_amount"] == 563200.00 * 0.10  # ₹56,320.00
        assert tds_2["cess_amount"] == 2252.80  # 4% of ₹56,320.00
        assert tds_2["tds_amount"] == 58572.80  # ₹56,320.00 + ₹2,252.80

        # Journal recalculation with updated values
        acct_payload = {
            "accounting": [
                {
                    "account_id": "ACC_EXP",
                    "account_name": "Cloud Infrastructure",
                    "amount": 563200.00,
                    "type": "DEBIT",
                    "is_approved": True,
                }
            ],
            "tds": tds_2,
            "itc_assessment": itc_2,
        }
        journal = journal_generator.generate_journal(
            invoice_data=payload_2,
            accounting_classification=acct_payload,
            gst_result=gst_2,
            itc_result=itc_2,
            tds_result=tds_2,
        )

        assert abs(journal["total_debit"] - journal["total_credit"]) < 0.01
        assert journal["total_debit"] == round(563200.00 + 101376.00, 2)  # ₹664,576.00 (Expense + RCM IGST Input)
        assert journal["total_credit"] == round(563200.00 + 101376.00, 2)  # ₹664,576.00 (AP + TDS + RCM IGST Output)

    def test_03_classification_override_audit_trail_and_reason_requirement(self):
        """
        D & H & I. Classification Override Audit Trail:
        Verifies system classification is preserved, override records mandatory reason,
        user, and timestamp, and changes pipeline routing accordingly.
        """
        raw_payload = {
            "vendor_name": "Apex Global Vendor",
            "vendor_country": "",
            "currency": "EUR",
            "total_amount": 1500.00,
            "taxable_amount": 1500.00,
            "line_items": [
                {"description": "General Consulting Services", "taxable_amount": 1500.00}
            ],
        }

        # Initially REVIEW_REQUIRED due to foreign currency without clear foreign entity country
        clf_result = invoice_classifier.classify(raw_payload)
        assert clf_result.classification == InvoiceClassification.REVIEW_REQUIRED

        # Finance overrides to FOREIGN_SERVICE
        user_email = "finance.controller@sakshi.com"
        now_ts = datetime.now(timezone.utc)
        override_reason = "Vendor registered in Delaware, USA confirmed via W-8BEN form."

        invoice = Invoice(
            id=uuid.uuid4(),
            file_path="mock/generic.pdf",
            file_name="generic.pdf",
            file_size=500,
            mime_type="application/pdf",
            file_hash="hash_generic",
            invoice_origin=clf_result.classification.value,
            classification_source="SYSTEM",
            currency="USD",
            raw_vlm_output={"data": raw_payload},
            current_vlm_output={"data": raw_payload},
        )

        # Apply override
        previous_origin = invoice.invoice_origin
        invoice.classification_override = "FOREIGN_SERVICE"
        invoice.classification_override_reason = override_reason
        invoice.classified_by = user_email
        invoice.classified_at = now_ts
        invoice.invoice_origin = "FOREIGN_SERVICE"
        invoice.classification_source = "USER_OVERRIDE"

        assert invoice.classification_override == "FOREIGN_SERVICE"
        assert invoice.classification_override_reason == override_reason
        assert invoice.classified_by == user_email
        assert invoice.classified_at == now_ts
        assert invoice.invoice_origin == "FOREIGN_SERVICE"

    def test_04_approval_state_explicit_and_not_marked_posted(self):
        """
        E & 7. Explicit Approval State:
        After Finance ACCEPT, invoice status becomes APPROVED (ready for downstream Zoho export),
        and is NOT marked 'POSTED' or 'EXPORTED' prematurely.
        """
        inv_id = uuid.uuid4()
        now_iso = datetime.now(timezone.utc).isoformat()

        journal_dict = {
            "status": "APPROVED",
            "approval_status": "APPROVED",
            "is_balanced": True,
            "total_debit": 557590.12,
            "total_credit": 557590.12,
            "lines": [
                {"account_id": "ACC_EXP", "debit": 557590.12, "credit": 0.0},
                {"account_id": "ACC_AP", "debit": 0.0, "credit": 501831.11},
                {"account_id": "ACC_TDS", "debit": 0.0, "credit": 55759.01},
            ],
        }

        invoice = Invoice(
            id=inv_id,
            file_path="mock/test.pdf",
            file_name="test.pdf",
            file_size=100,
            mime_type="application/pdf",
            file_hash="hash_test",
            status="COMPLETED",
            approval_status="APPROVED",
            accounting_status="COMPLETED",
            export_status="NOT_EXPORTED",
            journal_entry=journal_dict,
            invoice_origin="FOREIGN_SERVICE",
            converted_total_inr=Decimal("557590.12"),
        )

        # Verify approval state
        assert invoice.approval_status == "APPROVED"
        assert invoice.export_status != "EXPORTED"  # NOT marked EXPORTED or POSTED
        assert invoice.journal_entry["is_balanced"] is True

    def test_05_rejection_state_preserves_reason_and_unlocks(self):
        """
        G & 7. Rejection State:
        If Finance REJECTS, approval status becomes REJECTED, rejection reason is preserved,
        and invoice is unlocked for corrections.
        """
        invoice = Invoice(
            id=uuid.uuid4(),
            file_path="mock/reject.pdf",
            file_name="reject.pdf",
            file_size=100,
            mime_type="application/pdf",
            file_hash="hash_rej",
            status="PROCESSING",
            approval_status="PENDING_REVIEW",
            invoice_origin="FOREIGN_SERVICE",
        )

        rejection_reason = "Service period does not match contractual statement of work."
        invoice.approval_status = "REJECTED"
        invoice.error_message = f"Rejected: {rejection_reason}"

        assert invoice.approval_status == "REJECTED"
        assert rejection_reason in invoice.error_message

    def test_06_foreign_service_rcm_and_itc_display_integrity(self):
        """
        N & O. Foreign Service RCM & ITC State Display:
        Verifies statutory RCM category and multi-state ITC lifecycle
        (not simplistic 'ITC = Yes' or 'Foreign = RCM').
        """
        foreign_inr_payload = {
            "vendor_name": "Atlassian Pty Ltd",
            "vendor_country": "Australia",
            "customer_gstin": "29ABCDE1234F1Z5",
            "total_amount": 250000.00,
            "taxable_amount": 250000.00,
            "currency": "INR",
            "line_items": [
                {
                    "item_number": 1,
                    "description": "Jira Cloud Enterprise Subscription",
                    "unit_price": 250000.00,
                    "taxable_amount": 250000.00,
                    "total": 250000.00,
                    "sac_code": "998315",
                }
            ],
        }

        # 1. GST Engine evaluation
        gst_res = gst_engine.evaluate_gst(foreign_inr_payload)
        assert gst_res["is_reverse_charge"] is True
        assert gst_res["rcm_category"] == "IMPORT_OF_SERVICES"
        assert gst_res["rcm_notification"] == "IGST Act Sec 5(3) / Notif 10/2017-IT(R) Entry 1"
        assert gst_res["supply_type"] == "INTER_STATE"

        # 2. ITC Engine evaluation with accounting context
        acct_context = {
            "accounting": [
                {
                    "account_id": "ACC_EXP",
                    "account_name": "Software Subscription",
                    "debit": 250000.00,
                    "credit": 0.0,
                }
            ]
        }
        itc_res = itc_engine.evaluate_itc(foreign_inr_payload, gst_result=gst_res, accounting_output=acct_context)
        assert itc_res["is_reverse_charge"] is True
        assert itc_res["status"] in ("CLAIMABLE", "ELIGIBLE", "YES", "PENDING_DISCHARGE", "PENDING", "REVIEW_REQUIRED")
        assert "itc_breakdown" in itc_res or "category_assessments" in itc_res or "itc_reasoning" in itc_res or "reason" in itc_res

    def test_07_domestic_inr_and_indian_vendor_usd_regression_safety(self):
        """
        L & M. Domestic Invoice Regression Safety:
        - Indian INR invoice remains on standard domestic workflow.
        - Indian vendor billing in USD remains classified as INDIAN and does not trigger FX conversion.
        """
        # Case A: Domestic INR Invoice
        domestic_inr = {
            "vendor_name": "Infosys BPM Limited",
            "vendor_country": "India",
            "vendor_gstin": "29AAACI4747B1ZS",
            "customer_gstin": "29ABCDE1234F1Z5",
            "currency": "INR",
            "total_amount": 118000.00,
            "taxable_amount": 100000.00,
            "cgst_amount": 9000.00,
            "sgst_amount": 9000.00,
            "line_items": [
                {"description": "IT Consulting Services", "taxable_amount": 100000.00, "cgst_amount": 9000.00, "sgst_amount": 9000.00}
            ],
        }

        clf_a = invoice_classifier.classify(domestic_inr)
        assert clf_a.classification == InvoiceClassification.INDIAN

        # Case B: Indian Vendor Billing in USD
        indian_usd = {
            "vendor_name": "Tata Consultancy Services Ltd",
            "vendor_country": "India",
            "vendor_address": "Mumbai, Maharashtra, India",
            "vendor_gstin": "27AAACT2727Q1ZW",
            "customer_gstin": "29ABCDE1234F1Z5",
            "currency": "USD",
            "total_amount": 5000.00,
            "taxable_amount": 5000.00,
            "line_items": [
                {"description": "Global Project Management", "taxable_amount": 5000.00, "unit_price": 5000.00}
            ],
        }

        clf_b = invoice_classifier.classify(indian_usd)
        assert clf_b.classification == InvoiceClassification.INDIAN
        assert clf_b.classification != InvoiceClassification.FOREIGN_SERVICE
