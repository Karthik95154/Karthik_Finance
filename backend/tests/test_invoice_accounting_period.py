"""
Comprehensive test suite for:
Invoice Accounting-Period Indicator + Previous-FY Customer Confirmation.

Scenarios tested:
1. Current month
2. Previous month / current FY
3. Previous FY
4. March 31
5. April 1
6. January
7. December
8. Missing date
9. Invalid date
10. Previous FY + Continue decision
11. Previous FY + Cancel decision
12. Backend rejects invalid/fake Continue/Cancel
13. Existing flow unchanged for current/previous month
14. HITL date correction produces correct final period
15. Previous-FY Cancel does not start accounting processing
"""

import pytest
from datetime import date, datetime
import uuid
from app.core.date_utils import (
    get_indian_financial_year,
    calculate_invoice_accounting_period,
    parse_and_normalize_date,
)
from app.db.models import Invoice
from app.schemas.invoice import InvoiceStatusResponse, PeriodDecisionRequest


# ============================================================================
# 1-9: DATE LOGIC & EDGE CASES (Indian FY: April 1 -> March 31)
# ============================================================================

def test_indian_financial_year_boundaries():
    # April 1 is start of FY
    assert get_indian_financial_year(date(2026, 4, 1)) == (2026, 2027)
    # March 31 is end of FY
    assert get_indian_financial_year(date(2026, 3, 31)) == (2025, 2026)
    # January is within the same FY that started in previous calendar year
    assert get_indian_financial_year(date(2027, 1, 15)) == (2026, 2027)
    # December is within current calendar year FY
    assert get_indian_financial_year(date(2026, 12, 31)) == (2026, 2027)


def test_scenario_1_july_2026():
    # July 2026 -> Invoice Month: July 2026 (Current FY when ref is Sep 2026)
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2026-07-31", ref_date=ref)
    assert message == "Invoice Month: July 2026"
    assert month_name == "July 2026"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_2_august_2026():
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2026-08-15", ref_date=ref)
    assert message == "Invoice Month: August 2026"
    assert month_name == "August 2026"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_3_september_2026():
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2026-09-07", ref_date=ref)
    assert message == "Invoice Month: September 2026"
    assert month_name == "September 2026"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_4_december_2026():
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2026-12-25", ref_date=ref)
    assert message == "Invoice Month: December 2026"
    assert month_name == "December 2026"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_5_january_2027():
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2027-01-10", ref_date=ref)
    assert message == "Invoice Month: January 2027"
    assert month_name == "January 2027"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_6_march_31_2026_previous_fy():
    # When current date is in FY 2026-2027 (e.g. Sep 2026),
    # March 31, 2026 belongs to FY 2025-2026 (Previous Financial Year)
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2026-03-31", ref_date=ref)
    assert message == "Invoice Month: March 2026"
    assert month_name == "March 2026"
    assert category == "PREVIOUS_FINANCIAL_YEAR"


def test_scenario_7_april_1_2026_current_fy():
    # April 1, 2026 belongs to FY 2026-2027 (Current Financial Year)
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2026-04-01", ref_date=ref)
    assert message == "Invoice Month: April 2026"
    assert month_name == "April 2026"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_8_march_31_2027_current_fy():
    # March 31, 2027 belongs to FY 2026-2027 (Current Financial Year)
    ref = date(2026, 9, 15)
    category, message, month_name = calculate_invoice_accounting_period("2027-03-31", ref_date=ref)
    assert message == "Invoice Month: March 2027"
    assert month_name == "March 2027"
    assert category == "CURRENT_FINANCIAL_YEAR"


def test_scenario_9_missing_date():
    # Missing date should return None and not invent a month or period
    cat, msg, month_name = calculate_invoice_accounting_period(None)
    assert cat is None
    assert msg is None
    assert month_name is None

    cat2, msg2, month_name2 = calculate_invoice_accounting_period("")
    assert cat2 is None
    assert msg2 is None
    assert month_name2 is None


def test_scenario_10_invalid_date():
    # Invalid date strings should safely return None
    cat, msg, month_name = calculate_invoice_accounting_period("invalid-date-string")
    assert cat is None
    assert msg is None
    assert month_name is None

    cat2, msg2, month_name2 = calculate_invoice_accounting_period("2026-99-99")
    assert cat2 is None
    assert msg2 is None
    assert month_name2 is None



# ============================================================================
# 10-15: ENDPOINT, TRANSITION & WORKFLOW BEHAVIOR
# ============================================================================

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.api.v1.invoices import decide_invoice_period
from app.api.v1.hitl import approve_extraction_hitl, ExtractionApproveRequest


@pytest.mark.asyncio
async def test_scenario_10_previous_fy_continue():
    inv_id = uuid.uuid4()
    mock_invoice = MagicMock(spec=Invoice)
    mock_invoice.id = inv_id
    mock_invoice.status = "HITL_REVIEW"
    mock_invoice.period_category = "PREVIOUS_FINANCIAL_YEAR"
    mock_invoice.period_decision = "PENDING"
    mock_invoice.current_vlm_output = {"data": {"invoice_date": "2020-05-10"}}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    mock_user = MagicMock()
    mock_user.tenant_id = "tenant-1"
    mock_user.role = "CUSTOMER"
    mock_user.email = "cust@example.com"
    mock_user.id = "user-1"

    payload = PeriodDecisionRequest(decision="CONTINUE")

    with patch("app.api.v1.invoices.get_user_filter", return_value=True):
        resp = await decide_invoice_period(
            invoice_id=inv_id,
            payload=payload,
            current_user=mock_user,
            db=mock_db,
        )

    assert resp["period_decision"] == "CONTINUE"
    assert mock_invoice.period_decision == "CONTINUE"
    assert mock_invoice.status == "HITL_REVIEW"  # Existing workflow resumed
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_scenario_11_previous_fy_cancel():
    inv_id = uuid.uuid4()
    mock_invoice = MagicMock(spec=Invoice)
    mock_invoice.id = inv_id
    mock_invoice.status = "HITL_REVIEW"
    mock_invoice.period_category = "PREVIOUS_FINANCIAL_YEAR"
    mock_invoice.period_decision = "PENDING"
    mock_invoice.current_vlm_output = {"data": {"invoice_date": "2020-05-10"}}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    mock_user = MagicMock()
    mock_user.tenant_id = "tenant-1"
    mock_user.role = "CUSTOMER"
    mock_user.email = "cust@example.com"
    mock_user.id = "user-1"

    payload = PeriodDecisionRequest(decision="CANCEL")

    with patch("app.api.v1.invoices.get_user_filter", return_value=True):
        resp = await decide_invoice_period(
            invoice_id=inv_id,
            payload=payload,
            current_user=mock_user,
            db=mock_db,
        )

    assert resp["period_decision"] == "CANCELLED"
    assert resp["status"] == "CANCELLED"
    assert mock_invoice.period_decision == "CANCELLED"
    assert mock_invoice.status == "CANCELLED"
    assert "cancelled by user" in mock_invoice.error_message
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_scenario_12_backend_rejects_invalid_or_fake_decisions():
    inv_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_db = AsyncMock()

    # 12a: Invalid decision string
    with pytest.raises(HTTPException) as exc_info:
        await decide_invoice_period(
            invoice_id=inv_id,
            payload=PeriodDecisionRequest(decision="FOOBAR"),
            current_user=mock_user,
            db=mock_db,
        )
    assert exc_info.value.status_code == 400

    # 12b: Invoice not in PREVIOUS_FINANCIAL_YEAR
    mock_invoice = MagicMock(spec=Invoice)
    mock_invoice.id = inv_id
    mock_invoice.status = "HITL_REVIEW"
    mock_invoice.period_category = "CURRENT_MONTH"
    mock_invoice.period_decision = "NOT_REQUIRED"
    mock_invoice.current_vlm_output = {"data": {"invoice_date": date.today().isoformat()}}

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    with patch("app.api.v1.invoices.get_user_filter", return_value=True):
        with pytest.raises(HTTPException) as exc_info:
            await decide_invoice_period(
                invoice_id=inv_id,
                payload=PeriodDecisionRequest(decision="CONTINUE"),
                current_user=mock_user,
                db=mock_db,
            )
        assert exc_info.value.status_code == 400
        assert "not required" in exc_info.value.detail.lower()

    # 12c: Invoice not in post-VLM HITL_REVIEW state (e.g. COMPLETED or UPLOADED)
    mock_invoice.period_category = "PREVIOUS_FINANCIAL_YEAR"
    mock_invoice.current_vlm_output = {"data": {"invoice_date": "2020-01-01"}}
    mock_invoice.status = "APPROVED"
    with patch("app.api.v1.invoices.get_user_filter", return_value=True):
        with pytest.raises(HTTPException) as exc_info:
            await decide_invoice_period(
                invoice_id=inv_id,
                payload=PeriodDecisionRequest(decision="CONTINUE"),
                current_user=mock_user,
                db=mock_db,
            )
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_scenario_13_existing_flow_unchanged_for_current_month():
    # For any month in current FY, period_decision is NOT_REQUIRED
    today_iso = date.today().isoformat()
    cat, msg, month_name = calculate_invoice_accounting_period(today_iso)
    assert cat == "CURRENT_FINANCIAL_YEAR"
    assert msg.startswith("Invoice Month:")

    status_resp = InvoiceStatusResponse(
        invoice_id=uuid.uuid4(),
        status="HITL_REVIEW",
        period_category=cat,
        period_decision="NOT_REQUIRED",
        period_message=msg,
        updated_at=datetime.utcnow(),
    )
    assert status_resp.period_decision == "NOT_REQUIRED"
    assert status_resp.period_category == "CURRENT_FINANCIAL_YEAR"


@pytest.mark.asyncio
async def test_scenario_14_hitl_date_correction_updates_period():
    inv_id = uuid.uuid4()
    mock_invoice = MagicMock(spec=Invoice)
    mock_invoice.id = inv_id
    mock_invoice.status = "HITL_REVIEW"
    mock_invoice.period_category = "PREVIOUS_FINANCIAL_YEAR"
    mock_invoice.period_decision = "PENDING"
    mock_invoice.raw_vlm_output = {"data": {"invoice_date": "2020-01-01"}}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    mock_user = MagicMock()
    mock_user.id = "reviewer-1"
    mock_user.tenant_id = "tenant-1"

    # Reviewer corrects invoice_date to current month
    today_iso = date.today().isoformat()
    payload = ExtractionApproveRequest(
        corrected_data={"data": {"invoice_date": today_iso, "total_amount": 100.0}}
    )

    with patch("app.api.v1.hitl.process_accounting_downstream_background"):
        await approve_extraction_hitl(
            invoice_id=inv_id,
            payload=payload,
            db=mock_db,
            user=mock_user,
        )

    assert mock_invoice.period_category == "CURRENT_FINANCIAL_YEAR"
    assert mock_invoice.period_decision == "NOT_REQUIRED"
    assert mock_invoice.status == "ACCOUNTING_PROCESSING"


@pytest.mark.asyncio
async def test_scenario_15_cancelled_invoice_cannot_be_approved_downstream():
    inv_id = uuid.uuid4()
    mock_invoice = MagicMock(spec=Invoice)
    mock_invoice.id = inv_id
    mock_invoice.status = "CANCELLED"
    mock_invoice.period_category = "PREVIOUS_FINANCIAL_YEAR"
    mock_invoice.period_decision = "CANCELLED"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    mock_user = MagicMock()
    mock_user.id = "reviewer-1"
    mock_user.tenant_id = "tenant-1"

    payload = ExtractionApproveRequest(
        corrected_data={"data": {"invoice_date": "2020-01-01"}}
    )

    with pytest.raises(HTTPException) as exc_info:
        await approve_extraction_hitl(
            invoice_id=inv_id,
            payload=payload,
            db=mock_db,
            user=mock_user,
        )

    assert exc_info.value.status_code in (400, 409)
