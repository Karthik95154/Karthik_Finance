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
        section: Optional[str] = None,
        base_amount: float = 0.0,
        rate: Optional[float] = None,
        provision: Optional[str] = None,
        nature_of_payment: Optional[str] = None,
        vendor_pan: Optional[str] = None,
        is_subcontractor: bool = False,
        is_tech_service: bool = True,
    ) -> Dict[str, Any]:
        """
        Computes statutory TDS amount according to Indian Income Tax rules.
        Uses first-rupee calculation against invoice subtotal (no YTD or minimum threshold logic).
        If an explicit approved rate is passed, it is respected as the authoritative rate.
        Preserves AI assessment metadata (provision, section, nature of payment).
        """
        if base_amount <= 0 or (rate is None and not section and not provision and not nature_of_payment):
            return {
                "applicable": False,
                "provision": provision,
                "section": section,
                "nature_of_payment": nature_of_payment,
                "rate": 0.0,
                "base_amount": 0.0,
                "tds_amount": 0.0,
                "reason": "TDS not applicable or zero base amount",
            }

        pan_valid = cls.is_valid_pan(vendor_pan) if vendor_pan else True
        individual = cls.is_individual_or_huf(vendor_pan)

        computed_rate: float = 0.0
        reason: str = ""

        if rate is not None and float(rate) > 0:
            computed_rate = float(rate)
            label = nature_of_payment or section or provision or "TDS"
            reason = f"Authoritative TDS rate ({computed_rate}%) applied to subtotal for {label}."
        else:
            sec_str = (f"{provision or ''} {section or ''} {nature_of_payment or ''}").upper()
            if vendor_pan and not pan_valid:
                computed_rate = 20.0
                reason = "Section 206AA higher deduction (20%) applied due to invalid vendor PAN."
            elif "CONTRACT" in sec_str or "194C" in sec_str:
                computed_rate = 1.0 if individual else 2.0
                reason = f"Contractor TDS ({computed_rate}%) for {'Individual/HUF' if individual else 'Company/Firm'}"
            elif "PROFESSIONAL" in sec_str or "393" in sec_str or "194J" in sec_str:
                computed_rate = 2.0 if is_tech_service else 10.0
                reason = f"Professional/Technical TDS ({computed_rate}%) for {nature_of_payment or 'Professional services'}"
            elif "RENT" in sec_str or "194I" in sec_str:
                computed_rate = 2.0 if is_subcontractor else 10.0
                reason = f"Rent TDS ({computed_rate}%)"
            elif "COMMISSION" in sec_str or "194H" in sec_str:
                computed_rate = 2.0
                reason = "Commission / Brokerage TDS (2%)"
            elif "PURCHASE" in sec_str or "194Q" in sec_str:
                computed_rate = 0.1
                reason = "Purchase of Goods TDS (0.1%)"
            else:
                computed_rate = 10.0 if "PROFESSIONAL" in (nature_of_payment or "").upper() else 2.0
                reason = f"Statutory TDS ({computed_rate}%) for {nature_of_payment or 'Services'}"

        # TDS is strictly calculated on base_amount (Subtotal), NEVER on subtotal + GST
        tds_amount = round((base_amount * computed_rate) / 100.0, 2)

        return {
            "applicable": True,
            "provision": provision,
            "section": section,
            "nature_of_payment": nature_of_payment,
            "rate": computed_rate,
            "base_amount": round(base_amount, 2),
            "tds_amount": tds_amount,
            "pan_valid": pan_valid,
            "reason": reason,
        }


tds_engine = TDSEngine()


