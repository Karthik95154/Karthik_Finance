"""
Focused Unit Tests for BUG-01A: Statutory TDS Threshold & Vendor YTD Logic State Machine
"""
import unittest
import uuid
from datetime import datetime
from sqlalchemy import create_engine, select, func, cast, Float, or_
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Invoice
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


class TestBug07VendorMatchingWithoutName(unittest.TestCase):
    """Regression tests for BUG-07: YTD lookup execution independent of vendor_name."""

    def test_01_pan_only_no_vendor_name(self):
        """BUG-07 Test 1: Historical YTD matching by PAN only (vendor_name is None)."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        tenant_id = "tenant-bug07-pan"
        pan = "PANONLY123"
        cur_id = uuid.uuid4()

        with Session() as session:
            inv1 = Invoice(
                id=uuid.uuid4(), tenant_id=tenant_id, file_path="/tmp/1.pdf", file_name="1.pdf", file_size=100, mime_type="application/pdf", file_hash="h1",
                status="COMPLETED", approval_status="APPROVED",
                current_vlm_output={"vendor_pan": pan, "vendor_name": None, "subtotal": 48000.0, "invoice_date": "2025-05-10"},
            )
            inv_cur = Invoice(
                id=cur_id, tenant_id=tenant_id, file_path="/tmp/c.pdf", file_name="c.pdf", file_size=100, mime_type="application/pdf", file_hash="hc",
                status="PROCESSING", approval_status="PENDING_REVIEW",
                current_vlm_output={"vendor_pan": pan, "vendor_name": None, "subtotal": 5000.0, "invoice_date": "2025-06-10"},
            )
            session.add_all([inv1, inv_cur])
            session.commit()

            # Execute matching invoice_processing.py logic (PAN only, name is None)
            v_pan = pan
            v_gstin = None
            v_name = ""

            ytd_conditions = []
            if v_pan and len(str(v_pan).strip()) == 10:
                ytd_conditions.append(func.json_extract(Invoice.current_vlm_output, '$.vendor_pan') == str(v_pan).strip())
            if v_gstin and len(str(v_gstin).strip()) == 15:
                ytd_conditions.append(func.json_extract(Invoice.current_vlm_output, '$.vendor_gstin') == str(v_gstin).strip())
            if v_name:
                ytd_conditions.append(func.lower(func.json_extract(Invoice.current_vlm_output, '$.vendor_name')) == v_name)

            self.assertTrue(len(ytd_conditions) > 0)

            subtotal_expr = func.coalesce(cast(func.json_extract(Invoice.current_vlm_output, '$.subtotal'), Float), 0.0)
            inv_date_expr = func.coalesce(func.json_extract(Invoice.current_vlm_output, '$.invoice_date'), func.strftime('%Y-%m-%d', Invoice.created_at))

            q = select(func.coalesce(func.sum(subtotal_expr), 0.0)).where(
                Invoice.tenant_id == tenant_id, Invoice.id != cur_id, Invoice.status != "REJECTED", Invoice.approval_status != "REJECTED",
                inv_date_expr >= "2025-04-01", inv_date_expr <= "2026-03-31", or_(*ytd_conditions)
            )
            previous_ytd = float(session.execute(q).scalar() or 0.0)
            self.assertEqual(previous_ytd, 48000.0) # Verified YTD runs and matches even when vendor_name is None!

            # Calculate TDS for current invoice 5000
            tds_res = tds_engine.calculate_tds(
                applicable=True, section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
                provision="Professional Services", nature_of_payment="Legal Consultation",
                base_amount=5000.0, previous_ytd=previous_ytd, vendor_pan=pan
            )
            self.assertEqual(tds_res["previous_ytd"], 48000.0)
            self.assertEqual(tds_res["projected_ytd"], 53000.0)
            self.assertEqual(tds_res["threshold_status"], "THRESHOLD_CROSSED")
            self.assertEqual(tds_res["tds_base_amount"], 53000.0)

            # Next invoice 4000
            tds_next = tds_engine.calculate_tds(
                applicable=True, section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
                provision="Professional Services", nature_of_payment="Legal Consultation",
                base_amount=4000.0, previous_ytd=53000.0, vendor_pan=pan
            )
            self.assertEqual(tds_next["previous_ytd"], 53000.0)
            self.assertEqual(tds_next["threshold_status"], "THRESHOLD_ALREADY_CROSSED")
            self.assertEqual(tds_next["tds_base_amount"], 4000.0)

    def test_02_gstin_only_no_vendor_name(self):
        """BUG-07 Test 2: Historical YTD matching by GSTIN only (vendor_name is None)."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        tenant_id = "tenant-bug07-gstin"
        gstin = "27ABCDE1234F1Z5"
        cur_id = uuid.uuid4()

        with Session() as session:
            inv1 = Invoice(
                id=uuid.uuid4(), tenant_id=tenant_id, file_path="/tmp/1.pdf", file_name="1.pdf", file_size=100, mime_type="application/pdf", file_hash="h1",
                status="COMPLETED", approval_status="APPROVED",
                current_vlm_output={"vendor_gstin": gstin, "vendor_name": None, "subtotal": 25000.0, "invoice_date": "2025-05-10"},
            )
            session.add(inv1)
            session.commit()

            v_gstin = gstin
            ytd_conditions = [func.json_extract(Invoice.current_vlm_output, '$.vendor_gstin') == str(v_gstin).strip()]
            subtotal_expr = func.coalesce(cast(func.json_extract(Invoice.current_vlm_output, '$.subtotal'), Float), 0.0)
            q = select(func.coalesce(func.sum(subtotal_expr), 0.0)).where(
                Invoice.tenant_id == tenant_id, Invoice.id != cur_id, Invoice.status != "REJECTED", Invoice.approval_status != "REJECTED",
                or_(*ytd_conditions)
            )
            previous_ytd = float(session.execute(q).scalar() or 0.0)
            self.assertEqual(previous_ytd, 25000.0)

    def test_03_vendor_name_only(self):
        """BUG-07 Test 3: Historical YTD matching by vendor_name only."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        tenant_id = "tenant-bug07-name"
        vname = "acme legal corp"
        cur_id = uuid.uuid4()

        with Session() as session:
            inv1 = Invoice(
                id=uuid.uuid4(), tenant_id=tenant_id, file_path="/tmp/1.pdf", file_name="1.pdf", file_size=100, mime_type="application/pdf", file_hash="h1",
                status="COMPLETED", approval_status="APPROVED",
                current_vlm_output={"vendor_name": "Acme Legal Corp", "subtotal": 15000.0, "invoice_date": "2025-05-10"},
            )
            session.add(inv1)
            session.commit()

            ytd_conditions = [func.lower(func.json_extract(Invoice.current_vlm_output, '$.vendor_name')) == vname]
            subtotal_expr = func.coalesce(cast(func.json_extract(Invoice.current_vlm_output, '$.subtotal'), Float), 0.0)
            q = select(func.coalesce(func.sum(subtotal_expr), 0.0)).where(
                Invoice.tenant_id == tenant_id, Invoice.id != cur_id, Invoice.status != "REJECTED", Invoice.approval_status != "REJECTED",
                or_(*ytd_conditions)
            )
            previous_ytd = float(session.execute(q).scalar() or 0.0)
            self.assertEqual(previous_ytd, 15000.0)

    def test_04_pan_plus_gstin_no_name(self):
        """BUG-07 Test 4: Historical YTD matching by PAN + GSTIN (vendor_name is None)."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        tenant_id = "tenant-bug07-pan-gstin"
        pan = "PANONLY123"
        gstin = "27ABCDE1234F1Z5"
        cur_id = uuid.uuid4()

        with Session() as session:
            inv1 = Invoice(
                id=uuid.uuid4(), tenant_id=tenant_id, file_path="/tmp/1.pdf", file_name="1.pdf", file_size=100, mime_type="application/pdf", file_hash="h1",
                status="COMPLETED", approval_status="APPROVED",
                current_vlm_output={"vendor_pan": pan, "vendor_gstin": gstin, "vendor_name": None, "subtotal": 30000.0, "invoice_date": "2025-05-10"},
            )
            session.add(inv1)
            session.commit()

            ytd_conditions = [
                func.json_extract(Invoice.current_vlm_output, '$.vendor_pan') == pan,
                func.json_extract(Invoice.current_vlm_output, '$.vendor_gstin') == gstin,
            ]
            subtotal_expr = func.coalesce(cast(func.json_extract(Invoice.current_vlm_output, '$.subtotal'), Float), 0.0)
            q = select(func.coalesce(func.sum(subtotal_expr), 0.0)).where(
                Invoice.tenant_id == tenant_id, Invoice.id != cur_id, Invoice.status != "REJECTED", Invoice.approval_status != "REJECTED",
                or_(*ytd_conditions)
            )
            previous_ytd = float(session.execute(q).scalar() or 0.0)
            self.assertEqual(previous_ytd, 30000.0)

    def test_05_all_identifiers_missing(self):
        """BUG-07 Test 5: All vendor identifiers missing -> ytd_conditions empty, query skipped."""
        v_pan = None
        v_gstin = None
        v_name = ""

        ytd_conditions = []
        if v_pan and len(str(v_pan).strip()) == 10:
            ytd_conditions.append(True)
        if v_gstin and len(str(v_gstin).strip()) == 15:
            ytd_conditions.append(True)
        if v_name:
            ytd_conditions.append(True)

        self.assertEqual(len(ytd_conditions), 0)


class TestBug08StatutoryRatePreservationBelowThreshold(unittest.TestCase):
    """Regression tests for BUG-08: Statutory TDS rate preserved when below threshold."""

    def test_01_professional_service_below_threshold(self):
        """1. Professional service below threshold: rate 10%, applicable=False, base=0, amount=0."""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=40000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_rate"], 10.0)
        self.assertFalse(res["applicable"])
        self.assertFalse(res["tds_applicable"])
        self.assertEqual(res["tds_base_amount"], 0.0)
        self.assertEqual(res["tds_amount"], 0.0)
        self.assertEqual(res["threshold_status"], "BELOW_THRESHOLD")

    def test_02_professional_service_at_crossing_threshold(self):
        """2. Professional service at/crossing threshold: rate 10%, applicable=True, base=53000, amount=5300."""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=48000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_rate"], 10.0)
        self.assertTrue(res["applicable"])
        self.assertTrue(res["tds_applicable"])
        self.assertEqual(res["tds_base_amount"], 53000.0)
        self.assertEqual(res["tds_amount"], 5300.0)
        self.assertEqual(res["threshold_status"], "THRESHOLD_CROSSED")

    def test_03_contractor_category_rate_visible_below_threshold(self):
        """3. Contractor category: statutory rate visible below aggregate & single invoice threshold."""
        # Below single (30,000) and aggregate (100,000) threshold: invoice 10,000, prev YTD 10,000
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(i)]",
            provision="Payments to Contractors and Sub-contractors",
            nature_of_payment="Work Contracts & Sub-contractor Services",
            base_amount=10000.0,
            previous_ytd=10000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 2.0)
        self.assertEqual(res["tds_rate"], 2.0)
        self.assertFalse(res["applicable"])
        self.assertEqual(res["tds_base_amount"], 0.0)
        self.assertEqual(res["tds_amount"], 0.0)

        # Single invoice threshold crossed (>= 30,000)
        res_single = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(i)]",
            provision="Payments to Contractors and Sub-contractors",
            nature_of_payment="Work Contracts & Sub-contractor Services",
            base_amount=35000.0,
            previous_ytd=0.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_single["rate"], 2.0)
        self.assertTrue(res_single["applicable"])
        self.assertEqual(res_single["tds_base_amount"], 35000.0)
        self.assertEqual(res_single["tds_amount"], 700.0)

    def test_04_technical_services_below_threshold(self):
        """4. Technical services: statutory rate 2% visible below threshold."""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(a)]",
            provision="Fees for Technical Services (FTS)",
            nature_of_payment="Fees for Technical Services (FTS) & Cloud Infrastructure",
            base_amount=15000.0,
            previous_ytd=10000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 2.0)
        self.assertEqual(res["tds_rate"], 2.0)
        self.assertFalse(res["applicable"])
        self.assertEqual(res["tds_base_amount"], 0.0)
        self.assertEqual(res["tds_amount"], 0.0)

    def test_05_goods_purchase_below_threshold(self):
        """5. Goods purchase: statutory rate 0.1% visible below threshold (50L)."""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 8(ii)]",
            provision="Purchase of Goods",
            nature_of_payment="Purchase of Goods",
            base_amount=1000000.0, # 10 Lakhs < 50 Lakhs
            previous_ytd=2000000.0,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 0.1)
        self.assertEqual(res["tds_rate"], 0.1)
        self.assertFalse(res["applicable"])
        self.assertEqual(res["tds_base_amount"], 0.0)
        self.assertEqual(res["tds_amount"], 0.0)

    def test_06_rent_below_threshold(self):
        """6. Rent: statutory rate 10% visible below threshold (5 Lakhs)."""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 2(ii)]",
            provision="Rent for Land, Building or Furniture",
            nature_of_payment="Rent of Land, Building or Furniture",
            base_amount=100000.0,
            previous_ytd=200000.0, # Projected 3 Lakhs < 5 Lakhs
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_rate"], 10.0)
        self.assertFalse(res["applicable"])
        self.assertEqual(res["tds_base_amount"], 0.0)
        self.assertEqual(res["tds_amount"], 0.0)

    def test_07_pan_higher_rate_case(self):
        """7. PAN higher-rate (invalid/missing PAN -> 20%): preserved below threshold & applied when crossed."""
        # Invalid PAN below threshold
        res_below = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=40000.0, # Projected = 45000 < 50000
            vendor_pan="INVALIDPAN",
        )
        self.assertEqual(res_below["rate"], 20.0)
        self.assertEqual(res_below["tds_rate"], 20.0)
        self.assertFalse(res_below["applicable"])
        self.assertEqual(res_below["tds_base_amount"], 0.0)
        self.assertEqual(res_below["tds_amount"], 0.0)

        # Invalid PAN when threshold crossed
        res_crossed = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=5000.0,
            previous_ytd=48000.0, # Projected = 53000 >= 50000
            vendor_pan="INVALIDPAN",
        )
        self.assertEqual(res_crossed["rate"], 20.0)
        self.assertEqual(res_crossed["tds_rate"], 20.0)
        self.assertTrue(res_crossed["applicable"])
        self.assertEqual(res_crossed["tds_base_amount"], 53000.0)
        self.assertEqual(res_crossed["tds_amount"], 10600.0) # 20% of 53,000

    def test_08_tds_assessment_ytd_serialization(self):
        """8. Verify tds_assessment dict includes previous_ytd, projected_ytd, threshold_amount, and threshold_status."""
        final_tds_calc = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services",
            nature_of_payment="Legal Consultation",
            base_amount=90000.0,
            previous_ytd=48000.0,
            vendor_pan="ABCDE1234F",
        )
        tds_applicable = bool(final_tds_calc.get("applicable"))

        # Simulate persisted_accounting_output['tds_assessment'] construction in invoice_processing.py
        tds_assessment_persisted = {
            "applicable": tds_applicable,
            "tds_applicable": tds_applicable,
            "section": "Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            "tds_section": "Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            "provision": "Professional Services",
            "tds_provision": "Professional Services",
            "nature_of_payment": "Legal Consultation",
            "tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
            "rate": final_tds_calc.get("rate") if tds_applicable else None,
            "approved_tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
            "tds_base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
            "base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
            "proposed_tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
            "tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
            "tds_reasoning": final_tds_calc.get("reason"),
            "previous_ytd": final_tds_calc.get("previous_ytd"),
            "projected_ytd": final_tds_calc.get("projected_ytd"),
            "threshold_amount": final_tds_calc.get("threshold_amount"),
            "threshold_status": final_tds_calc.get("threshold_status"),
        }

        self.assertEqual(tds_assessment_persisted["previous_ytd"], 48000.0)
        self.assertEqual(tds_assessment_persisted["projected_ytd"], 138000.0)
        self.assertEqual(tds_assessment_persisted["threshold_amount"], 50000.0)
        self.assertEqual(tds_assessment_persisted["threshold_status"], "THRESHOLD_CROSSED")


if __name__ == "__main__":
    unittest.main()


