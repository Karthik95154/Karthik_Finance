import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


def get_effective_tds_data(accounting: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Single source of truth for statutory TDS assessment across display, validation, journal, and export.
    Prioritizes tds_assessment (authoritative current assessment) over legacy keys.
    If tds_assessment is present, its tds_applicable flag strictly governs.
    """
    if not accounting or not isinstance(accounting, dict):
        return {
            "applicable": False,
            "section": None,
            "provision": None,
            "nature_of_payment": None,
            "rate": None,
            "base_amount": None,
            "tds_amount": None,
            "reasoning": None,
            "is_approved": False,
            "approval_status": "PENDING",
        }

    # 1. Authoritative assessment source (tds_assessment)
    tds_assessment = accounting.get("tds_assessment")
    if isinstance(tds_assessment, dict):
        raw_app = tds_assessment.get("tds_applicable")
        if raw_app is None and "applicable" in tds_assessment:
            raw_app = tds_assessment.get("applicable")
        is_app = bool(raw_app) if raw_app is not None else False

        rate_val = (
            tds_assessment.get("approved_tds_rate")
            or tds_assessment.get("tds_rate")
            or tds_assessment.get("rate")
        )
        try:
            rate_float = float(rate_val) if rate_val is not None else None
        except (ValueError, TypeError):
            rate_float = None

        base_val = (
            tds_assessment.get("tds_base_amount")
            or tds_assessment.get("base_amount")
        )
        try:
            base_float = float(base_val) if base_val is not None else None
        except (ValueError, TypeError):
            base_float = None

        tds_amt_val = (
            tds_assessment.get("final_tds_amount")
            or tds_assessment.get("calculated_tds_amount")
            or tds_assessment.get("proposed_tds_amount")
            or tds_assessment.get("tds_amount")
            or tds_assessment.get("amount")
        )
        try:
            tds_amt_float = float(tds_amt_val) if tds_amt_val is not None else None
        except (ValueError, TypeError):
            tds_amt_float = None

        is_appr = bool(
            tds_assessment.get("is_approved")
            or tds_assessment.get("approved")
            or tds_assessment.get("approval_status") == "APPROVED"
        )

        return {
            "applicable": is_app,
            "section": tds_assessment.get("approved_tds_section") or tds_assessment.get("tds_section") or tds_assessment.get("section"),
            "provision": tds_assessment.get("approved_tds_provision") or tds_assessment.get("tds_provision") or tds_assessment.get("provision"),
            "nature_of_payment": tds_assessment.get("approved_nature_of_payment") or tds_assessment.get("nature_of_payment") or tds_assessment.get("nature"),
            "rate": rate_float if is_app else None,
            "base_amount": base_float if is_app else None,
            "tds_amount": tds_amt_float if is_app else None,
            "reasoning": tds_assessment.get("tds_reasoning") or tds_assessment.get("reason"),
            "is_approved": is_appr,
            "approval_status": "APPROVED" if is_appr else "PENDING",
        }

    # 2. Fallback to legacy tds only if tds_assessment is completely absent
    legacy_tds = accounting.get("tds")
    if isinstance(legacy_tds, dict):
        raw_app = legacy_tds.get("applicable") if "applicable" in legacy_tds else legacy_tds.get("tds_applicable")
        is_app = bool(raw_app) if raw_app is not None else False
        rate_val = (
            legacy_tds.get("approved_tds_rate")
            or legacy_tds.get("tds_rate")
            or legacy_tds.get("rate")
        )
        try:
            rate_float = float(rate_val) if rate_val is not None else None
        except (ValueError, TypeError):
            rate_float = None

        base_val = (
            legacy_tds.get("tds_base_amount")
            or legacy_tds.get("base_amount")
        )
        try:
            base_float = float(base_val) if base_val is not None else None
        except (ValueError, TypeError):
            base_float = None

        tds_amt_val = (
            legacy_tds.get("final_tds_amount")
            or legacy_tds.get("calculated_tds_amount")
            or legacy_tds.get("proposed_tds_amount")
            or legacy_tds.get("tds_amount")
            or legacy_tds.get("amount")
        )
        try:
            tds_amt_float = float(tds_amt_val) if tds_amt_val is not None else None
        except (ValueError, TypeError):
            tds_amt_float = None

        is_appr = bool(
            legacy_tds.get("is_approved")
            or legacy_tds.get("approved")
            or legacy_tds.get("approval_status") == "APPROVED"
        )

        return {
            "applicable": is_app,
            "section": legacy_tds.get("approved_tds_section") or legacy_tds.get("tds_section") or legacy_tds.get("section"),
            "provision": legacy_tds.get("approved_tds_provision") or legacy_tds.get("tds_provision") or legacy_tds.get("provision"),
            "nature_of_payment": legacy_tds.get("approved_nature_of_payment") or legacy_tds.get("nature_of_payment") or legacy_tds.get("nature"),
            "rate": rate_float if is_app else None,
            "base_amount": base_float if is_app else None,
            "tds_amount": tds_amt_float if is_app else None,
            "reasoning": legacy_tds.get("tds_reasoning") or legacy_tds.get("reason"),
            "is_approved": is_appr,
            "approval_status": "APPROVED" if is_appr else "PENDING",
        }

    return {
        "applicable": False,
        "section": None,
        "provision": None,
        "nature_of_payment": None,
        "rate": None,
        "base_amount": None,
        "tds_amount": None,
        "reasoning": None,
        "is_approved": False,
        "approval_status": "PENDING",
    }


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
        applicable: Optional[bool] = None,
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
        If applicable is False, strictly returns TDS not applicable with 0.0 amounts.
        If applicable is None and no section/rate is specified, defaults to not applicable.
        """
        if applicable is False or base_amount <= 0 or (rate is None and not section and not provision and not nature_of_payment):
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

        # If applicable is unspecified (None) and rate is 0 or None with no section/provision, not applicable
        if applicable is None and (rate is None or rate == 0.0) and not section and not provision:
            return {
                "applicable": False,
                "provision": provision,
                "section": section,
                "nature_of_payment": nature_of_payment,
                "rate": 0.0,
                "base_amount": 0.0,
                "tds_amount": 0.0,
                "reason": "TDS not applicable",
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


