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
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val) if not (isinstance(val, float) and (val != val)) else None
    if isinstance(val, str):
        clean = val.strip().replace(",", "")
        clean = re.sub(r"^(?:Rupees|Rupee|Rs\.?|INR|₹)\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*(?:/-\s*|Only\s*)$", "", clean, flags=re.IGNORECASE)
        clean = clean.strip()
        negative = clean.startswith("(") and clean.endswith(")")
        clean = clean.replace("(", "").replace(")", "").strip()
        try:
            num = float(clean)
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
    }.get(tax_type, [])

    # 1. Top-level keys
    for src in [data, data_obj]:
        for k in exact_keys:
            if k in src and src[k] is not None and src[k] != "":
                val = parse_clean_numeric(src[k])
                if val is not None:
                    return val
            upper_k = k.upper()
            if upper_k in src and src[upper_k] is not None and src[upper_k] != "":
                val = parse_clean_numeric(src[upper_k])
                if val is not None:
                    return val

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
                            upper_k = k.upper()
                            if upper_k in target and target[upper_k] is not None and target[upper_k] != "":
                                val = parse_clean_numeric(target[upper_k])
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


class GSTEngine:
    """Deterministic GST Rule & Validation Engine."""

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
        is_reverse_charge: bool = False

        # Check explicit reverse charge indicators
        af = data_obj.get("additional_fields") or {}
        rc_text = str(
            af.get("Whether tax is payable under Reverse Charge?")
            or af.get("reverse_charge")
            or data_obj.get("reverse_charge")
            or ""
        ).lower()
        if "yes" in rc_text or rc_text == "true":
            is_reverse_charge = True

        if supplier_state_code and pos_state_code:
            if supplier_state_code == pos_state_code:
                supply_type = "INTRA_STATE"
            else:
                supply_type = "INTER_STATE"
        else:
            supply_type = "REVIEW_REQUIRED"

        # Supporting cross-check: buyer GSTIN vs supplier GSTIN
        if supplier_state_code and buyer_state_code:
            if (supplier_state_code == buyer_state_code) and supply_type == "INTER_STATE" and pos_source == "explicit_invoice":
                warnings.append(
                    f"Cross-check note: Vendor GSTIN ({supplier_state_name}) and Buyer GSTIN ({buyer_state_name}) have same registration state, but explicit invoice POS is {pos_state_name} (Inter-State)."
                )

        # 5. Extract Stored Values (Zero Data Loss & Provenance)
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
