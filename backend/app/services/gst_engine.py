import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Complete 2-digit Indian GST State & Union Territory Codes Mapping
GST_STATE_CODES: Dict[str, str] = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman & Diu",
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

# Reverse lookup dictionary for state names & common aliases to 2-digit numeric GST codes
STATE_NAME_TO_CODE: Dict[str, str] = {
    # 01 Jammu & Kashmir
    "jammu and kashmir": "01",
    "jammu & kashmir": "01",
    "jammu": "01",
    "kashmir": "01",
    "j&k": "01",
    "jk": "01",
    # 02 Himachal Pradesh
    "himachal pradesh": "02",
    "himachal": "02",
    "hp": "02",
    # 03 Punjab
    "punjab": "03",
    "pb": "03",
    # 04 Chandigarh
    "chandigarh": "04",
    "ch": "04",
    # 05 Uttarakhand
    "uttarakhand": "05",
    "uttaranchal": "05",
    "uk": "05",
    "ua": "05",
    # 06 Haryana
    "haryana": "06",
    "hr": "06",
    # 07 Delhi
    "delhi": "07",
    "new delhi": "07",
    "nct of delhi": "07",
    "dl": "07",
    # 08 Rajasthan
    "rajasthan": "08",
    "rj": "08",
    # 09 Uttar Pradesh
    "uttar pradesh": "09",
    "up": "09",
    # 10 Bihar
    "bihar": "10",
    "br": "10",
    "bh": "10",
    # 11 Sikkim
    "sikkim": "11",
    "sk": "11",
    # 12 Arunachal Pradesh
    "arunachal pradesh": "12",
    "arunachal": "12",
    "ar": "12",
    # 13 Nagaland
    "nagaland": "13",
    "nl": "13",
    # 14 Manipur
    "manipur": "14",
    "mn": "14",
    # 15 Mizoram
    "mizoram": "15",
    "mz": "15",
    # 16 Tripura
    "tripura": "16",
    "tr": "16",
    # 17 Meghalaya
    "meghalaya": "17",
    "ml": "17",
    # 18 Assam
    "assam": "18",
    "as": "18",
    # 19 West Bengal
    "west bengal": "19",
    "bengal": "19",
    "wb": "19",
    # 20 Jharkhand
    "jharkhand": "20",
    "jh": "20",
    # 21 Odisha
    "odisha": "21",
    "orissa": "21",
    "od": "21",
    "or": "21",
    # 22 Chhattisgarh
    "chhattisgarh": "22",
    "chattisgarh": "22",
    "cg": "22",
    "ct": "22",
    # 23 Madhya Pradesh
    "madhya pradesh": "23",
    "mp": "23",
    # 24 Gujarat
    "gujarat": "24",
    "gj": "24",
    # 25 & 26 Dadra & Nagar Haveli and Daman & Diu
    "daman and diu": "26",
    "daman & diu": "26",
    "dadra and nagar haveli": "26",
    "dadra & nagar haveli": "26",
    "dadra & nagar haveli and daman & diu": "26",
    "dadra and nagar haveli and daman and diu": "26",
    "dn": "26",
    "dd": "26",
    "dnh": "26",
    # 27 Maharashtra
    "maharashtra": "27",
    "mh": "27",
    # 29 Karnataka
    "karnataka": "29",
    "ka": "29",
    # 30 Goa
    "goa": "30",
    "ga": "30",
    # 31 Lakshadweep
    "lakshadweep": "31",
    "lakshadweep islands": "31",
    "ld": "31",
    # 32 Kerala
    "kerala": "32",
    "kl": "32",
    # 33 Tamil Nadu
    "tamil nadu": "33",
    "tamilnadu": "33",
    "tn": "33",
    # 34 Puducherry
    "puducherry": "34",
    "pondicherry": "34",
    "py": "34",
    "pd": "34",
    # 35 Andaman & Nicobar Islands
    "andaman and nicobar": "35",
    "andaman & nicobar": "35",
    "andaman and nicobar islands": "35",
    "andaman & nicobar islands": "35",
    "an": "35",
    # 36 Telangana
    "telangana": "36",
    "ts": "36",
    "tg": "36",
    # 37 Andhra Pradesh
    "andhra pradesh": "37",
    "andhra": "37",
    "ad": "37",
    "ap": "37",
    # 38 Ladakh
    "ladakh": "38",
    "la": "38",
    "lk": "38",
    # 97 Other Territory
    "other territory": "97",
    "ot": "97",
}

# Zoho Books India Official 2-letter State Code Mapping
GST_NUMERIC_TO_ZOHO_CODE: Dict[str, str] = {
    "01": "JK",  # Jammu & Kashmir
    "02": "HP",  # Himachal Pradesh
    "03": "PB",  # Punjab
    "04": "CH",  # Chandigarh
    "05": "UK",  # Uttarakhand
    "06": "HR",  # Haryana
    "07": "DL",  # Delhi
    "08": "RJ",  # Rajasthan
    "09": "UP",  # Uttar Pradesh
    "10": "BR",  # Bihar
    "11": "SK",  # Sikkim
    "12": "AR",  # Arunachal Pradesh
    "13": "NL",  # Nagaland
    "14": "MN",  # Manipur
    "15": "MZ",  # Mizoram
    "16": "TR",  # Tripura
    "17": "ML",  # Meghalaya
    "18": "AS",  # Assam
    "19": "WB",  # West Bengal
    "20": "JH",  # Jharkhand
    "21": "OD",  # Odisha
    "22": "CG",  # Chhattisgarh
    "23": "MP",  # Madhya Pradesh
    "24": "GJ",  # Gujarat
    "25": "DN",  # Daman & Diu
    "26": "DN",  # Dadra & Nagar Haveli and Daman & Diu
    "27": "MH",  # Maharashtra
    "28": "AD",  # Andhra Pradesh (Old)
    "29": "KA",  # Karnataka
    "30": "GA",  # Goa
    "31": "LD",  # Lakshadweep
    "32": "KL",  # Kerala
    "33": "TN",  # Tamil Nadu
    "34": "PY",  # Puducherry / Pondicherry
    "35": "AN",  # Andaman & Nicobar Islands
    "36": "TS",  # Telangana (Zoho Books India official code is TS)
    "37": "AD",  # Andhra Pradesh (Zoho Books India official code is AD)
    "38": "LA",  # Ladakh
    "97": "OT",  # Other Territory
}


def normalize_indian_state(
    state_input: Optional[str] = None,
    gstin: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Normalizes arbitrary Indian state representations (e.g. 'Telangana', 'TG', 'TS', '36',
    'Maharashtra', 'MH', '27', 'Karnataka', 'KA', 'Andhra Pradesh', 'AP', 'AD', etc.) or GSTIN
    into standard Zoho Books India representations.

    Returns:
        (zoho_state_code, numeric_gst_code, full_state_name)
        Example for Telangana: ("TS", "36", "Telangana")
        Example for Maharashtra: ("MH", "27", "Maharashtra")
        Example for Andhra Pradesh: ("AD", "37", "Andhra Pradesh")
    """
    numeric_code: Optional[str] = None

    # 1. Try resolving from state_input if provided
    if state_input and isinstance(state_input, str):
        clean_input = state_input.strip().lower()
        # Direct numeric check (e.g. "36" or "27")
        if clean_input in GST_STATE_CODES:
            numeric_code = clean_input
        # Lookup in alias dictionary
        elif clean_input in STATE_NAME_TO_CODE:
            numeric_code = STATE_NAME_TO_CODE[clean_input]
        else:
            # Check if input starts with a known numeric code e.g. "36 - Telangana" or contains parentheses
            match_num = re.search(r"\b(0[1-9]|[1-3][0-9]|97)\b", clean_input)
            if match_num and match_num.group(1) in GST_STATE_CODES:
                numeric_code = match_num.group(1)
            else:
                # Fuzzy word matching for compound state names
                for name, code in STATE_NAME_TO_CODE.items():
                    if len(name) > 3 and (name in clean_input or clean_input in name):
                        numeric_code = code
                        break

    # 2. Fallback to extracting from GSTIN if state_input didn't resolve
    if not numeric_code and gstin and isinstance(gstin, str):
        cleaned_gst = re.sub(r"[^A-Za-z0-9]", "", gstin).upper().strip()
        if len(cleaned_gst) >= 2:
            gst_prefix = cleaned_gst[:2]
            if gst_prefix in GST_STATE_CODES:
                numeric_code = gst_prefix

    if numeric_code and numeric_code in GST_STATE_CODES:
        full_name = GST_STATE_CODES[numeric_code]
        zoho_code = GST_NUMERIC_TO_ZOHO_CODE.get(numeric_code, "TS")
        return zoho_code, numeric_code, full_name

    return None, None, None


def validate_gstin(gstin: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates standard 15-character Indian GSTIN format.
    Accepts standard GSTINs and extracts state code accurately.
    """
    if not gstin or not isinstance(gstin, str):
        return False, None
    cleaned = re.sub(r"[^A-Za-z0-9]", "", gstin).upper().strip()
    if len(cleaned) == 15 and cleaned[:2] in GST_STATE_CODES:
        return True, cleaned
    return False, None


def extract_state_code_from_gstin(gstin: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts 2-digit state code and name from valid GSTIN.
    Returns (state_code, state_name).
    """
    is_valid, cleaned = validate_gstin(gstin)
    if is_valid and cleaned:
        code = cleaned[:2]
        if code in GST_STATE_CODES:
            return code, GST_STATE_CODES[code]
    return None, None


def resolve_state_from_text(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves 2-digit state code from arbitrary text (e.g. 'Telangana (36)', 'Maharashtra', 'State: 27').
    """
    if not text or not isinstance(text, str):
        return None, None


    cleaned = text.strip()

    # Check for embedded 2-digit code e.g. "Telangana (36)" or "Code: 36" or "36-Telangana"
    code_match = re.search(r"\b(0[1-9]|[1-2][0-9]|3[0-8]|97|99)\b", cleaned)
    if code_match:
        code = code_match.group(1)
        if code in GST_STATE_CODES:
            return code, GST_STATE_CODES[code]

    # Check for direct state name in text
    normalized = cleaned.lower()
    for name, code in STATE_NAME_TO_CODE.items():
        # Match whole word or bounded phrase
        if re.search(r"\b" + re.escape(name) + r"\b", normalized):
            return code, GST_STATE_CODES.get(code, name.title())

    return None, None


def parse_clean_numeric(val: Any) -> Optional[float]:
    """Parses clean numeric values from numbers or strings with currency symbols."""
    import math
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return float(val)
    if isinstance(val, str):
        clean = val.strip()
        if re.match(r"^[+\-]{2,}", clean):
            return None
        negative = False
        if clean.startswith("-"):
            negative = True
            clean = clean[1:].strip()
        elif clean.startswith("+"):
            clean = clean[1:].strip()
        elif clean.startswith("(") and clean.endswith(")"):
            negative = True
            clean = clean[1:-1].strip()

        clean = re.sub(r"^(?:Rupees|Rupee|Rs\.?|INR|₹)\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*(?:/-\s*|Only\s*|%\s*)$", "", clean, flags=re.IGNORECASE)
        clean = clean.strip()
        if re.match(r"^[+\-]{2,}", clean):
            return None
        if not negative and clean.startswith("-"):
            negative = True
            clean = clean[1:].strip()
        elif not negative and clean.startswith("(") and clean.endswith(")"):
            negative = True
            clean = clean[1:-1].strip()
        elif negative and (clean.startswith("-") or clean.startswith("+")):
            return None
        if re.search(r"[a-zA-Z]", clean):
            return None
        if "," in clean:
            if clean.startswith(",") or clean.endswith(",") or ",," in clean:
                return None
            parts = clean.split(".")
            if len(parts) > 2:
                return None
            int_part = parts[0]
            if not int_part:
                return None
            indian_pattern = r"^\d{1,2}(?:,\d{2})*,\d{3}$"
            intl_pattern = r"^\d{1,3}(?:,\d{3})+$"
            if not (re.match(indian_pattern, int_part) or re.match(intl_pattern, int_part)):
                return None
            clean = clean.replace(",", "")
        if not re.match(r"^\d+(?:\.\d+)?$", clean):
            return None
        try:
            num = float(clean)
            if math.isnan(num) or math.isinf(num):
                return None
            return -num if negative else num
        except ValueError:
            return None
    return None


def extract_tax_value(data: Dict[str, Any], tax_type: str) -> Optional[float]:
    """
    Extracts invoice-level CGST, SGST, or IGST value from explicit keys, additional_fields, or line items.
    """
    if not isinstance(data, dict):
        return None

    data_obj = data.get("data") if isinstance(data.get("data"), dict) else data

    exact_keys = {
        "cgst": ["cgst", "cgst_amount", "cgst_total", "total_cgst", "cgst_tax", "c_gst"],
        "sgst": ["sgst", "sgst_amount", "sgst_total", "total_sgst", "sgst_tax", "s_gst", "utgst", "utgst_amount"],
        "igst": ["igst", "igst_amount", "igst_total", "total_igst", "igst_tax", "i_gst"],
        "cess": [
            "cess",
            "cess_amount",
            "cess_total",
            "total_cess",
            "compensation_cess",
            "compensation_cess_amount",
            "compensation cess",
            "comp_cess",
        ],
    }.get(tax_type, [])

    # 1. Top-level keys (collect all candidate values to check consistency)
    found_candidates: List[float] = []
    for src in [data, data_obj]:
        for k in exact_keys:
            if k in src and src[k] is not None and src[k] != "":
                val = parse_clean_numeric(src[k])
                if val is not None and val not in found_candidates:
                    found_candidates.append(val)
            upper_k = k.upper()
            if upper_k in src and src[upper_k] is not None and src[upper_k] != "":
                val = parse_clean_numeric(src[upper_k])
                if val is not None and val not in found_candidates:
                    found_candidates.append(val)

    # Check candidate consistency: if multiple conflicting values exist, return the first but warn/note
    if found_candidates:
        unique_vals = []
        for v in found_candidates:
            if not any(abs(v - u) <= 0.05 for u in unique_vals):
                unique_vals.append(v)
        # If conflicting values exist, return None to trigger review in FinancialValidator or return first
        return found_candidates[0]

    # 2. Search inside additional_fields (and tax_details)
    for src in [data, data_obj]:
        af = src.get("additional_fields")
        if isinstance(af, dict):
            for k, v in af.items():
                if v is None or v == "":
                    continue
                clean_k = re.sub(r"[^a-zA-Z0-9]", "", k).lower()
                if tax_type == "cgst" and clean_k in ["cgst", "cgstamount", "cgsttotal", "cgsttax", "centralgst", "centralgstamount", "cgstamt"]:
                    val = parse_clean_numeric(v)
                    if val is not None:
                        return val
                elif tax_type == "sgst" and clean_k in ["sgst", "sgstamount", "sgsttotal", "sgsttax", "stategst", "utgst", "utgstamount", "sgstamt"]:
                    val = parse_clean_numeric(v)
                    if val is not None:
                        return val
                elif tax_type == "igst" and clean_k in ["igst", "igstamount", "igsttotal", "igsttax", "integratedgst", "igstamt"]:
                    val = parse_clean_numeric(v)
                    if val is not None:
                        return val
                elif tax_type == "cess" and clean_k in [
                    "cess",
                    "cessamount",
                    "cesstotal",
                    "totalcess",
                    "compensationcess",
                    "compensationcessamount",
                    "compcess",
                    "gstcess",
                ]:
                    val = parse_clean_numeric(v)
                    if val is not None:
                        return val

            td = af.get("tax_details")
            if isinstance(td, dict):
                for section in ["output_tax", "tax_payable", "input_tax_credit", "tax_breakdown", ""]:
                    target = td.get(section) if section else td
                    if isinstance(target, dict):
                        for k in exact_keys:
                            if k in target and target[k] is not None and target[k] != "":
                                val = parse_clean_numeric(target[k])
                                if val is not None:
                                    return val
                                # If target[k] is a dict with 'amount' or 'total'
                                if isinstance(target[k], dict):
                                    inner_amt = target[k].get("amount") or target[k].get("total")
                                    val = parse_clean_numeric(inner_amt)
                                    if val is not None:
                                        return val
                            upper_k = k.upper()
                            if upper_k in target and target[upper_k] is not None and target[upper_k] != "":
                                val = parse_clean_numeric(target[upper_k])
                                if val is not None:
                                    return val
                                if isinstance(target[upper_k], dict):
                                    inner_amt = target[upper_k].get("amount") or target[upper_k].get("total")
                                    val = parse_clean_numeric(inner_amt)
                                    if val is not None:
                                        return val

    # 3. Sum from line items
    line_items = data_obj.get("line_items") or data.get("line_items")
    if isinstance(line_items, list) and len(line_items) > 0:
        line_vals = []
        for item in line_items:
            if not isinstance(item, dict):
                continue
            found_val = None
            for k in exact_keys:
                if k in item and item[k] is not None and item[k] != "":
                    val = parse_clean_numeric(item[k])
                    if val is not None:
                        found_val = val
                        break
                upper_k = k.upper()
                if upper_k in item and item[upper_k] is not None and item[upper_k] != "":
                    val = parse_clean_numeric(item[upper_k])
                    if val is not None:
                        found_val = val
                        break

            # If explicit amount omitted on line, compute from rate * taxable
            if found_val is None:
                rate_key = f"{tax_type}_rate"
                rate_val = parse_clean_numeric(item.get(rate_key) or item.get(rate_key.upper()))
                taxable_val = parse_clean_numeric(
                    item.get("taxable_amount")
                    or item.get("taxable")
                    or item.get("pretax_amount")
                    or (
                        float(item["unit_price"]) * float(item["quantity"])
                        if item.get("unit_price") is not None and item.get("quantity") is not None
                        else None
                    )
                )
                if rate_val is not None and rate_val > 0 and taxable_val is not None and taxable_val > 0:
                    found_val = round((taxable_val * rate_val / 100.0), 2)

            if found_val is not None:
                line_vals.append(found_val)

        if line_vals:
            return round(sum(line_vals), 2)

    return None


def extract_explicit_place_of_supply(data_obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Scans invoice data for explicit Place of Supply statements across:
    1. Direct fields: place_of_supply, pos, place_of_delivery, state_of_supply
    2. Any key in additional_fields containing 'place of supply', 'pos', 'supply state', etc.
    3. Any value in additional_fields containing 'Place of Supply' pattern
    4. Address fields containing explicit 'Place of Supply: ...' or 'POS: ...'
    """
    if not isinstance(data_obj, dict):
        return None, None

    # 1. Direct fields
    for k in ["place_of_supply", "pos", "place_of_delivery", "state_of_supply", "supply_state", "Place Of Supply", "Place of Supply"]:
        val = data_obj.get(k)
        if val:
            code, name = resolve_state_from_text(str(val))
            if code:
                return code, name

    # 2. Check additional_fields keys and values
    af = data_obj.get("additional_fields")
    if isinstance(af, dict):
        for k, v in af.items():
            if not v:
                continue
            k_clean = re.sub(r"[^a-zA-Z0-9]", "", k).lower()
            if any(target in k_clean for target in ["placeofsupply", "pos", "stateofsupply", "supplystate", "placeofdelivery", "shiptostate", "stateut"]):
                code, name = resolve_state_from_text(str(v))
                if code:
                    return code, name
            # If value contains explicit POS text like "Place of Supply: Karnataka (29)" or "POS: 29"
            v_str = str(v)
            pos_match = re.search(r"(?:place\s+of\s+supply|pos|place\s+of\s+delivery)\s*[:\-]?\s*([A-Za-z0-9\s()&,\-]+)", v_str, re.IGNORECASE)
            if pos_match:
                code, name = resolve_state_from_text(pos_match.group(1))
                if code:
                    return code, name

    # 3. Check address / text fields for embedded 'Place of Supply' lines
    for addr_k in ["customer_address", "vendor_address", "shipping_address", "notes", "say"]:
        addr_val = data_obj.get(addr_k)
        if addr_val:
            pos_match = re.search(r"(?:place\s+of\s+supply|pos|place\s+of\s+delivery)\s*[:\-]?\s*([A-Za-z0-9\s()&,\-]+)", str(addr_val), re.IGNORECASE)
            if pos_match:
                code, name = resolve_state_from_text(pos_match.group(1))
                if code:
                    return code, name

    return None, None


def classify_entity_constitution(
    pan: Optional[str] = None,
    gstin: Optional[str] = None,
    entity_name: Optional[str] = None,
) -> str:
    """
    Classifies entity constitution as evidence (not forced boolean):
    - BODY_CORPORATE: Company, Corporation, Ltd, Private Limited
    - NON_BODY_CORPORATE: Individual / HUF
    - FIRM: Partnership Firm / LLP
    - UNKNOWN: Missing/invalid evidence
    """
    clean_pan = (pan or "").strip().upper()
    if not clean_pan and gstin and len(gstin.strip()) >= 12:
        clean_pan = gstin.strip()[2:12].upper()

    if clean_pan and len(clean_pan) >= 4:
        fourth_char = clean_pan[3]
        if fourth_char == "C":
            return "BODY_CORPORATE"
        elif fourth_char in ("P", "H"):
            return "NON_BODY_CORPORATE"
        elif fourth_char == "F":
            return "FIRM"

    name_lower = (entity_name or "").lower()
    if any(k in name_lower for k in ("pvt ltd", "private limited", "ltd", "limited", "corp", "corporation", "inc", "gmbh", "b.v.")):
        if "llp" not in name_lower and "proprietor" not in name_lower:
            return "BODY_CORPORATE"
    elif "llp" in name_lower or "partnership" in name_lower:
        return "FIRM"
    elif any(k in name_lower for k in ("proprietor", "proprietorship", "individual", "mr.", "ms.", "mrs.")):
        return "NON_BODY_CORPORATE"

    return "UNKNOWN"


def check_foreign_supplier_evidence(data_obj: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Deterministically evaluates whether the supplier is located in non-taxable territory (outside India).
    CRITICAL RULE: Never infer 'supplier outside India' merely from missing Indian GSTIN.
    Requires explicit foreign country/location evidence.
    Missing location/GSTIN alone = UNKNOWN, not foreign.
    """
    if not isinstance(data_obj, dict):
        return False, None

    vendor_country = str(data_obj.get("vendor_country") or data_obj.get("supplier_country") or "").strip().upper()
    if vendor_country and vendor_country not in ("IN", "IND", "INDIA"):
        return True, f"Explicit vendor country '{vendor_country}' outside India"

    v_addr = str(data_obj.get("vendor_address") or data_obj.get("supplier_address") or "")
    if v_addr:
        foreign_country_patterns = [
            r"\b(usa|united states|united kingdom|uk|singapore|germany|ireland|australia|canada|netherlands|france|japan|china|hong kong|switzerland|uae|dubai)\b",
            r"\b(california|delaware|new york|texas|washington|london|dublin|singapore)\b",
        ]
        for pat in foreign_country_patterns:
            m = re.search(pat, v_addr, re.IGNORECASE)
            if m:
                # Ensure it doesn't also mention India
                if not re.search(r"\b(india|pin\s*-\s*\d{6}|\b\d{6}\b)\b", v_addr, re.IGNORECASE):
                    return True, f"Vendor address indicates overseas location: '{m.group(0)}'"

    return False, None


class GSTEngine:
    """Deterministic GST Rule & Validation Engine."""

    def _evaluate_rcm(
        self,
        data_obj: Dict[str, Any],
        vendor_gstin: Optional[str],
        buyer_gstin: Optional[str],
        supplier_state_code: Optional[str],
        pos_state_code: Optional[str],
        supply_type: str,
    ) -> Dict[str, Any]:
        """
        Deterministic statutory evaluation of Reverse Charge Mechanism (RCM) applicability.
        Authority:
          - Notification No. 13/2017-Central Tax (Rate) as amended (including 29/2018, 05/2019, 22/2019, 05/2022, 09/2024, 07/2025)
          - Notification No. 10/2017-Integrated Tax (Rate) as amended
        """
        af = data_obj.get("additional_fields") or {}
        explicit_rc_raw = str(
            af.get("Whether tax is payable under Reverse Charge?")
            or af.get("reverse_charge")
            or data_obj.get("reverse_charge")
            or ""
        ).strip().lower()

        explicit_rcm_flag: Optional[bool] = None
        if explicit_rc_raw in ("yes", "true", "1", "y"):
            explicit_rcm_flag = True
        elif explicit_rc_raw in ("no", "false", "0", "n"):
            explicit_rcm_flag = False

        vendor_name = str(data_obj.get("vendor_name") or data_obj.get("supplier_name") or "")
        buyer_name = str(data_obj.get("customer_name") or data_obj.get("buyer_name") or "")
        vendor_pan = str(data_obj.get("vendor_pan") or data_obj.get("supplier_pan") or "")
        buyer_pan = str(data_obj.get("customer_pan") or data_obj.get("buyer_pan") or "")

        supplier_entity = classify_entity_constitution(vendor_pan, vendor_gstin, vendor_name)
        recipient_entity = classify_entity_constitution(buyer_pan, buyer_gstin, buyer_name)
        is_recipient_registered = bool(buyer_gstin and len(buyer_gstin.strip()) == 15)

        line_items = data_obj.get("line_items") or []
        descriptions = []
        sac_codes = []
        for it in line_items:
            if isinstance(it, dict):
                d = str(it.get("description") or "")
                if d:
                    descriptions.append(d)
                s = str(it.get("sac") or it.get("sac_code") or it.get("hsn") or it.get("hsn_code") or "")
                if s:
                    sac_codes.append(s)

        header_desc = str(data_obj.get("description") or data_obj.get("notes") or "")
        if header_desc:
            descriptions.append(header_desc)

        all_desc_text = " ".join(descriptions).lower()
        all_sac_text = " ".join(sac_codes)

        # -------------------------------------------------------------
        # 1. IMPORT OF SERVICES (IGST Act Sec 5(3) / Notif 10/2017-IT(R) Entry 1)
        # -------------------------------------------------------------
        is_foreign, foreign_reason = check_foreign_supplier_evidence(data_obj)
        if is_foreign:
            # Check doc type - Goods import (Bill of Entry) is Customs, not service RCM
            doc_type = str(data_obj.get("document_type") or "").upper()
            if "BILL_OF_ENTRY" in doc_type or "CUSTOMS" in doc_type:
                return {
                    "is_reverse_charge": False,
                    "rcm_category": None,
                    "rcm_reason": "Bill of entry / Goods import is subject to Customs duty, not Service RCM under Notif 10/2017-IT(R)",
                    "rcm_notification": None,
                    "rcm_conflict": None,
                    "rcm_requires_review": False,
                }

            if is_recipient_registered or recipient_entity in ("BODY_CORPORATE", "FIRM"):
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "IMPORT_OF_SERVICES",
                    "rcm_reason": f"Import of services from overseas supplier ({foreign_reason}) to taxable recipient in India.",
                    "rcm_notification": "IGST Act Sec 5(3) / Notif 10/2017-IT(R) Entry 1",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            else:
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "IMPORT_OF_SERVICES",
                    "rcm_reason": "Overseas supplier identified, but recipient registration/business status in India is unverified (potential OIDAR non-taxable online recipient).",
                    "rcm_notification": "IGST Act Sec 5(3) / Notif 10/2017-IT(R) Entry 1",
                    "rcm_conflict": None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 2. GOODS TRANSPORT AGENCY (GTA) (Notif 13/2017-CT(R) Entry 1 / Notif 10/2017-IT(R) Entry 2)
        # -------------------------------------------------------------
        has_gta_sac = any(s.startswith("996511") or s.startswith("996791") for s in sac_codes)
        gta_terms = ["goods transport agency", "gta", "consignment note", "bilty", "lr no", "l/r no", "lorry receipt"]
        has_gta_terms = any(t in all_desc_text for t in gta_terms)

        # False positive shields for transport
        non_gta_terms = [
            "cab", "taxi", "passenger", "bus", "flight", "air ticket", "courier",
            "car purchase", "vehicle purchase", "loading charges", "delivery boy"
        ]
        is_ordinary_non_gta = any(nt in all_desc_text for nt in non_gta_terms) and not has_gta_terms and not has_gta_sac

        if (has_gta_sac or has_gta_terms) and not is_ordinary_non_gta:
            # Check forward charge declaration (Annexure V / opted forward charge at 5% or 12%)
            forward_charge_opted = any(k in all_desc_text for k in ("annexure v", "forward charge", "opted to pay gst under forward charge", "declaration under gta forward charge"))
            if forward_charge_opted:
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "GTA",
                    "rcm_reason": "GTA service supplier has explicitly declared payment under Forward Charge (Annexure V option).",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 1 as amended by Notif 05/2022-CT(R)",
                    "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": bool(explicit_rcm_flag is True),
                }

            # Statutory recipient condition: Registered entity, body corporate, factory, society, firm
            if is_recipient_registered or recipient_entity in ("BODY_CORPORATE", "FIRM"):
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "GTA",
                    "rcm_reason": "Goods Transport Agency (GTA) services supplied to registered entity without forward charge declaration.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 1 / Notif 10/2017-IT(R) Entry 2",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            else:
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "GTA",
                    "rcm_reason": "GTA services identified, but recipient registered/specified entity status could not be established.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 1",
                    "rcm_conflict": None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 3. LEGAL SERVICES (Notif 13/2017-CT(R) Entry 2 / Notif 10/2017-IT(R) Entry 3)
        # -------------------------------------------------------------
        has_legal_sac = any(s.startswith("99821") for s in sac_codes)
        legal_terms = ["advocate", "senior advocate", "firm of advocates", "legal advisory", "legal consultation", "legal services", "court representation", "arbitration"]
        has_legal_terms = any(t in all_desc_text for t in legal_terms)

        # Strict false-positive filters for Legal
        legal_false_positives = ["legal software", "software license", "subscription", "scc online", "manupatra", "compliance software", "lexisnexis", "law book", "legal journal"]
        is_legal_software_or_goods = any(fp in all_desc_text for fp in legal_false_positives)

        if (has_legal_sac or has_legal_terms) and not is_legal_software_or_goods:
            # Under Notif 13/2017-CT(R) Entry 2, recipient must be a business entity located in taxable territory.
            # In an enterprise accounts payable / purchase billing system, an inward purchase bill or explicit RCM declaration
            # indicates business entity recipient unless recipient is explicitly personal / non-business.
            has_business_context = is_recipient_registered or recipient_entity in ("BODY_CORPORATE", "FIRM") or explicit_rcm_flag is True or not buyer_name
            if has_business_context:
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "LEGAL_SERVICES",
                    "rcm_reason": "Legal services provided by an advocate / firm of advocates to a business entity in taxable territory.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 2 / Notif 10/2017-IT(R) Entry 3",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            else:
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "LEGAL_SERVICES",
                    "rcm_reason": "Legal services identified, but recipient business entity status could not be established (possible individual/non-business recipient).",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 2",
                    "rcm_conflict": None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 4. SECURITY SERVICES (MANPOWER) (Notif 13/2017-CT(R) Entry 14 w.e.f. 01.01.2019)
        # -------------------------------------------------------------
        has_sec_sac = any(s.startswith("998525") or s.startswith("998529") for s in sac_codes)
        sec_manpower_terms = ["security guard", "security personnel", "manned guarding", "security manpower", "guarding services", "patrol service"]
        has_sec_manpower_terms = any(t in all_desc_text for t in sec_manpower_terms)

        # False-positive filters for Security
        sec_false_positives = [
            "cctv", "camera", "security camera", "security system", "security software",
            "antivirus", "firewall", "biometric", "alarm system", "hardware", "access control machine"
        ]
        is_sec_goods_or_tech = any(fp in all_desc_text for fp in sec_false_positives)

        if (has_sec_sac or has_sec_manpower_terms) and not is_sec_goods_or_tech:
            if supplier_entity == "BODY_CORPORATE":
                # Statutoriily excluded: Body corporate suppliers charge GST under Forward Charge
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "SECURITY_SERVICES",
                    "rcm_reason": "Security services provided by a Body Corporate (Company); falls under Forward Charge per Notif 29/2018-CT(R).",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 14 as amended by Notif 29/2018-CT(R)",
                    "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": bool(explicit_rcm_flag is True),
                }
            elif supplier_entity in ("NON_BODY_CORPORATE", "FIRM") and is_recipient_registered:
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "SECURITY_SERVICES",
                    "rcm_reason": "Security personnel / manned guarding services provided by a non-body corporate supplier to a registered person.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 14 as amended by Notif 29/2018-CT(R)",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            elif supplier_entity == "UNKNOWN":
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "SECURITY_SERVICES",
                    "rcm_reason": "Security services detected, but supplier entity constitution (Body Corporate vs Non-Body Corporate) is unknown.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 14",
                    "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 5. DIRECTOR SERVICES (Notif 13/2017-CT(R) Entry 6 / Notif 10/2017-IT(R) Entry 7)
        # -------------------------------------------------------------
        director_terms = ["director fee", "director sitting fee", "director commission", "directorship services", "sitting fee for attending board"]
        has_director_terms = any(t in all_desc_text for t in director_terms)

        # Strict exclusions: Employee salary / payroll is not supply under Schedule III
        salary_terms = ["salary", "payroll", "wages", "monthly compensation", "remuneration u/s 192", "employee salary"]
        is_employee_salary = any(st in all_desc_text for st in salary_terms)

        if has_director_terms and not is_employee_salary:
            if recipient_entity == "BODY_CORPORATE" or is_recipient_registered:
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "DIRECTOR_SERVICES",
                    "rcm_reason": "Services supplied by a director to the company or body corporate in capacity of director.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 6 / Notif 10/2017-IT(R) Entry 7",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            else:
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "DIRECTOR_SERVICES",
                    "rcm_reason": "Director services detected, but recipient body corporate status is not verified.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 6",
                    "rcm_conflict": None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 6. RENTING OF MOTOR VEHICLE (Notif 13/2017-CT(R) Entry 15 / Notif 22/2019-CT(R))
        # -------------------------------------------------------------
        has_cab_sac = any(s.startswith("996601") or s.startswith("9966") for s in sac_codes)
        mv_rent_terms = ["renting of motor vehicle", "cab rental", "car hire", "vehicle rental with fuel", "cab hire services"]
        has_mv_rent_terms = any(t in all_desc_text for t in mv_rent_terms)

        # False-positive shields
        mv_false_positives = ["car purchase", "vehicle purchase", "car repair", "vehicle maintenance", "spare parts", "fuel expense", "vehicle insurance"]
        is_mv_purchase_or_repair = any(fp in all_desc_text for fp in mv_false_positives)

        if (has_cab_sac or has_mv_rent_terms) and not is_mv_purchase_or_repair:
            if supplier_entity == "BODY_CORPORATE":
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "RENTING_OF_MOTOR_VEHICLE",
                    "rcm_reason": "Renting of motor vehicle supplied by a Body Corporate; falls under Forward Charge per Notif 22/2019-CT(R).",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 15 as amended by Notif 22/2019-CT(R)",
                    "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": bool(explicit_rcm_flag is True),
                }
            elif supplier_entity in ("NON_BODY_CORPORATE", "FIRM") and recipient_entity == "BODY_CORPORATE":
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "RENTING_OF_MOTOR_VEHICLE",
                    "rcm_reason": "Renting of motor vehicle designed to carry passengers with fuel supplied by non-body corporate to body corporate.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 15 as amended by Notif 22/2019-CT(R)",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            elif supplier_entity == "UNKNOWN" or recipient_entity != "BODY_CORPORATE":
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "RENTING_OF_MOTOR_VEHICLE",
                    "rcm_reason": "Motor vehicle renting detected, but statutory supplier (non-body corporate) or recipient (body corporate) conditions cannot be verified.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 15",
                    "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 7. RENTING OF IMMOVABLE PROPERTY OTHER THAN RESIDENTIAL DWELLING
        #    (Notif 13/2017-CT(R) Entry 5AB inserted via Notif 09/2024-CT(R), corrigendum 22-Oct-2024, amended via Notif 07/2025-CT(R))
        # -------------------------------------------------------------
        immovable_rent_terms = ["commercial rent", "office rent", "shop rent", "renting of immovable property", "rent of commercial building", "warehouse rent", "factory rent", "office lease"]
        has_immovable_rent_terms = any(t in all_desc_text for t in immovable_rent_terms)
        is_residential = "residential" in all_desc_text or "dwelling" in all_desc_text

        if has_immovable_rent_terms and not is_residential:
            # Supplier condition: UNREGISTERED person (landlord)
            # Recipient condition: REGISTERED person (excluding composition levy per Notif 07/2025-CT(R))
            supplier_is_unregistered = not vendor_gstin or len(vendor_gstin.strip()) < 15
            recipient_is_composition = any(k in str(af.get("composition") or "").lower() for k in ("yes", "true"))

            if supplier_is_unregistered and is_recipient_registered and not recipient_is_composition:
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "RENTING_IMMOVABLE_PROPERTY_NON_RESIDENTIAL",
                    "rcm_reason": "Renting of immovable property other than residential dwelling by an unregistered supplier to a registered recipient.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 5AB (Notif 09/2024-CT(R) / Notif 07/2025-CT(R))",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }
            elif not supplier_is_unregistered:
                # Registered landlord -> Forward Charge
                return {
                    "is_reverse_charge": False,
                    "rcm_category": "RENTING_IMMOVABLE_PROPERTY_NON_RESIDENTIAL",
                    "rcm_reason": "Renting of immovable property supplied by a registered person; falls under Forward Charge.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 5AB",
                    "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": bool(explicit_rcm_flag is True),
                }

        # -------------------------------------------------------------
        # 8. RENTING OF RESIDENTIAL DWELLING TO REGISTERED PERSON (Notif 13/2017-CT(R) Entry 5AA)
        # -------------------------------------------------------------
        if is_residential and any(r in all_desc_text for r in ("rent", "lease", "tenancy")):
            if is_recipient_registered:
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "RENTING_RESIDENTIAL_DWELLING",
                    "rcm_reason": "Services by way of renting of residential dwelling to a registered person for business / corporate purpose.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 5AA as inserted by Notif 05/2022-CT(R)",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }

        # -------------------------------------------------------------
        # 9. SPONSORSHIP SERVICES (Notif 13/2017-CT(R) Entry 4 / Notif 10/2017-IT(R) Entry 5)
        # -------------------------------------------------------------
        has_sponsorship_sac = any(s.startswith("998397") for s in sac_codes)
        has_sponsorship_terms = any(t in all_desc_text for t in ("sponsorship service", "event sponsorship", "title sponsor"))
        if (has_sponsorship_sac or has_sponsorship_terms) and not any(k in all_desc_text for k in ("software", "hardware", "gift")):
            if recipient_entity in ("BODY_CORPORATE", "FIRM"):
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "SPONSORSHIP_SERVICES",
                    "rcm_reason": "Sponsorship services provided to a body corporate or partnership firm.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 4 / Notif 10/2017-IT(R) Entry 5",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }

        # -------------------------------------------------------------
        # 10. SERVICES OF ARBITRAL TRIBUNAL (Notif 13/2017-CT(R) Entry 3)
        # -------------------------------------------------------------
        if "arbitral tribunal" in all_desc_text or any(s == "998215" for s in sac_codes):
            if is_recipient_registered or recipient_entity in ("BODY_CORPORATE", "FIRM"):
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "ARBITRAL_TRIBUNAL",
                    "rcm_reason": "Services supplied by an arbitral tribunal to a business entity in taxable territory.",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 3",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }

        # -------------------------------------------------------------
        # 11. GOVERNMENT / LOCAL AUTHORITY SERVICES (Notif 13/2017-CT(R) Entry 5)
        # -------------------------------------------------------------
        govt_terms = ["government of", "ministry of", "municipal corporation", "gram panchayat", "department of revenue"]
        is_govt_supplier = any(gt in vendor_name.lower() for gt in govt_terms) or any(gt in all_desc_text for gt in govt_terms)
        govt_exclusions = ["speed post", "express parcel", "passenger transport", "aircraft", "vessel in port", "airport"]
        is_govt_forward_charge = any(ge in all_desc_text for ge in govt_exclusions)

        if is_govt_supplier and not is_govt_forward_charge:
            if is_recipient_registered or recipient_entity in ("BODY_CORPORATE", "FIRM"):
                return {
                    "is_reverse_charge": True,
                    "rcm_category": "GOVERNMENT_SERVICES",
                    "rcm_reason": "Services supplied by Central/State Government, UT, or local authority to a business entity (excluding speed post, passenger transport, port/airport services).",
                    "rcm_notification": "Notif 13/2017-CT(R) Entry 5",
                    "rcm_conflict": "STATUTORY_RCM_OVERRIDES_INVOICE" if explicit_rcm_flag is False else None,
                    "rcm_requires_review": False,
                }

        # -------------------------------------------------------------
        # 12. CONDITIONAL GOODS RCM: METAL SCRAP (Notif 04/2017-CT(R) / Notif 06/2024-CT(R))
        # -------------------------------------------------------------
        has_scrap_hsn = any(s.startswith(("72", "73", "74", "75", "76", "77", "78", "79", "80", "81")) for s in sac_codes)
        has_scrap_terms = any(t in all_desc_text for t in ("metal scrap", "iron scrap", "steel scrap", "copper scrap", "aluminum scrap"))
        if (has_scrap_hsn or has_scrap_terms) and not vendor_gstin and is_recipient_registered:
            return {
                "is_reverse_charge": False,
                "rcm_category": "METAL_SCRAP",
                "rcm_reason": "Potential Metal Scrap RCM under Notif 06/2024-CT(R) from unregistered supplier; requires manual verification of scrap classification.",
                "rcm_notification": "Notif 04/2017-CT(R) as amended by Notif 06/2024-CT(R)",
                "rcm_conflict": None,
                "rcm_requires_review": True,
            }

        # -------------------------------------------------------------
        # 13. SPECIALIZED / UNSUPPORTED RCM CATEGORIES
        #     (Recovery Agent, Insurance Agent, DSA)
        # -------------------------------------------------------------
        if any(t in all_desc_text for t in ("recovery agent", "direct selling agent", "dsa commission")):
            return {
                "is_reverse_charge": False,
                "rcm_category": "SPECIALIZED_FINANCIAL_RCM",
                "rcm_reason": "Specialized RCM service (Recovery Agent/DSA); applicable only when recipient is a Bank/NBFC.",
                "rcm_notification": "Notif 13/2017-CT(R) Entry 8, 9",
                "rcm_conflict": None,
                "rcm_requires_review": True,
            }

        # -------------------------------------------------------------
        # 14. AMBIGUOUS RCM CANDIDATE SIGNALS
        # -------------------------------------------------------------
        # Note: If a term was already matched as a false positive (e.g. CCTV equipment, legal software, car purchase),
        # it is NOT an ambiguous RCM candidate; it is clean Forward Charge.
        is_known_false_positive = is_sec_goods_or_tech or is_legal_software_or_goods or is_mv_purchase_or_repair or is_employee_salary
        if not is_known_false_positive:
            ambiguous_rcm_signals = ["transport", "freight", "cartage", "security personnel", "security guard", "manned guarding", "director fee", "renting of motor vehicle"]
            matched_ambiguous = [sig for sig in ambiguous_rcm_signals if sig in all_desc_text]
            if matched_ambiguous and not is_ordinary_non_gta:
                # We had an RCM-adjacent term, but failed to establish statutory conditions definitively
                return {
                    "is_reverse_charge": False,
                    "rcm_category": None,
                    "rcm_reason": f"Ambiguous transaction facts for potential RCM term(s): {', '.join(matched_ambiguous)}. Unable to establish statutory RCM conditions deterministically.",
                    "rcm_notification": None,
                    "rcm_conflict": "AMBIGUOUS_RCM_FACTS" if explicit_rcm_flag is True else None,
                    "rcm_requires_review": True,
                }

        # -------------------------------------------------------------
        # 15. EXPLICIT INVOICE CONFLICT OR UNRESOLVED STATUTORY CHECK
        # -------------------------------------------------------------
        if explicit_rcm_flag is True:
            # Invoice explicitly declares RCM, but no statutory notified category conditions were satisfied
            return {
                "is_reverse_charge": False,
                "rcm_category": None,
                "rcm_reason": "Invoice declares Reverse Charge (RCM=YES), but transaction facts do not satisfy any notified statutory RCM category.",
                "rcm_notification": None,
                "rcm_conflict": "EXPLICIT_RCM_CONTRADICTS_FACTS",
                "rcm_requires_review": True,
            }

        # Clean Forward Charge default
        return {
            "is_reverse_charge": False,
            "rcm_category": None,
            "rcm_reason": "Standard Forward Charge supply (no statutory RCM category identified).",
            "rcm_notification": None,
            "rcm_conflict": None,
            "rcm_requires_review": False,
        }

    def evaluate_gst(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates GST rules, resolves Place of Supply (POS), determines supply type,
        validates tax structure against extracted values, and checks line mathematical consistency.
        """
        if not isinstance(invoice_data, dict):
            invoice_data = {}

        data_obj = invoice_data.get("data") if isinstance(invoice_data.get("data"), dict) else invoice_data

        errors: List[str] = []
        warnings: List[str] = []

        # 1. Vendor / Supplier GSTIN & State
        raw_vendor_gstin = str(data_obj.get("vendor_gstin") or "").strip() or None
        is_vendor_gstin_valid, vendor_gstin = validate_gstin(raw_vendor_gstin)
        supplier_state_code, supplier_state_name = extract_state_code_from_gstin(vendor_gstin)

        # Fallback to vendor address state if GSTIN is absent or invalid
        if not supplier_state_code:
            v_addr = str(data_obj.get("vendor_address") or "")
            s_code, s_name = resolve_state_from_text(v_addr)
            if s_code:
                supplier_state_code, supplier_state_name = s_code, s_name
                warnings.append(f"Supplier state resolved from vendor address ({s_name}).")
            elif raw_vendor_gstin:
                warnings.append(f"Vendor GSTIN '{raw_vendor_gstin}' is invalid or non-standard format.")

        # 2. Customer / Buyer GSTIN & State
        raw_buyer_gstin = str(data_obj.get("customer_gstin") or data_obj.get("buyer_gstin") or data_obj.get("recipient_gstin") or "").strip() or None
        is_buyer_gstin_valid, buyer_gstin = validate_gstin(raw_buyer_gstin)
        buyer_state_code, buyer_state_name = extract_state_code_from_gstin(buyer_gstin)

        # Fallback to customer address state if buyer GSTIN missing
        if not buyer_state_code:
            c_addr = str(data_obj.get("customer_address") or "")
            b_code, b_name = resolve_state_from_text(c_addr)
            if b_code:
                buyer_state_code, buyer_state_name = b_code, b_name
                warnings.append(f"Buyer state resolved from customer address ({b_name}).")

        # 3. Place of Supply (POS) Determination (Priority: Explicit POS > Buyer GSTIN Fallback)
        pos_state_code: Optional[str] = None
        pos_state_name: Optional[str] = None
        pos_source: str = "unresolved"

        exp_code, exp_name = extract_explicit_place_of_supply(data_obj)
        if exp_code:
            pos_state_code, pos_state_name = exp_code, exp_name
            pos_source = "explicit_invoice"
        elif buyer_state_code:
            pos_state_code, pos_state_name = buyer_state_code, buyer_state_name
            pos_source = "buyer_gstin_fallback"
            warnings.append("Place of supply established using buyer GSTIN/address state as fallback.")
        else:
            warnings.append("Place of supply could not be reliably established.")

        # 4. Supply Type Determination
        supply_type: str = "REVIEW_REQUIRED"

        if supplier_state_code and pos_state_code:
            if supplier_state_code == pos_state_code:
                supply_type = "INTRA_STATE"
            else:
                supply_type = "INTER_STATE"
        else:
            supply_type = "REVIEW_REQUIRED"

        # 4b. Deterministic Reverse Charge Mechanism (RCM) Evaluation
        rcm_eval = self._evaluate_rcm(
            data_obj=data_obj,
            vendor_gstin=vendor_gstin,
            buyer_gstin=buyer_gstin,
            supplier_state_code=supplier_state_code,
            pos_state_code=pos_state_code,
            supply_type=supply_type,
        )
        is_reverse_charge: bool = rcm_eval.get("is_reverse_charge", False)
        rcm_category: Optional[str] = rcm_eval.get("rcm_category")
        rcm_reason: str = rcm_eval.get("rcm_reason") or "Forward charge supply"
        rcm_notification: Optional[str] = rcm_eval.get("rcm_notification")
        rcm_conflict: Optional[str] = rcm_eval.get("rcm_conflict")
        rcm_requires_review: bool = rcm_eval.get("rcm_requires_review", False)

        if rcm_conflict:
            warnings.append(f"RCM Conflict: {rcm_conflict} - {rcm_reason}")
        elif rcm_requires_review:
            warnings.append(f"RCM Notice: {rcm_reason}")

        # Supporting cross-check: buyer GSTIN vs supplier GSTIN
        if supplier_state_code and buyer_state_code:
            if (supplier_state_code == buyer_state_code) and supply_type == "INTER_STATE" and pos_source == "explicit_invoice":
                warnings.append(
                    f"Cross-check note: Vendor GSTIN ({supplier_state_name}) and Buyer GSTIN ({buyer_state_name}) have same registration state, but explicit invoice POS is {pos_state_name} (Inter-State)."
                )

        # 5. Extract Stored Values (Zero Data Loss & Provenance)
        af = data_obj.get("additional_fields") or {}
        ext_cgst = extract_tax_value(data_obj, "cgst")
        ext_sgst = extract_tax_value(data_obj, "sgst")
        ext_igst = extract_tax_value(data_obj, "igst")
        ext_tax_total = (
            parse_clean_numeric(data_obj.get("tax_total"))
            or parse_clean_numeric(data_obj.get("total_tax"))
            or parse_clean_numeric(af.get("Tax Amount"))
            or parse_clean_numeric(af.get("tax_amount"))
            or parse_clean_numeric(af.get("Total Tax"))
            or parse_clean_numeric(af.get("Tax Total"))
            or (round(ext_cgst + ext_sgst, 2) if ext_cgst is not None and ext_sgst is not None else None)
            or ext_igst
        )

        # 6. Line-Level Mathematical Validation
        line_items = data_obj.get("line_items") or []
        calc_cgst: float = 0.0
        calc_sgst: float = 0.0
        calc_igst: float = 0.0
        has_line_math: bool = False

        line_validations: List[Dict[str, Any]] = []

        for idx, item in enumerate(line_items, 1):
            if not isinstance(item, dict):
                continue

            desc = str(item.get("description") or f"Item {idx}")
            taxable = parse_clean_numeric(
                item.get("taxable_amount")
                or item.get("taxable")
                or item.get("pretax_amount")
                or (
                    float(item["unit_price"]) * float(item["quantity"])
                    if item.get("unit_price") is not None and item.get("quantity") is not None
                    else None
                )
            )

            item_cgst_r = parse_clean_numeric(item.get("cgst_rate"))
            item_sgst_r = parse_clean_numeric(item.get("sgst_rate"))
            item_igst_r = parse_clean_numeric(item.get("igst_rate"))
            item_gst_r = parse_clean_numeric(item.get("gst_rate") or item.get("tax_rate"))

            item_cgst_a = parse_clean_numeric(item.get("cgst_amount"))
            item_sgst_a = parse_clean_numeric(item.get("sgst_amount"))
            item_igst_a = parse_clean_numeric(item.get("igst_amount"))

            # Derive expected line components based on supply type
            expected_line_cgst = None
            expected_line_sgst = None
            expected_line_igst = None

            if taxable is not None and taxable > 0:
                has_line_math = True
                if supply_type == "INTRA_STATE":
                    rate = item_cgst_r or (item_gst_r / 2.0 if item_gst_r else 0.0)
                    expected_line_cgst = round((taxable * rate / 100.0), 2)
                    rate_s = item_sgst_r or (item_gst_r / 2.0 if item_gst_r else 0.0)
                    expected_line_sgst = round((taxable * rate_s / 100.0), 2)
                    calc_cgst += expected_line_cgst
                    calc_sgst += expected_line_sgst
                elif supply_type == "INTER_STATE":
                    rate_i = item_igst_r or item_gst_r or ((item_cgst_r or 0.0) + (item_sgst_r or 0.0))
                    expected_line_igst = round((taxable * rate_i / 100.0), 2)
                    calc_igst += expected_line_igst

            line_validations.append({
                "line_index": idx,
                "description": desc,
                "taxable_amount": taxable,
                "extracted_cgst": item_cgst_a,
                "extracted_sgst": item_sgst_a,
                "extracted_igst": item_igst_a,
                "calculated_cgst": expected_line_cgst,
                "calculated_sgst": expected_line_sgst,
                "calculated_igst": expected_line_igst,
            })

        calc_cgst = round(calc_cgst, 2)
        calc_sgst = round(calc_sgst, 2)
        calc_igst = round(calc_igst, 2)
        calculated_gst_total = round(calc_cgst + calc_sgst + calc_igst, 2)

        # 7. Tax Structure Consistency & Status Validation
        validation_status = "PASSED"

        if supply_type == "INTRA_STATE":
            if ext_igst and ext_igst > 0:
                validation_status = "GST_MISMATCH"
                errors.append(f"Unexpected IGST (₹{ext_igst:,.2f}) charged on Intra-State supply (Supplier: {supplier_state_name}, POS: {pos_state_name}).")
            
            # Intra-state CGST / SGST pairing validation
            has_cgst = ext_cgst is not None
            has_sgst = ext_sgst is not None
            if has_cgst != has_sgst:
                validation_status = "GST_MISMATCH"
                present_comp = "CGST" if has_cgst else "SGST"
                missing_comp = "SGST" if has_cgst else "CGST"
                present_val = ext_cgst if has_cgst else ext_sgst
                errors.append(f"Incomplete Intra-State GST breakdown: {present_comp} (₹{present_val:,.2f}) present without corresponding {missing_comp}.")
            elif has_cgst and has_sgst:
                raw_cgst_sgst_diff = abs(ext_cgst - ext_sgst)
                if raw_cgst_sgst_diff > 1.0:
                    validation_status = "GST_MISMATCH"
                    errors.append(f"Intra-State CGST (₹{ext_cgst:,.2f}) and SGST (₹{ext_sgst:,.2f}) mismatch (diff: ₹{round(raw_cgst_sgst_diff, 4):,.4f} exceeds ₹1.00 tolerance).")

            if ext_cgst is None and ext_sgst is None and ext_tax_total and ext_tax_total > 0:
                warnings.append("Tax total is charged, but explicit CGST/SGST breakdown is missing at invoice header.")
        elif supply_type == "INTER_STATE":
            if (ext_cgst and ext_cgst > 0) or (ext_sgst and ext_sgst > 0):
                validation_status = "GST_MISMATCH"
                errors.append(f"Unexpected CGST/SGST charged on Inter-State supply (Supplier: {supplier_state_name}, POS: {pos_state_name}). Expected IGST.")
            if ext_igst is None and ext_tax_total and ext_tax_total > 0:
                warnings.append("Tax total is charged, but explicit IGST is missing at invoice header.")
        else:
            validation_status = "REVIEW_REQUIRED"
            warnings.append("Supply type could not be determined definitively. Manual review required.")

        # Check total discrepancy if both extracted and line math exist
        if ext_tax_total is not None and has_line_math and calculated_gst_total > 0:
            diff = abs(ext_tax_total - calculated_gst_total)
            if diff > 2.0:  # Rounding tolerance threshold
                warnings.append(f"Discrepancy of ₹{diff:,.2f} between extracted Tax Total (₹{ext_tax_total:,.2f}) and line-level GST sum (₹{calculated_gst_total:,.2f}).")

        # RCM Review Gate: If RCM determination requires review or has conflict, flag validation_status
        if rcm_requires_review and validation_status == "PASSED":
            validation_status = "REVIEW_REQUIRED"

        return {
            "supplier_state_code": supplier_state_code,
            "supplier_state_name": supplier_state_name,
            "buyer_state_code": buyer_state_code,
            "buyer_state_name": buyer_state_name,
            "place_of_supply_state_code": pos_state_code,
            "place_of_supply_state_name": pos_state_name,
            "place_of_supply_source": pos_source,
            "supply_type": supply_type,
            "is_reverse_charge": is_reverse_charge,
            "rcm_category": rcm_category,
            "rcm_reason": rcm_reason,
            "rcm_notification": rcm_notification,
            "rcm_conflict": rcm_conflict,
            "rcm_requires_review": rcm_requires_review,
            "extracted": {
                "cgst_amount": ext_cgst,
                "sgst_amount": ext_sgst,
                "igst_amount": ext_igst,
                "tax_total": ext_tax_total,
            },
            "calculated": {
                "cgst_amount": calc_cgst if supply_type == "INTRA_STATE" else 0.0,
                "sgst_amount": calc_sgst if supply_type == "INTRA_STATE" else 0.0,
                "igst_amount": calc_igst if supply_type == "INTER_STATE" else 0.0,
                "gst_total": calculated_gst_total,
            },
            "line_validations": line_validations,
            "validation_status": validation_status,
            "errors": errors,
            "warnings": warnings,
        }


gst_engine = GSTEngine()
