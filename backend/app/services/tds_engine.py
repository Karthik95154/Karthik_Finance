import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


def parse_vendor_declared_tds(
    text_sources: Optional[List[Any]] = None,
    base_amount: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministic generic parser for explicit vendor-declared TDS declarations
    found in invoice text, terms, footnotes, or model textual notes.
    Extracts statements such as:
      - 'We have booked TDS amount Rs. 31.08...'
      - 'TDS deducted Rs. 500...'
      - 'TDS @ 1%' or 'TDS rate 2%'
      - 'TDS withheld amount Rs. 100...'
    Does not hardcode any vendor name, invoice number, or amount.
    """
    empty_result = {
        "present": False,
        "amount": None,
        "rate": None,
        "derived_rate": None,
        "raw_text": None,
    }
    if not text_sources:
        return empty_result

    lines: List[str] = []
    for src in text_sources:
        if not src:
            continue
        if isinstance(src, str):
            lines.extend(src.splitlines())
        elif isinstance(src, list):
            for item in src:
                if isinstance(item, str):
                    lines.extend(item.splitlines())

    p_amt_booked = re.compile(
        r"(?:(?:we\s+have\s+)?(?:booked|deducted|withheld|deposited)|(?:please\s+)?(?:book|deduct))\s+tds\s+(?:amount\s+)?(?:of\s+)?(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    p_tds_amt_action = re.compile(
        r"tds\s+(?:(?:booked|deducted|withheld|deposited)\s+)?(?:amount\s+)?(?:of\s+)?(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)(?:\s*(?:has\s+been\s+)?(?:booked|deducted|withheld|deposited))?",
        re.IGNORECASE,
    )
    p_tds_rate_explicit = re.compile(
        r"tds\s*(?:@|at|\b(?:rate|percentage)\b)?\s*([0-9]+(?:\.[0-9]+)?)\s*%",
        re.IGNORECASE,
    )
    p_tds_deducted_rate = re.compile(
        r"tds\s+(?:deducted|booked|withheld)\s*@\s*([0-9]+(?:\.[0-9]+)?)\s*%",
        re.IGNORECASE,
    )

    found_amt: Optional[float] = None
    found_rate: Optional[float] = None
    matched_line: Optional[str] = None

    for raw_l in lines:
        l = raw_l.strip()
        if not l or "tds" not in l.lower():
            continue

        # Check explicit rate first
        m_rate = p_tds_deducted_rate.search(l) or p_tds_rate_explicit.search(l)
        if m_rate:
            try:
                r_val = float(m_rate.group(1))
                if 0.01 <= r_val <= 30.0:
                    found_rate = r_val
                    matched_line = l
            except Exception:
                pass

        # Check explicit amount
        m_amt = p_amt_booked.search(l) or p_tds_amt_action.search(l)
        if m_amt:
            try:
                a_str = m_amt.group(1).replace(",", "")
                a_val = float(a_str)
                if a_val > 0:
                    found_amt = round(a_val, 2)
                    matched_line = l
            except Exception:
                pass

        if found_amt is not None or found_rate is not None:
            break

    if found_amt is None and found_rate is None:
        return empty_result

    derived_rate = None
    if found_rate is not None:
        pass
    elif found_amt is not None and base_amount and base_amount > 0:
        raw_calc = (found_amt / base_amount) * 100.0
        derived_rate = round(raw_calc, 2) if raw_calc >= 0.05 else round(raw_calc, 4)

    return {
        "present": True,
        "amount": found_amt,
        "rate": found_rate,
        "derived_rate": derived_rate,
        "raw_text": matched_line,
    }


# Complete Statutory TDS Comparison Table (Income-tax Act, 2025 - FY 2026-27)
# Source: Official Income-tax Act, 2025 Sections 392, 393 & Comparison Chart
STATUTORY_TDS_TABLE_2025 = {
    "SALARY": {
        "section": "Section 392",
        "provision": "Section 392 - Salary",
        "nature_of_payment": "Salary / Remuneration",
        "default_rate": None,
        "legacy_section": "192",
    },
    "EPF_PREMATURE": {
        "section": "Section 392",
        "provision": "Section 392 - Premature EPF Withdrawal",
        "nature_of_payment": "Premature EPF Withdrawal",
        "default_rate": 10.0,
        "legacy_section": "192A",
    },
    "INTEREST_SECURITIES": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 5(i)] - Interest on Securities",
        "nature_of_payment": "Interest on Securities",
        "default_rate": 10.0,
        "legacy_section": "193",
        "zoho_section_slug": "income_interest_on_securities",
    },
    "INTEREST_OTHER": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 5(ii)] - Interest (Bank / Co-op / Post Office / Others)",
        "nature_of_payment": "Interest Payments",
        "default_rate": 10.0,
        "legacy_section": "194A",
        "zoho_section_slug": "income_other_interest_on_securities_specified_person",
    },
    "DIVIDENDS": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 7] - Dividends",
        "nature_of_payment": "Dividend Distribution",
        "default_rate": 10.0,
        "legacy_section": "194",
        "zoho_section_slug": "dividend",
    },
    "INSURANCE_COMMISSION": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 1(i)] - Insurance Commission",
        "nature_of_payment": "Insurance Commission",
        "default_rate": 2.0,
        "legacy_section": "194D",
        "zoho_section_slug": "insurance_commission",
    },
    "COMMISSION_BROKERAGE": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 1(ii)] - Commission or Brokerage",
        "nature_of_payment": "Commission & Brokerage Payments",
        "default_rate": 2.0,
        "legacy_section": "194H",
        "zoho_section_slug": "commission_or_brokerage",
    },
    "RENT_PLANT_MACHINERY": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 2(ii)] - Rent for Plant, Machinery or Equipment",
        "nature_of_payment": "Rent of Plant, Machinery or Equipment",
        "default_rate": 2.0,
        "legacy_section": "194-I(a)",
        "zoho_section_slug": "rent_plant_machinery",
    },
    "RENT_LAND_BUILDING": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 2(ii)] - Rent for Land, Building or Furniture",
        "nature_of_payment": "Rent of Land, Building or Furniture",
        "default_rate": 10.0,
        "legacy_section": "194-I(b)",
        "zoho_section_slug": "rent_land_building",
    },
    "CONTRACTORS": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 6(i)] - Payments to Contractors and Sub-contractors",
        "nature_of_payment": "Work Contracts & Sub-contractor Services",
        "default_rate": 2.0,
        "individual_rate": 1.0,
        "legacy_section": "194C",
        "zoho_section_slug": "payment_contractors_and_professionals",
    },
    "CONTRACTORS_INDIVIDUAL": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 6(i)] - Payments to Contractors (Individual/HUF)",
        "nature_of_payment": "Contractor Services (Individual / HUF)",
        "default_rate": 1.0,
        "legacy_section": "194C",
        "zoho_section_slug": "contract_payments_individual_or_huf",
    },
    "TECHNICAL_SERVICES": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        "nature_of_payment": "Fees for Technical Services (FTS) & Cloud Infrastructure",
        "default_rate": 2.0,
        "legacy_section": "194J(1)(b)",
        "zoho_section_slug": "technical_services",
    },
    "PROFESSIONAL_SERVICES": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 6(iii)(D)(b)] - Professional Services & Fees",
        "nature_of_payment": "Professional Services & Consultancy",
        "default_rate": 10.0,
        "legacy_section": "194J(1)(a)",
        "zoho_section_slug": "professional_fees",
    },
    "PROFESSIONAL_TECHNICAL": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 6(iii)] - Professional and Technical Services",
        "nature_of_payment": "Fees for Technical Services (FTS) & Cloud Infrastructure",
        "default_rate": 2.0,
        "professional_rate": 10.0,
        "legacy_section": "194J",
        "zoho_section_slug": "technical_services",
    },
    "MUTUAL_FUND_UNITS": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 4(i)] - Income from Units (Mutual Funds)",
        "nature_of_payment": "Income from Units",
        "default_rate": 10.0,
        "legacy_section": "194K",
        "zoho_section_slug": "income_units",
    },
    "PURCHASE_OF_GOODS": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        "nature_of_payment": "Purchase of Goods",
        "default_rate": 0.10,
        "legacy_section": "194Q",
        "zoho_section_slug": "purchase_of_goods",
    },
    "BENEFIT_PERQUISITE": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 8(iv)] - Benefit or Perquisite",
        "nature_of_payment": "Benefit or Perquisite in respect of Business",
        "default_rate": 10.0,
        "legacy_section": "194R",
        "zoho_section_slug": "benefit_or_perquisite",
    },
    "ECOMMERCE": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 8(v)] - E-commerce Participant",
        "nature_of_payment": "E-commerce Participant Supply",
        "default_rate": 0.10,
        "legacy_section": "194-O",
        "zoho_section_slug": "e_commerce_operator",
    },
    "VIRTUAL_DIGITAL_ASSET": {
        "section": "Section 393",
        "provision": "Section 393(1) [Table Sl. No. 8(vi)] - Transfer of Virtual Digital Asset",
        "nature_of_payment": "Transfer of Virtual Digital Asset",
        "default_rate": 1.0,
        "legacy_section": "194S",
        "zoho_section_slug": "virtual_digital_asset",
    },
    "CASH_WITHDRAWAL": {
        "section": "Section 393",
        "provision": "Section 393(3) [Table Sl. No. 5] - Cash Withdrawal",
        "nature_of_payment": "Cash Withdrawal",
        "default_rate": 2.0,
        "legacy_section": "194N",
        "zoho_section_slug": "cash_withdrawal",
    },
    "PARTNER_REMUNERATION": {
        "section": "Section 393",
        "provision": "Section 393(3) [Table Sl. No. 7] - Partner Remuneration or Interest",
        "nature_of_payment": "Partner Remuneration or Interest",
        "default_rate": 10.0,
        "legacy_section": "194T",
        "zoho_section_slug": "partner_remuneration",
    },
    "NON_RESIDENT": {
        "section": "Section 393",
        "provision": "Section 393(2) - Sum Paid to Non-Resident",
        "nature_of_payment": "Non-Resident Payment / Foreign Remittance",
        "default_rate": 20.0,
        "legacy_section": "195",
        "zoho_section_slug": "non_resident_payments",
    },
}


def normalize_statutory_text(text: Optional[str]) -> str:
    """
    Normalizes statutory text (removing dots, extra spaces, brackets) for robust comparison.
    E.g., 'Section 393(1) SI6(iii)(D)(b) - Fees' -> 'SECTION 393 1 SL 6 III D B FEES'
    """
    if not text:
        return ""
    s = str(text).upper()
    # Normalize SI/Sl -> SL
    s = re.sub(r"\bSI\b", "SL", s)
    s = re.sub(r"\bSI(\d)", r"SL \1", s)
    s = re.sub(r"\bSL(\d)", r"SL \1", s)
    # Replace punctuation with spaces
    s = re.sub(r"[\[\]\(\)\-\.,_/:;]", " ", s)
    # Normalize multiple whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_tds_tax_details(
    section_raw: Optional[str] = None,
    provision_raw: Optional[str] = None,
    nature_raw: Optional[str] = None,
    rate_hint: Optional[float] = None,
) -> Dict[str, str]:
    """
    Cleans raw/unformatted TDS section, provision, and nature of payment strings into
    canonical Indian Income Tax statutory descriptions using STATUTORY_TDS_TABLE_2025.
    Respects rate_hint (e.g. 10% vs 2%) to disambiguate subclauses when available.
    """
    combined = f"{provision_raw or ''} {section_raw or ''} {nature_raw or ''}".upper()
    norm = normalize_statutory_text(combined)

    # Handle Section 392 (Salaries / EPF)
    if "392" in norm or "SALARY" in norm or "192" in norm or "EPF" in norm:
        entry = STATUTORY_TDS_TABLE_2025["EPF_PREMATURE"] if "EPF" in norm else STATUTORY_TDS_TABLE_2025["SALARY"]
        return {
            "section": entry["section"],
            "provision": entry["provision"],
            "nature_of_payment": nature_raw if (nature_raw and "_" not in nature_raw) else entry["nature_of_payment"],
            "zoho_section_slug": entry.get("zoho_section_slug"),
        }
    # Handle composite multi-section withholding (e.g., 'Sl. 6(i), Sl. 6(iii)')
    elif "COMPOSITE" in norm or ("," in (section_raw or "") and any(k in norm for k in ("194C", "194J", "194I", "SL 6", "SL 2"))):
        sec = section_raw or "Composite"
        prov = provision_raw if (provision_raw and "_" not in provision_raw) else f"Sections {sec} - Composite Statutory Withholding"
        nat = nature_raw if (nature_raw and "_" not in nature_raw) else f"Composite Services ({sec})"
        return {"section": sec, "provision": prov, "nature_of_payment": nat, "zoho_section_slug": None}

    # Match against STATUTORY_TDS_TABLE_2025 with strict clause & rate disambiguation
    is_explicit_fts = (
        any(k in norm for k in ("D A", "TECHNICAL", "TECH SERVICES", "FTS", "CLOUD", "SOFTWARE", "IT SERVICE"))
        or (rate_hint is not None and abs(rate_hint - 2.0) < 0.05 and any(k in norm for k in ("393", "194J", "SL 6 III")))
    )
    is_explicit_prof = (
        any(k in norm for k in ("D B", "PROFESSIONAL", "LEGAL", "CONSULTING", "ARCHITECT", "MEDICAL", "ROYALTY"))
        or (rate_hint is not None and abs(rate_hint - 10.0) < 0.05 and any(k in norm for k in ("393", "194J", "SL 6 III", "FEES", "WITHHELD")))
    )

    # 1. First check explicit specific provisions / categories
    tokens = set(norm.split())
    is_contractor = (
        ("SL 6 I" in norm and "SL 6 III" not in norm and "SL 6 II" not in norm)
        or any(k in norm for k in ("194C", "CONTRACT", "SUB CONTRACT", "MANPOWER", "GUARD"))
    )
    if is_contractor and not any(k in norm for k in ("FTS", "TECHNICAL", "PROFESSIONAL", "LEGAL", "CONSULT")):
        if rate_hint is not None and abs(rate_hint - 1.0) < 0.05:
            entry = STATUTORY_TDS_TABLE_2025["CONTRACTORS_INDIVIDUAL"]
        else:
            entry = STATUTORY_TDS_TABLE_2025["CONTRACTORS"]
    elif any(k in norm for k in ("SL 2", "RENT", "194I", "194 I")):
        is_land = any(w in norm for w in ("LAND", "BUILDING", "FURNITURE", "IMMOVABLE"))
        if rate_hint is not None and abs(rate_hint - 10.0) < 0.05:
            is_land = True
        elif rate_hint is not None and abs(rate_hint - 2.0) < 0.05:
            is_land = False
        entry = STATUTORY_TDS_TABLE_2025["RENT_LAND_BUILDING"] if is_land else STATUTORY_TDS_TABLE_2025["RENT_PLANT_MACHINERY"]
    elif any(k in norm for k in ("SL 1 II", "COMMISSION", "BROKER", "194H")):
        entry = STATUTORY_TDS_TABLE_2025["COMMISSION_BROKERAGE"]
    elif any(k in norm for k in ("SL 1 I", "INSURANCE", "194D")):
        entry = STATUTORY_TDS_TABLE_2025["INSURANCE_COMMISSION"]
    elif any(k in norm for k in ("SL 8 II", "GOODS", "PURCHASE", "194Q")):
        entry = STATUTORY_TDS_TABLE_2025["PURCHASE_OF_GOODS"]
    elif any(k in norm for k in ("SL 8 IV", "PERQUISITE", "BENEFIT", "194R")):
        entry = STATUTORY_TDS_TABLE_2025["BENEFIT_PERQUISITE"]
    elif any(k in norm for k in ("SL 8 V", "ECOMMERCE", "E COMMERCE", "194 O")):
        entry = STATUTORY_TDS_TABLE_2025["ECOMMERCE"]
    elif any(k in norm for k in ("SL 8 VI", "VIRTUAL", "CRYPTO", "VDA", "194S")):
        entry = STATUTORY_TDS_TABLE_2025["VIRTUAL_DIGITAL_ASSET"]
    elif any(k in norm for k in ("SL 5 I", " 193 ", " 193")):
        entry = STATUTORY_TDS_TABLE_2025["INTEREST_SECURITIES"]
    elif any(k in norm for k in ("SL 5 II", "INTEREST", "194A")):
        entry = STATUTORY_TDS_TABLE_2025["INTEREST_OTHER"]
    elif "DIVIDEND" in norm or "SL 7" in norm or " 194 " in f" {norm} ":
        entry = STATUTORY_TDS_TABLE_2025["DIVIDENDS"]
    elif any(k in norm for k in ("SL 4 I", "MUTUAL", "194K")):
        entry = STATUTORY_TDS_TABLE_2025["MUTUAL_FUND_UNITS"]
    elif any(k in norm for k in ("194N", "CASH")):
        entry = STATUTORY_TDS_TABLE_2025["CASH_WITHDRAWAL"]
    elif any(k in norm for k in ("194T", "PARTNER")):
        entry = STATUTORY_TDS_TABLE_2025["PARTNER_REMUNERATION"]
    elif any(k in norm for k in ("195", "NON RESIDENT", "FOREIGN")):
        entry = STATUTORY_TDS_TABLE_2025["NON_RESIDENT"]
    # 2. Then check Section 393(1) Sl 6(iii) / 194J (Professional vs Technical Services)
    elif is_explicit_prof and not (is_explicit_fts and rate_hint == 2.0):
        entry = STATUTORY_TDS_TABLE_2025["PROFESSIONAL_SERVICES"]
    elif is_explicit_fts:
        entry = STATUTORY_TDS_TABLE_2025["TECHNICAL_SERVICES"]
    elif any(k in norm for k in ("SL 6 III", "393", "194J", "TECHNICAL", "PROFESSIONAL")):
        if rate_hint is not None and abs(rate_hint - 10.0) < 0.05:
            entry = STATUTORY_TDS_TABLE_2025["PROFESSIONAL_SERVICES"]
        elif rate_hint is not None and abs(rate_hint - 2.0) < 0.05:
            entry = STATUTORY_TDS_TABLE_2025["TECHNICAL_SERVICES"]
        else:
            entry = STATUTORY_TDS_TABLE_2025["PROFESSIONAL_TECHNICAL"]
    else:
        return {
            "section": "Section 393",
            "provision": f"Section 393 - Statutory Deduction ({section_raw or 'Services'})",
            "nature_of_payment": nature_raw if (nature_raw and "_" not in nature_raw) else "Technical / Professional Services",
            "zoho_section_slug": None,
        }

    return {
        "section": entry["section"],
        "provision": entry["provision"],
        "nature_of_payment": nature_raw if (nature_raw and "_" not in nature_raw) else entry["nature_of_payment"],
        "zoho_section_slug": entry.get("zoho_section_slug"),
    }


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

        section_val = tds_assessment.get("approved_tds_section") or tds_assessment.get("tds_section") or tds_assessment.get("section")
        provision_val = tds_assessment.get("approved_tds_provision") or tds_assessment.get("tds_provision") or tds_assessment.get("provision")
        nature_val = tds_assessment.get("approved_nature_of_payment") or tds_assessment.get("nature_of_payment") or tds_assessment.get("nature")

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

        if raw_app is not None:
            is_app = bool(raw_app)
        else:
            # Deterministic statutory resolution when raw_app is None (unspecified)
            nature_str = (f"{provision_val or ''} {section_val or ''} {nature_val or ''}").upper()
            is_statutory = any(k in nature_str for k in ("CONTRACT", "194C", "PROFESSIONAL", "TECHNICAL", "194J", "393", "RENT", "194I", "COMMISSION", "194H", "PURCHASE", "194Q"))
            is_app = is_statutory and ((base_float is not None and base_float > 0) or rate_float is not None)

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

        is_classification_unresolved = (
            tds_assessment.get("tds_conflict_code") == "TDS_AMBIGUOUS_SAC"
            or (is_app and not section_val and not provision_val and (rate_float is None or rate_float <= 0))
        )

        if is_app and not is_classification_unresolved:
            canonical = resolve_tds_tax_details(section_val, provision_val, nature_val, rate_hint=rate_float)
            section_val = canonical["section"]
            provision_val = canonical["provision"]
            nature_val = canonical["nature_of_payment"]

        if is_app and not is_classification_unresolved and (rate_float is None or rate_float <= 0):
            sec_str = f"{provision_val or ''} {section_val or ''} {nature_val or ''}".upper()
            if "CONTRACT" in sec_str or "194C" in sec_str:
                rate_float = 2.0
            elif "RENT" in sec_str or "194I" in sec_str:
                rate_float = 10.0
            elif "COMMISSION" in sec_str or "194H" in sec_str:
                rate_float = 2.0
            elif "PURCHASE" in sec_str or "194Q" in sec_str:
                rate_float = 0.1
            else:
                rate_float = 2.0

        if is_app and not is_classification_unresolved and (tds_amt_float is None or tds_amt_float == 0) and base_float and rate_float and rate_float > 0:
            tds_amt_float = round((base_float * rate_float) / 100.0, 2)

        vendor_decl = tds_assessment.get("vendor_declared_tds") or accounting.get("vendor_declared_tds")
        tds_needs_review = bool(tds_assessment.get("tds_needs_review"))
        conflict_code = tds_assessment.get("tds_conflict_code")
        conflict_reason = tds_assessment.get("tds_conflict_reason")

        # Conflict check: If vendor explicitly declared TDS, compare against statutory calculation
        if vendor_decl and isinstance(vendor_decl, dict) and vendor_decl.get("present"):
            v_amt = vendor_decl.get("amount")
            v_rate = vendor_decl.get("rate") or vendor_decl.get("derived_rate")
            
            # Check for material discrepancy (amount diff > 1.0 or rate diff > 0.05%)
            has_amt_mismatch = (
                v_amt is not None and tds_amt_float is not None and abs(v_amt - tds_amt_float) > 1.0
            )
            has_rate_mismatch = (
                v_rate is not None and rate_float is not None and abs(v_rate - rate_float) > 0.05
            )

            if has_amt_mismatch or has_rate_mismatch:
                tds_needs_review = True
                conflict_code = "TDS_VENDOR_STATUTORY_MISMATCH"
                v_desc = f"₹{v_amt:,.2f}" if v_amt is not None else ""
                if v_rate is not None:
                    v_desc += f" ({v_rate}%)"
                s_desc = f"₹{tds_amt_float:,.2f}" if tds_amt_float is not None else ""
                if rate_float is not None:
                    s_desc += f" ({rate_float}%)"
                conflict_reason = (
                    f"Conflict between vendor-declared TDS [{v_desc}] and statutory determination [{s_desc}]. "
                    f"Statutory section: {section_val or 'Services'}. Manual review required."
                )

        eff_approval = "APPROVED" if is_appr else ("REVIEW_REQUIRED" if tds_needs_review else "PENDING")

        return {
            "applicable": is_app,
            "section": section_val if is_app else None,
            "tds_section": section_val if is_app else None,
            "provision": provision_val if is_app else None,
            "tds_provision": provision_val if is_app else None,
            "nature_of_payment": nature_val if is_app else None,
            "rate": rate_float if is_app else None,
            "tds_rate": rate_float if is_app else None,
            "approved_tds_rate": rate_float if is_app else None,
            "base_amount": base_float if is_app else None,
            "tds_base_amount": base_float if is_app else None,
            "tds_amount": tds_amt_float if is_app else None,
            "proposed_tds_amount": tds_amt_float if is_app else None,
            "reasoning": conflict_reason or tds_assessment.get("tds_reasoning") or tds_assessment.get("reason"),
            "is_approved": is_appr,
            "approval_status": eff_approval,
            "tds_needs_review": tds_needs_review,
            "tds_conflict_code": conflict_code,
            "tds_conflict_reason": conflict_reason,
            "vendor_declared_tds": vendor_decl,
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

    @staticmethod
    def determine_tds_base_amount(
        invoice_data: Optional[Dict[str, Any]] = None,
        tds_proposal: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Determines the authoritative statutory TDS Base Amount from available transaction values.
        Does NOT blindly map to invoice subtotal.
        Hierarchy:
        1. Explicit valid proposal/user base_amount if positive and supported by transaction
        2. Sum of taxable line items (pretax services/goods amount)
        3. Document subtotal (pre-tax amount)
        4. Total amount less tax total if available
        5. Zero if non-applicable or unavailable
        """
        inv = invoice_data if isinstance(invoice_data, dict) else {}
        tds = tds_proposal if isinstance(tds_proposal, dict) else {}

        # Check explicit proposed base amount
        prop_base = (
            tds.get("approved_tds_base_amount")
            or tds.get("tds_base_amount")
            or tds.get("base_amount")
        )
        try:
            prop_float = float(prop_base) if prop_base is not None else None
        except (ValueError, TypeError):
            prop_float = None

        if prop_float is not None and prop_float > 0:
            return round(prop_float, 2)

        # Check sum of line items taxable amounts
        line_items = inv.get("line_items") or []
        if isinstance(line_items, list) and len(line_items) > 0:
            taxable_sum = 0.0
            has_taxable = False
            for item in line_items:
                if isinstance(item, dict):
                    t_amt = (
                        item.get("taxable_amount")
                        or item.get("taxable")
                        or item.get("pretax_amount")
                        or item.get("amount")
                    )
                    try:
                        val = float(t_amt) if t_amt is not None else None
                    except (ValueError, TypeError):
                        val = None

                    if val is None:
                        qty = item.get("quantity")
                        u_price = item.get("unit_price")
                        try:
                            if qty is not None and u_price is not None:
                                val = float(qty) * float(u_price)
                        except (ValueError, TypeError):
                            val = None

                    if val is not None and val > 0:
                        taxable_sum += val
                        has_taxable = True

            if has_taxable and taxable_sum > 0:
                return round(taxable_sum, 2)

        # Pretax Subtotal fallback
        subtotal = inv.get("subtotal")
        try:
            subtotal_float = float(subtotal) if subtotal is not None else None
        except (ValueError, TypeError):
            subtotal_float = None

        if subtotal_float is not None and subtotal_float > 0:
            return round(subtotal_float, 2)

        # Fallback: total_amount minus tax_total
        total_amt = inv.get("total_amount")
        tax_tot = inv.get("tax_total") or 0.0
        try:
            tot_float = float(total_amt) if total_amt is not None else None
            tax_float = float(tax_tot) if tax_tot is not None else 0.0
            if tot_float is not None and tot_float > 0:
                calc_base = tot_float - tax_float
                if calc_base > 0:
                    return round(calc_base, 2)
                return round(tot_float, 2)
        except (ValueError, TypeError):
            pass

        return 0.0

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
        vendor_declared_tds: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Computes statutory TDS amount according to Indian Income Tax rules.
        If applicable is False, strictly returns TDS not applicable with 0.0 amounts.
        If applicable is None and no section/rate is specified, defaults to not applicable.
        Preserves vendor_declared_tds separately and flags conflicts if vendor declaration
        materially differs from the statutory calculation.
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
                "vendor_declared_tds": vendor_declared_tds,
                "tds_needs_review": False,
                "tds_conflict_code": None,
                "tds_conflict_reason": None,
            }

        # If applicable is True and base_amount > 0, but no rate, section, or provision is resolved (unresolved classification)
        if applicable is True and (rate is None or rate == 0.0) and not section and not provision:
            return {
                "applicable": True,
                "provision": None,
                "section": None,
                "nature_of_payment": nature_of_payment or "Classification Unresolved",
                "rate": None,
                "base_amount": round(base_amount, 2),
                "tds_amount": None,
                "pan_valid": cls.is_valid_pan(vendor_pan) if vendor_pan else True,
                "reason": "TDS classification unresolved - manual review required",
                "vendor_declared_tds": vendor_declared_tds,
                "tds_needs_review": True,
                "tds_conflict_code": "TDS_AMBIGUOUS_SAC",
                "tds_conflict_reason": "TDS classification unresolved - manual review required",
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
                "vendor_declared_tds": vendor_declared_tds,
                "tds_needs_review": False,
                "tds_conflict_code": None,
                "tds_conflict_reason": None,
            }

        pan_valid = cls.is_valid_pan(vendor_pan) if vendor_pan else True
        individual = cls.is_individual_or_huf(vendor_pan)

        computed_rate: float = 0.0
        reason: str = ""

        if rate is not None and float(rate) > 0:
            computed_rate = float(rate)
            label = nature_of_payment or section or provision or "TDS"
            reason = f"Authoritative TDS rate ({computed_rate}%) applied to base amount (₹{base_amount:,.2f}) for {label}."
        else:
            sec_str = (f"{provision or ''} {section or ''} {nature_of_payment or ''}").upper()
            if vendor_pan and not pan_valid:
                computed_rate = 20.0
                reason = "Section 206AA higher deduction (20%) applied due to invalid vendor PAN."
            elif "392" in sec_str or "EPF" in sec_str:
                computed_rate = 10.0
                reason = "Premature EPF Withdrawal TDS (10%) under Section 392"
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

        tds_needs_review = False
        conflict_code = None
        conflict_reason = None

        if vendor_declared_tds and isinstance(vendor_declared_tds, dict) and vendor_declared_tds.get("present"):
            v_amt = vendor_declared_tds.get("amount")
            v_rate = vendor_declared_tds.get("rate") or vendor_declared_tds.get("derived_rate")
            has_amt_mismatch = v_amt is not None and abs(v_amt - tds_amount) > 1.0
            has_rate_mismatch = v_rate is not None and abs(v_rate - computed_rate) > 0.05
            if has_amt_mismatch or has_rate_mismatch:
                tds_needs_review = True
                conflict_code = "TDS_VENDOR_STATUTORY_MISMATCH"
                v_desc = f"₹{v_amt:,.2f}" if v_amt is not None else ""
                if v_rate is not None:
                    v_desc += f" ({v_rate}%)"
                s_desc = f"₹{tds_amount:,.2f} ({computed_rate}%)"
                conflict_reason = (
                    f"Conflict between vendor-declared TDS [{v_desc}] and statutory determination [{s_desc}]. "
                    f"Statutory provision: {provision or section or 'Services'}. Manual review required."
                )

        return {
            "applicable": True,
            "provision": provision,
            "section": section,
            "nature_of_payment": nature_of_payment,
            "rate": computed_rate,
            "base_amount": round(base_amount, 2),
            "tds_amount": tds_amount,
            "pan_valid": pan_valid,
            "reason": conflict_reason or reason,
            "vendor_declared_tds": vendor_declared_tds,
            "tds_needs_review": tds_needs_review,
            "tds_conflict_code": conflict_code,
            "tds_conflict_reason": conflict_reason,
        }


tds_engine = TDSEngine()


