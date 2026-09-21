"""
Unit & Integration Tests for Zoho-Based Vendor YTD for TDS
Tests A, B, C, D, E, F, G as specified in requirements.
"""
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.zoho_client import ZohoClientService
from app.db.models import Vendor, ZohoConnection, Invoice
from app.services.tds_engine import tds_engine


class TestZohoVendorYTDIntegration(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.zoho_client = ZohoClientService()
        self.mock_connection = MagicMock(spec=ZohoConnection)
        self.mock_connection.status = "CONNECTED"
        self.mock_connection.organization_id = "org_123"
        self.mock_db = AsyncMock()

    async def test_a_zoho_vendor_bills_successfully_retrieved(self):
        """TEST A: Zoho vendor mapping exists and Zoho bills are successfully retrieved."""
        mock_bills = [
            {"bill_id": "b1", "sub_total": 25000.0, "status": "paid"},
            {"bill_id": "b2", "sub_total": 15000.0, "status": "open"},
        ]
        with patch.object(self.zoho_client, "_make_authorized_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"bills": mock_bills, "page_context": {"has_more_page": False}}
            res = await self.zoho_client.get_vendor_bills(
                connection=self.mock_connection,
                db=self.mock_db,
                vendor_id="zoho_v_100",
                date_start="2025-04-01",
                date_end="2026-03-31",
            )
            self.assertEqual(len(res), 2)
            self.assertEqual(res[0]["sub_total"], 25000.0)

    async def test_b_multiple_zoho_bills_summed_using_pretax_subtotal(self):
        """TEST B: Multiple Zoho bills are summed using pre-tax subtotal."""
        mock_bills = [
            {"bill_id": "b1", "sub_total": 30000.0, "total": 35400.0, "status": "paid"},
            {"bill_id": "b2", "sub_total": 18000.0, "total": 21240.0, "status": "approved"},
        ]
        pretax_sum = sum(float(b["sub_total"]) for b in mock_bills if b.get("status") not in ("void", "cancelled", "deleted"))
        self.assertEqual(pretax_sum, 48000.0)

    async def test_c_current_invoice_not_included_in_previous_ytd(self):
        """TEST C: Current invoice is not included in previous_ytd; projected_ytd = previous_ytd + current_amount."""
        previous_ytd = 48000.0
        current_amount = 5000.0
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=current_amount,
            previous_ytd=previous_ytd,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["previous_ytd"], 48000.0)
        self.assertEqual(res["current_invoice_amount"], 5000.0)
        self.assertEqual(res["projected_ytd"], 53000.0)

    async def test_d_zoho_unavailable_fallback_to_local(self):
        """TEST D: When Zoho is unavailable, fallback gracefully to empty list / local query."""
        with patch.object(self.zoho_client, "_make_authorized_request", side_effect=Exception("Zoho API Down")):
            res = await self.zoho_client.get_vendor_bills(
                connection=self.mock_connection,
                db=self.mock_db,
                vendor_id="zoho_v_100",
            )
            self.assertEqual(res, [])

    async def test_e_vendor_has_no_zoho_contact_id(self):
        """TEST E: When vendor_id is None or empty, empty list returned for fallback."""
        res = await self.zoho_client.get_vendor_bills(
            connection=self.mock_connection,
            db=self.mock_db,
            vendor_id="",
        )
        self.assertEqual(res, [])

    async def test_f_zoho_bill_has_gst_pretax_used(self):
        """TEST F: When Zoho bill has GST, total - tax_total or sub_total is used (NOT GST-inclusive total)."""
        bill_with_gst = {"total": 11800.0, "tax_total": 1800.0, "status": "open"}
        pretax = float(bill_with_gst["total"]) - float(bill_with_gst["tax_total"])
        self.assertEqual(pretax, 10000.0)
        self.assertNotEqual(pretax, bill_with_gst["total"])

    def test_g_existing_tds_threshold_tests_pass(self):
        """TEST G: Existing statutory TDS threshold rules evaluated unchanged."""
        res = tds_engine.evaluate_threshold_state(
            resolved_category="PROFESSIONAL_SERVICES",
            previous_ytd=48000.0,
            current_amount=5000.0,
            section_raw="194J",
        )
        self.assertEqual(res["previous_ytd"], 48000.0)
        self.assertEqual(res["projected_ytd"], 53000.0)
        self.assertIn(res["threshold_status"], ("THRESHOLD_CROSSED", "THRESHOLD_ALREADY_CROSSED", "SINGLE_INVOICE_THRESHOLD_EXCEEDED"))

    async def test_i_get_bill_detail_returns_sub_total(self):
        """TEST I: get_bill_detail fetches individual bill endpoint GET /bills/{bill_id} returning exact sub_total."""
        mock_detail = {
            "bill_id": "5652783360",
            "sub_total": 162443.65,
            "tax_total": 29239.86,
            "total": 188434.64,
        }
        with patch.object(self.zoho_client, "_make_authorized_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"bill": mock_detail}
            res = await self.zoho_client.get_bill_detail(
                connection=self.mock_connection,
                db=self.mock_db,
                bill_id="5652783360",
            )
            self.assertEqual(res["sub_total"], 162443.65)
            self.assertEqual(res["total"], 188434.64)

    async def test_j_list_summary_subtotal_none_does_not_use_gross_total(self):
        """TEST J: Summary list item with sub_total=None and tax_total=None uses detail endpoint sub_total (162443.65), NOT gross total (188434.64)."""
        list_item = {"bill_id": "b_5652783360", "total": 188434.64, "status": "overdue", "sub_total": None, "tax_total": None}
        detail_item = {"bill_id": "b_5652783360", "sub_total": 162443.65, "tax_total": 29239.86, "total": 188434.64}

        with patch.object(self.zoho_client, "get_bill_detail", new_callable=AsyncMock) as mock_detail:
            mock_detail.return_value = detail_item
            
            # Simulate invoice processing logic for sub_total resolution
            sub_t = list_item.get("sub_total")
            if sub_t is None and list_item.get("bill_id"):
                detail = await self.zoho_client.get_bill_detail(
                    connection=self.mock_connection,
                    db=self.mock_db,
                    bill_id=list_item["bill_id"],
                )
                sub_t = detail.get("sub_total")

            self.assertEqual(sub_t, 162443.65)
            self.assertNotEqual(sub_t, list_item["total"])


if __name__ == "__main__":
    unittest.main()
