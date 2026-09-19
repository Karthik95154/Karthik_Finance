"""
Focused Unit Tests for BUG-01: Single Source of Truth Statutory TDS Rate Resolution
"""
import unittest
from app.services.tds_engine import tds_engine, STATUTORY_TDS_TABLE_2025
from app.services.model_response_adapter import ModelResponseAdapter

class TestTdsRateResolution(unittest.TestCase):

    def test_contractor_rate_resolution(self):
        """TEST 1: Contractor / Work contract statutory rate resolution"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(i)]",
            provision="Payments to Contractors",
            nature_of_payment="Work contract",
            base_amount=100000.0,
            rate=None,
            vendor_pan="ABCDE1234F", # Firm/Company PAN (4th char 'E' / 'F') -> 2%
        )
        self.assertEqual(res["rate"], 2.0)
        self.assertEqual(res["tds_amount"], 2000.0)

        # Individual contractor (1%)
        res_indiv = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(i)]",
            provision="Payments to Contractors (Individual/HUF)",
            nature_of_payment="Work contract",
            base_amount=100000.0,
            rate=None,
            vendor_pan="ABCDP1234F", # Individual PAN (4th char 'P') -> 1%
        )
        self.assertEqual(res_indiv["rate"], 1.0)
        self.assertEqual(res_indiv["tds_amount"], 1000.0)

    def test_professional_services_rate_resolution(self):
        """TEST 2: Professional service statutory rate resolution (10%)"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(b)]",
            provision="Professional Services & Fees",
            nature_of_payment="Legal Consultation",
            base_amount=50000.0,
            rate=None,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 10.0)
        self.assertEqual(res["tds_amount"], 5000.0)

        # Technical services / FTS (2%)
        res_fts = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 6(iii)(D)(a)]",
            provision="Fees for Technical Services",
            nature_of_payment="Cloud Infrastructure & Software",
            base_amount=50000.0,
            rate=None,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_fts["rate"], 2.0)
        self.assertEqual(res_fts["tds_amount"], 1000.0)

    def test_rent_rate_resolution(self):
        """TEST 3: Rent statutory rate resolution (10% immovable / 2% plant & machinery)"""
        res_immovable = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 2(ii)]",
            provision="Rent for Land, Building or Furniture",
            nature_of_payment="Office Premises Rent",
            base_amount=600000.0,
            rate=None,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_immovable["rate"], 10.0)
        self.assertEqual(res_immovable["tds_amount"], 60000.0)

        res_equipment = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 2(ii)]",
            provision="Rent for Plant, Machinery or Equipment",
            nature_of_payment="CCTV Equipment Hiring",
            base_amount=600000.0,
            rate=None,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res_equipment["rate"], 2.0)
        self.assertEqual(res_equipment["tds_amount"], 12000.0)

    def test_goods_purchase_rate_resolution(self):
        """TEST 4: Goods purchase statutory rate resolution (0.1%)"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section="Section 393(1) [Table Sl. No. 8(ii)]",
            provision="Purchase of Goods",
            nature_of_payment="Purchase of Goods",
            base_amount=6000000.0,
            rate=None,
            vendor_pan="ABCDE1234F",
        )
        self.assertEqual(res["rate"], 0.1)
        self.assertEqual(res["tds_amount"], 6000.0)

    def test_unknown_category_no_fallback(self):
        """TEST 5: Unknown/unclassified TDS category does NOT fallback to 2%"""
        res = tds_engine.calculate_tds(
            applicable=True,
            section=None,
            provision=None,
            nature_of_payment="Unidentified Custom Miscellaneous Service",
            base_amount=50000.0,
            rate=None,
            vendor_pan="ABCDE1234F",
        )
        self.assertIsNone(res["rate"])
        self.assertIsNone(res["tds_amount"])
        self.assertTrue(res["tds_needs_review"])
        self.assertEqual(res["tds_conflict_code"], "TDS_AMBIGUOUS_SAC")

if __name__ == "__main__":
    unittest.main()
