"""
Unit and Regression Test Suite for Date Normalization and Export Safety Checks.
Covers:
- 02-Aug-2026 -> 2026-08-02
- 18-Jul-2026 -> 2026-07-18
- 02/08/2026 -> 2026-08-02 (Indian dayfirst standard)
- 02-08-2026 -> 2026-08-02
- 02 Aug 2026 -> 2026-08-02
- 02-Aug-26 -> 2026-08-02
- 2 August 2026 -> 2026-08-02
- August 2, 2026 -> 2026-08-02
- Due date >= invoice date validation (valid vs invalid)
- Export safety check blocking due_date < invoice_date before Zoho call
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.date_utils import parse_and_normalize_date, validate_invoice_due_dates
from app.db.models import Invoice, ZohoConnection, JournalEntry
from app.services.export_service import export_service


def test_date_normalization_formats():
    """Verify various Indian and standard date formats correctly normalize to ISO YYYY-MM-DD."""
    # Strict Indian standard DD/MM/YYYY tests
    assert parse_and_normalize_date("18/07/2026") == "2026-07-18"
    assert parse_and_normalize_date("02/08/2026") == "2026-08-02"
    assert parse_and_normalize_date("31/08/2026") == "2026-08-31"
    assert parse_and_normalize_date("01/04/2026") == "2026-04-01"

    # Invariant: 02/08/2026 must NEVER become 2026-02-08
    assert parse_and_normalize_date("02/08/2026") != "2026-02-08"

    # Named month and hyphen formats
    assert parse_and_normalize_date("02-Aug-2026") == "2026-08-02"
    assert parse_and_normalize_date("18-Jul-2026") == "2026-07-18"
    assert parse_and_normalize_date("02-08-2026") == "2026-08-02"
    assert parse_and_normalize_date("02 Aug 2026") == "2026-08-02"
    assert parse_and_normalize_date("02-Aug-26") == "2026-08-02"
    assert parse_and_normalize_date("2 August 2026") == "2026-08-02"
    assert parse_and_normalize_date("August 2, 2026") == "2026-08-02"
    assert parse_and_normalize_date("2026-08-02") == "2026-08-02"
    assert parse_and_normalize_date("31/12/2025") == "2025-12-31"


def test_due_date_validation():
    """Verify validate_invoice_due_dates correctly accepts due >= inv and rejects due < inv."""
    # Valid Cases
    is_valid, err = validate_invoice_due_dates("2026-07-18", "2026-08-02")
    assert is_valid is True
    assert err is None

    is_valid, err = validate_invoice_due_dates("18-Jul-2026", "02-Aug-2026")
    assert is_valid is True
    assert err is None

    is_valid, err = validate_invoice_due_dates("2026-07-18", "2026-07-18")
    assert is_valid is True
    assert err is None

    # Invalid Cases (Due date before invoice date)
    is_valid, err = validate_invoice_due_dates("2026-07-18", "2026-02-08")
    assert is_valid is False
    assert "cannot be earlier than invoice date" in err

    is_valid, err = validate_invoice_due_dates("18-Jul-2026", "08-Feb-2026")
    assert is_valid is False
    assert "cannot be earlier than invoice date" in err


@pytest.mark.asyncio
async def test_export_safety_check_blocks_earlier_due_date():
    """Verify export_service stops and raises ValueError locally if due_date < invoice_date before calling Zoho."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"

    mock_inv = Invoice(
        id=inv_id,
        tenant_id=tenant_id,
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-DATE-ERR",
                "invoice_date": "2026-07-18",
                "due_date": "2026-02-08",  # Invalid earlier date
                "vendor_name": "NimbusStack Cloud Solutions",
                "subtotal": 50000.0,
                "total_amount": 59000.0,
                "line_items": [{"description": "Cloud Servers", "taxable_amount": 50000.0}],
            }
        },
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_1", "approved_account_name": "Cloud Expenses"}]
        },
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        status="BALANCED",
        is_balanced=True,
    )

    mock_conn = ZohoConnection(id=uuid.uuid4(), tenant_id=tenant_id, status="CONNECTED", organization_id="ORG_1")

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_conn)),
    ]

    with patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill:
        with pytest.raises(ValueError) as exc_info:
            await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)

        assert "Due date (08/02/2026) cannot be earlier than invoice date (18/07/2026)" in str(exc_info.value)
        # Verify Zoho API was NOT called
        mock_create_bill.assert_not_called()
