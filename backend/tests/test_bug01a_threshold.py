"""
Focused Unit Tests for BUG-01A: Statutory TDS Threshold & Vendor YTD Logic State Machine
"""
import unittest
from app.services.tds_engine import tds_engine, STATUTORY_TDS_TABLE_2025

class TestBug01AThresholdStateMachine(unittest.TestCase):

    def test_case_a_below_threshold(self):
        """CASE A: Previous YTD + Current invoice < Threshold -> BELOW_THRESHOLD, TDS base = 0, TDS = 0"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=40000.0, # Projected = 45,000 < 50,000
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["threshold_status"], "BELOW_THRESHOLD")
        self.assertEqual(res["threshold_amount"], 50000.0)
        self.assertEqual(res["previous_ytd"], 40000.0)
        self.assertEqual(res["current_invoice_amount"], 5000.0)
        self.assertEqual(res["projected_ytd"], 45000.0)
        self.assertEqual(res["tds_base_amount"], 0.0)
        self.assertEqual(res["tds_amount"], 0.0)
        self.assertFalse(res["applicable"])

    def test_case_b_exactly_reaches_threshold(self):
        """CASE B: Previous YTD < Threshold AND Projected YTD == Threshold -> THRESHOLD_CROSSED, TDS base = Projected YTD"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=45000.0, # Projected = 50,000 == 50,000
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["threshold_status"], "THRESHOLD_CROSSED")
        self.assertEqual(res["threshold_amount"], 50000.0)
        self.assertEqual(res["previous_ytd"], 45000.0)
        self.assertEqual(res["current_invoice_amount"], 5000.0)
        self.assertEqual(res["projected_ytd"], 50000.0)
        self.assertEqual(res["tds_base_amount"], 50000.0)
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_amount"], 5000.0) # 10% of 50,000
        self.assertTrue(res["applicable"])

    def test_case_c_crosses_threshold(self):
        """CASE C: Previous YTD < Threshold AND Projected YTD > Threshold -> THRESHOLD_CROSSED, TDS base = Projected YTD"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=20000.0,
            previous_ytd=40000.0, # Projected = 60,000 > 50,000
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["threshold_status"], "THRESHOLD_CROSSED")
        self.assertEqual(res["threshold_amount"], 50000.0)
        self.assertEqual(res["previous_ytd"], 40000.0)
        self.assertEqual(res["current_invoice_amount"], 20000.0)
        self.assertEqual(res["projected_ytd"], 60000.0)
        self.assertEqual(res["tds_base_amount"], 60000.0)
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_amount"], 6000.0) # 10% of 60,000
        self.assertTrue(res["applicable"])

    def test_case_d_already_crossed_threshold(self):
        """CASE D: Previous YTD >= Threshold -> THRESHOLD_ALREADY_CROSSED, TDS base = Current Invoice Subtotal"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=10000.0,
            previous_ytd=60000.0, # Previous YTD >= 50,000
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["threshold_status"], "THRESHOLD_ALREADY_CROSSED")
        self.assertEqual(res["threshold_amount"], 50000.0)
        self.assertEqual(res["previous_ytd"], 60000.0)
        self.assertEqual(res["current_invoice_amount"], 10000.0)
        self.assertEqual(res["projected_ytd"], 70000.0)
        self.assertEqual(res["tds_base_amount"], 10000.0)
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_amount"], 1000.0) # 10% of 10,000
        self.assertTrue(res["applicable"])

    def test_case_e_first_invoice_above_threshold(self):
        """CASE E: Previous YTD = 0 AND Current invoice >= Threshold -> THRESHOLD_CROSSED, TDS base = Current Invoice Subtotal"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=70000.0,
            previous_ytd=0.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["threshold_status"], "THRESHOLD_CROSSED")
        self.assertEqual(res["threshold_amount"], 50000.0)
        self.assertEqual(res["previous_ytd"], 0.0)
        self.assertEqual(res["current_invoice_amount"], 70000.0)
        self.assertEqual(res["projected_ytd"], 70000.0)
        self.assertEqual(res["tds_base_amount"], 70000.0)
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_amount"], 7000.0) # 10% of 70,000
        self.assertTrue(res["applicable"])

    def test_goods_purchase_50l_threshold(self):
        """Goods purchase Section 194Q / 393(1) Table Sl. No. 8(ii) threshold = 5,000,000 (50 Lakhs)"""
        # Case A: Below 50L
        res_below = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 8(ii)]",
            provision="Purchase of Goods",
            nature_of_payment="Purchase of Goods",
            base_amount=500000.0, # 5 Lakhs
            previous_ytd=4000000.0, # 40 Lakhs (Projected 45L < 50L)
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_below["threshold_status"], "BELOW_THRESHOLD")
        self.assertEqual(res_below["threshold_amount"], 5000000.0)
        self.assertEqual(res_below["tds_base_amount"], 0.0)
        self.assertEqual(res_below["tds_amount"], 0.0)

        # Case C: Crossing 50L
        res_cross = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 8(ii)]",
            provision="Purchase of Goods",
            nature_of_payment="Purchase of Goods",
            base_amount=1500000.0, # 15 Lakhs
            previous_ytd=4000000.0, # 40 Lakhs (Projected 55L > 50L)
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_cross["threshold_status"], "THRESHOLD_CROSSED")
        self.assertEqual(res_cross["threshold_amount"], 5000000.0)
        self.assertEqual(res_cross["projected_ytd"], 5500000.0)
        self.assertEqual(res_cross["tds_base_amount"], 5500000.0)
    def test_user_requested_exact_crossing_sequence(self):
        """TEST (User Req 5 & 6): Sequence of invoices crossing threshold and subsequent invoice base"""
        # User Req 5: Historical invoices (5000 + 30000 + 13000 = 48000), current = 5000
        res_cross = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=48000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_cross["previous_ytd"], 48000.0)
        self.assertEqual(res_cross["current_invoice_amount"], 5000.0)
        self.assertEqual(res_cross["projected_ytd"], 53000.0)
        self.assertEqual(res_cross["tds_base_amount"], 53000.0)
        self.assertEqual(res_cross["threshold_status"], "THRESHOLD_CROSSED")

        # User Req 6: Subsequent invoice after threshold crossed (Previous YTD = 53000, new = 4000)
        res_after = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=4000.0,
            previous_ytd=53000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_after["previous_ytd"], 53000.0)
        self.assertEqual(res_after["current_invoice_amount"], 4000.0)
        self.assertEqual(res_after["projected_ytd"], 57000.0)
        self.assertEqual(res_after["tds_base_amount"], 4000.0)
        self.assertEqual(res_after["threshold_status"], "THRESHOLD_ALREADY_CROSSED")

    def test_contractor_single_invoice_vs_aggregate(self):
        """TEST (User Req 8): Contractor Section 194C single-invoice threshold (30,000) vs aggregate (100,000)"""
        # Single invoice 35,000 >= 30,000 triggers TDS even if YTD = 0
        res_single = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(i)]",
            provision="Payments to Contractors",
            nature_of_payment="Work Contracts",
            base_amount=35000.0,
            previous_ytd=0.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertTrue(res_single["applicable"])
        self.assertEqual(res_single["threshold_status"], "SINGLE_INVOICE_THRESHOLD_EXCEEDED")
        self.assertEqual(res_single["tds_base_amount"], 35000.0)

        # Single invoice 25,000 < 30,000 with YTD 40,000 (total 65k < 100k) -> BELOW_THRESHOLD
        res_below = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(i)]",
            provision="Payments to Contractors",
            nature_of_payment="Work Contracts",
            base_amount=25000.0,
            previous_ytd=40000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertFalse(res_below["applicable"])
        self.assertEqual(res_below["threshold_status"], "BELOW_THRESHOLD")
        self.assertEqual(res_below["tds_base_amount"], 0.0)


class TestYTDDatabaseIntegration(unittest.TestCase):
    """Real Database / Integration Test for YTD Query & Invoice Exclusion (User Req 3, 4, 5, 7)"""

    def test_ytd_db_accumulation_and_current_invoice_exclusion(self):
        """
        Integration test executing against SQLite DB session:
        Inserts historical invoices (5000, 30000, 13000 on 2025-05-10)
        Plus a previous FY invoice (20000 on 2025-02-15) and a REJECTED invoice.
        Verifies that current invoice is excluded, previous FY is excluded, and subtotal sum = 48000.
        """
        import uuid
        from datetime import datetime
        from sqlalchemy import create_engine, select, func, cast, Float, or_
        from sqlalchemy.orm import sessionmaker
        from app.db.models import Base, Invoice
        from app.core.date_utils import get_indian_financial_year

        # Register SQLite compilation handler for PostgreSQL JSONB type in unit tests
        from sqlalchemy.ext.compiler import compiles
        from sqlalchemy.dialects.postgresql import JSONB
        @compiles(JSONB, 'sqlite')
        def compile_jsonb_sqlite(type_, compiler, **kw):
            return "JSON"

        # Create in-memory SQLite database engine
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)

        tenant_id = "test-tenant-ytd-001"
        vendor_pan = "ABCDE1234F"
        current_inv_id = uuid.uuid4()

        with Session() as session:
            # 1. Historical invoice 1 (Current FY 2025-26): 5000
            inv1 = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                file_path="/tmp/i1.pdf",
                file_name="i1.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash="h1",
                status="COMPLETED",
                approval_status="APPROVED",
                current_vlm_output={"vendor_pan": vendor_pan, "vendor_name": "Acme Legal", "subtotal": 5000.0, "invoice_date": "2025-05-10"},
                current_accounting_output={"tds_assessment": {"tds_base_amount": 5000.0}},
            )
            # 2. Historical invoice 2 (Current FY 2025-26): 30000
            inv2 = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                file_path="/tmp/i2.pdf",
                file_name="i2.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash="h2",
                status="COMPLETED",
                approval_status="APPROVED",
                current_vlm_output={"vendor_pan": vendor_pan, "vendor_name": "Acme Legal", "subtotal": 30000.0, "invoice_date": "2025-06-15"},
                current_accounting_output={"tds_assessment": {"tds_base_amount": 30000.0}},
            )
            # 3. Historical invoice 3 (Current FY 2025-26): 13000
            inv3 = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                file_path="/tmp/i3.pdf",
                file_name="i3.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash="h3",
                status="COMPLETED",
                approval_status="APPROVED",
                current_vlm_output={"vendor_pan": vendor_pan, "vendor_name": "Acme Legal", "subtotal": 13000.0, "invoice_date": "2025-07-20"},
                current_accounting_output={"tds_assessment": {"tds_base_amount": 13000.0}},
            )
            # 4. Previous FY invoice (2024-25, dated 2025-02-15): 20000 -> SHOULD BE EXCLUDED BY FY FILTER
            inv_prev_fy = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                file_path="/tmp/iprev.pdf",
                file_name="iprev.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash="hprev",
                status="COMPLETED",
                approval_status="APPROVED",
                current_vlm_output={"vendor_pan": vendor_pan, "vendor_name": "Acme Legal", "subtotal": 20000.0, "invoice_date": "2025-02-15"},
                current_accounting_output={"tds_assessment": {"tds_base_amount": 20000.0}},
            )
            # 5. REJECTED invoice (Current FY): 15000 -> SHOULD BE EXCLUDED
            inv_rejected = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                file_path="/tmp/irej.pdf",
                file_name="irej.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash="hrej",
                status="REJECTED",
                approval_status="REJECTED",
                current_vlm_output={"vendor_pan": vendor_pan, "vendor_name": "Acme Legal", "subtotal": 15000.0, "invoice_date": "2025-08-01"},
                current_accounting_output={"tds_assessment": {"tds_base_amount": 15000.0}},
            )
            # 6. Current invoice undergoing stage 5 (Current FY 2025-26): 5000 -> MUST BE EXCLUDED BY ID
            inv_current = Invoice(
                id=current_inv_id,
                tenant_id=tenant_id,
                file_path="/tmp/icur.pdf",
                file_name="icur.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash="hcur",
                status="PROCESSING",
                approval_status="PENDING_REVIEW",
                current_vlm_output={"vendor_pan": vendor_pan, "vendor_name": "Acme Legal", "subtotal": 5000.0, "invoice_date": "2025-09-01"},
                current_accounting_output={},
            )

            session.add_all([inv1, inv2, inv3, inv_prev_fy, inv_rejected, inv_current])
            session.commit()

            # Execute YTD Query matching invoice_processing.py logic
            inv_d = datetime.strptime("2025-09-01", "%Y-%m-%d").date()
            fy_start_year, fy_end_year = get_indian_financial_year(inv_d)
            fy_start_str = f"{fy_start_year}-04-01"
            fy_end_str = f"{fy_end_year}-03-31"

            subtotal_expr = func.coalesce(
                cast(func.json_extract(Invoice.current_vlm_output, '$.subtotal'), Float),
                0.0
            )
            inv_date_expr = func.coalesce(
                func.json_extract(Invoice.current_vlm_output, '$.invoice_date'),
                func.strftime('%Y-%m-%d', Invoice.created_at)
            )

            ytd_query = (
                select(func.coalesce(func.sum(subtotal_expr), 0.0))
                .where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.id != current_inv_id,
                    Invoice.status != "REJECTED",
                    Invoice.approval_status != "REJECTED",
                    inv_date_expr >= fy_start_str,
                    inv_date_expr <= fy_end_str,
                    func.json_extract(Invoice.current_vlm_output, '$.vendor_pan') == vendor_pan
                )
            )
            res = session.execute(ytd_query)
            previous_ytd = float(res.scalar() or 0.0)

            # Verification assertions
            self.assertEqual(previous_ytd, 48000.0) # 5000 + 30000 + 13000

            # Calculate TDS for current invoice (5000)
            tds_res = tds_engine.calculate_tds(
                applicable=True,
                section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]", # 10%, threshold 50,000
                provision="Professional Services",
                nature_of_payment="Legal Consultation",
                base_amount=5000.0,
                previous_ytd=previous_ytd,
                vendor_pan=vendor_pan,
            )
            self.assertEqual(tds_res["previous_ytd"], 48000.0)
            self.assertEqual(tds_res["current_invoice_amount"], 5000.0)
            self.assertEqual(tds_res["projected_ytd"], 53000.0)
            self.assertEqual(tds_res["tds_base_amount"], 53000.0)
            self.assertEqual(tds_res["tds_amount"], 5300.0) # 10% of 53,000


if __name__ == "__main__":
    unittest.main()

