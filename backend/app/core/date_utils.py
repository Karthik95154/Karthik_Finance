"""
Robust Indian & International Date Parsing and Normalization Utility.
Supports:
- DD-Mon-YYYY (e.g. 02-Aug-2026, 18-Jul-2026, 02 Aug 2026, 2 August 2026, 02-Aug-26)
- DD/MM/YYYY and DD-MM-YYYY (Indian standard convention dayfirst=True)
- YYYY-MM-DD (ISO 8601 standard)
- Mon DD, YYYY (e.g. August 2, 2026, Aug 02, 2026)
- Natural text extraction fallback
"""

import re
import logging
from datetime import datetime, date
from typing import Optional, Union

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_and_normalize_date(date_val: Union[str, date, datetime, None]) -> Optional[str]:
    """
    Parses and normalizes arbitrary invoice/due date values into standard ISO 'YYYY-MM-DD' string format.
    Ensures Indian date conventions (Day first) are respected without ambiguous MM/DD confusion.
    """
    if not date_val:
        return None

    if isinstance(date_val, datetime):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, date):
        return date_val.strftime("%Y-%m-%d")

    raw_str = str(date_val).strip()
    if not raw_str or raw_str.lower() in ("none", "null", "n/a", "-"):
        return None

    # 1. Check already normalized ISO YYYY-MM-DD
    iso_match = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", raw_str)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            return date(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 2. Check Word Month Formats (e.g., '02-Aug-2026', '2 August 2026', '18-Jul-26', 'Aug 02, 2026')
    # Pattern A: DD[- /.]Month[- /.]YYYY or YY
    word_dmy = re.search(
        r"\b(\d{1,2})[\s\-/\.,]+([a-zA-Z]{3,10})[\s\-/\.,]+(\d{2,4})\b",
        raw_str,
        re.IGNORECASE,
    )
    if word_dmy:
        d_val = int(word_dmy.group(1))
        m_str = word_dmy.group(2).lower()
        y_val = int(word_dmy.group(3))
        if y_val < 100:
            y_val += 2000 if y_val < 70 else 1900
        m_val = MONTH_MAP.get(m_str[:3]) or MONTH_MAP.get(m_str)
        if m_val and 1 <= d_val <= 31:
            try:
                return date(y_val, m_val, d_val).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Pattern B: Month[- /.]DD[- /.]YYYY (e.g. 'August 2, 2026' or 'Aug 02, 2026')
    word_mdy = re.search(
        r"\b([a-zA-Z]{3,10})[\s\-/\.,]+(\d{1,2})[\s\-/\.,]+(\d{2,4})\b",
        raw_str,
        re.IGNORECASE,
    )
    if word_mdy:
        m_str = word_mdy.group(1).lower()
        d_val = int(word_mdy.group(2))
        y_val = int(word_mdy.group(3))
        if y_val < 100:
            y_val += 2000 if y_val < 70 else 1900
        m_val = MONTH_MAP.get(m_str[:3]) or MONTH_MAP.get(m_str)
        if m_val and 1 <= d_val <= 31:
            try:
                return date(y_val, m_val, d_val).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 3. Check Numeric Indian Standard Formats: DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    num_dmy = re.search(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b", raw_str)
    if num_dmy:
        d_val = int(num_dmy.group(1))
        m_val = int(num_dmy.group(2))
        y_val = int(num_dmy.group(3))
        if y_val < 100:
            y_val += 2000 if y_val < 70 else 1900

        # In Indian tax invoices, DD/MM/YYYY is standard.
        # If d_val > 12 and m_val <= 12, it's definitively DD/MM/YYYY.
        # If m_val > 12 and d_val <= 12, it's MM/DD/YYYY.
        if d_val > 12 and m_val <= 12:
            try:
                return date(y_val, m_val, d_val).strftime("%Y-%m-%d")
            except ValueError:
                pass
        elif m_val > 12 and d_val <= 12:
            try:
                return date(y_val, d_val, m_val).strftime("%Y-%m-%d")
            except ValueError:
                pass
        elif 1 <= d_val <= 31 and 1 <= m_val <= 12:
            # Default to Indian convention day-first
            try:
                return date(y_val, m_val, d_val).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 4. Fallback to python-dateutil parser with dayfirst=True
    try:
        from dateutil import parser as dt_parser
        parsed_dt = dt_parser.parse(raw_str, dayfirst=True, fuzzy=True)
        return parsed_dt.strftime("%Y-%m-%d")
    except Exception:
        pass

def format_to_indian_standard(date_val: Union[str, date, datetime, None]) -> Optional[str]:
    """
    Converts any parsed/normalized date into project-wide standard user-facing 'DD/MM/YYYY'.
    Examples:
        '2026-07-18' -> '18/07/2026'
        '2026-08-02' -> '02/08/2026'
    """
    if not date_val:
        return None

    iso_date = parse_and_normalize_date(date_val)
    if not iso_date:
        return None

    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d").date()
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def format_to_zoho_date(date_val: Union[str, date, datetime, None]) -> Optional[str]:
    """
    Converts date to Zoho Books API required format 'YYYY-MM-DD'.
    Preserves exact calendar day and month without swapping.
    """
    return parse_and_normalize_date(date_val)


def validate_invoice_due_dates(invoice_date_str: Optional[str], due_date_str: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Validates that due date is on or after invoice date.
    Returns (is_valid, error_message).
    """
    if not invoice_date_str or not due_date_str:
        return True, None

    norm_inv = parse_and_normalize_date(invoice_date_str)
    norm_due = parse_and_normalize_date(due_date_str)

    if not norm_inv or not norm_due:
        return True, None

    # Check if string matches YYYY-MM-DD
    try:
        inv_dt = datetime.strptime(norm_inv, "%Y-%m-%d").date()
        due_dt = datetime.strptime(norm_due, "%Y-%m-%d").date()
    except ValueError:
        return True, None

    if due_dt < inv_dt:
        inv_disp = format_to_indian_standard(norm_inv) or norm_inv
        due_disp = format_to_indian_standard(norm_due) or norm_due
        return False, f"Due date ({due_disp}) cannot be earlier than invoice date ({inv_disp})."

    return True, None


def is_date_in_closed_period(
    target_date: Union[str, date, datetime, None],
    books_closed_through_date: Union[str, date, datetime, None],
) -> bool:
    """
    Pure calendar-date comparison:
    target_date <= books_closed_through_date => CLOSED (True)
    target_date > books_closed_through_date => OPEN (False)
    If books_closed_through_date is None/empty => OPEN (False)
    """
    if not target_date or not books_closed_through_date:
        return False

    norm_target = parse_and_normalize_date(target_date)
    norm_lock = parse_and_normalize_date(books_closed_through_date)
    if not norm_target or not norm_lock:
        return False

    try:
        t_dt = datetime.strptime(norm_target, "%Y-%m-%d").date()
        l_dt = datetime.strptime(norm_lock, "%Y-%m-%d").date()
        return t_dt <= l_dt
    except (ValueError, TypeError):
        return False


def check_accounting_period(
    document_date: Union[str, date, datetime, None],
    posting_date: Union[str, date, datetime, None],
    books_closed_through_date: Union[str, date, datetime, None],
    period_resolution: Optional[str] = "NONE",
) -> dict:
    """
    Authoritative evaluation of accounting period status.
    Uses calendar-date comparison strictly.
    """
    norm_doc = parse_and_normalize_date(document_date)
    norm_lock = parse_and_normalize_date(books_closed_through_date)
    effective_posting = parse_and_normalize_date(posting_date) or norm_doc

    is_doc_closed = is_date_in_closed_period(norm_doc, norm_lock)
    is_posting_closed = is_date_in_closed_period(effective_posting, norm_lock)

    # Resolution validity
    resolution_val = (period_resolution or "NONE").upper()
    is_resolved = False
    resolution_error = None

    if not is_doc_closed:
        is_resolved = True
    else:
        if resolution_val == "POST_TO_OPEN_PERIOD":
            if is_posting_closed:
                resolution_error = f"Selected posting date ({format_to_indian_standard(effective_posting)}) is still within the closed period (Books closed through {format_to_indian_standard(norm_lock)}). Posting date must be strictly after the closed date."
            else:
                is_resolved = True
        elif resolution_val == "PRIOR_PERIOD_EXCEPTION":
            is_resolved = True
        elif resolution_val == "FLAGGED_FOR_AUDIT":
            is_resolved = False
            resolution_error = "Invoice is flagged for audit and blocked from accounting approval."
        else:
            is_resolved = False
            resolution_error = f"Invoice document date ({format_to_indian_standard(norm_doc)}) is in a closed accounting period (Books closed through {format_to_indian_standard(norm_lock)}). A period resolution must be selected."

    return {
        "is_closed_period": is_doc_closed,
        "is_doc_date_closed": is_doc_closed,
        "is_posting_date_closed": is_posting_closed,
        "is_resolved": is_resolved,
        "resolution_error": resolution_error,
        "document_date": norm_doc,
        "document_date_formatted": format_to_indian_standard(norm_doc),
        "posting_date": effective_posting,
        "posting_date_formatted": format_to_indian_standard(effective_posting),
        "books_closed_through_date": norm_lock,
        "books_closed_through_date_formatted": format_to_indian_standard(norm_lock) if norm_lock else None,
        "period_resolution": resolution_val,
    }
