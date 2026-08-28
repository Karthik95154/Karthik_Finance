import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


class TDSEngine:
    """
    Deterministic Indian Income Tax TDS (Tax Deducted at Source) calculation engine.
    Calculates statutory deductions, section rates, and PAN-linked higher deduction rates.
    """

    @staticmethod
    def is_valid_pan(pan: Optional[str]) -> bool:
        """Validates 10-character Indian Permanent Account Number (PAN) format."""
        if not pan or not isinstance(pan, str):
            return False
        return bool(PAN_PATTERN.fullmatch(pan.strip().upper()))

    @staticmethod
    def is_individual_or_huf(pan: Optional[str]) -> bool:
        """
        In Indian PAN syntax, the 4th character represents entity type:
        - 'P': Individual
        - 'H': Hindu Undivided Family (HUF)
        - 'C': Company
        - 'F': Firm / LLP
        """
        if not pan or len(pan.strip()) < 4:
            return False
        fourth_char = pan.strip().upper()[3]
        return fourth_char in ("P", "H")

    @classmethod
    def calculate_tds(
        cls,
        section: Optional[str],
        base_amount: float,
        vendor_pan: Optional[str] = None,
        is_subcontractor: bool = False,
        is_tech_service: bool = True,  # Section 194J(FTS) 2% vs Professional Fees 10%
    ) -> Dict[str, Any]:
        """
        Computes statutory TDS amount according to Indian Income Tax rules.
        """
        if not section or base_amount <= 0:
            return {
                "applicable": False,
                "section": None,
                "rate": 0.0,
                "base_amount": 0.0,
                "tds_amount": 0.0,
                "reason": "TDS not applicable or zero base amount",
            }

        clean_section = section.strip().upper().replace("SECTION", "").replace("SEC", "").strip()
        pan_valid = cls.is_valid_pan(vendor_pan)
        individual = cls.is_individual_or_huf(vendor_pan)

        rate: float = 0.0
        reason: str = ""

        # Higher deduction for invalid PAN (Section 206AA)
        if not pan_valid:
            rate = 20.0
            reason = f"Section 206AA higher deduction (20%) applied due to invalid or missing vendor PAN."
        else:
            if "194C" in clean_section:
                # 194C: Contractors -> 1% for Individual/HUF, 2% for Others
                rate = 1.0 if individual else 2.0
                reason = f"Section 194C ({rate}%) for {'Individual/HUF' if individual else 'Company/Firm'}"

            elif "194J" in clean_section:
                # 194J: 2% for Technical Services (FTS) / Royalty, 10% for Professional Fees
                rate = 2.0 if is_tech_service else 10.0
                reason = f"Section 194J ({rate}%) for {'Fees for Technical Services (FTS)' if is_tech_service else 'Professional Services'}"

            elif "194I" in clean_section:
                # 194I: 2% for Plant & Machinery, 10% for Land/Building/Furniture
                rate = 2.0 if is_subcontractor else 10.0
                reason = f"Section 194I ({rate}%) for Rent"

            elif "194H" in clean_section:
                # 194H: Commission or Brokerage (2% / 5%)
                rate = 2.0
                reason = f"Section 194H (2%) for Commission / Brokerage"

            elif "194Q" in clean_section:
                # 194Q: Purchase of Goods (0.1%)
                rate = 0.1
                reason = f"Section 194Q (0.1%) for Purchase of Goods"

            else:
                rate = 2.0
                reason = f"Standard default statutory rate (2%) for Section {clean_section}"

        tds_amount = round((base_amount * rate) / 100.0, 2)

        return {
            "applicable": True,
            "section": clean_section,
            "rate": rate,
            "base_amount": round(base_amount, 2),
            "tds_amount": tds_amount,
            "pan_valid": pan_valid,
            "reason": reason,
        }


tds_engine = TDSEngine()
