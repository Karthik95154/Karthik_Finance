import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.db.database import AsyncSessionLocal
from app.services import invoice_processing
from app.db.models import Invoice

@pytest.mark.asyncio
async def test_accounting_only_releases_db_session_during_inference():
    """
    Verifies that during long-running AI inference (COA and TDS calls),
    the initial DB session has exited and closed before AI calls begin,
    and a new session is only acquired afterwards for persisting results.
    """
    invoice_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=invoice_id,
        tenant_id="test-tenant",
        status="HITL_REVIEW",
        raw_vlm_output={
            "data": {
                "invoice_number": "INV-TEST-001",
                "subtotal": 1000.0,
                "total_amount": 1180.0,
                "tax_total": 180.0,
                "vendor_gstin": "36AABCU9603R1ZM",
                "customer_gstin": "36AAACH7409R1ZZ",
                "place_of_supply": "36-Telangana",
            }
        },
        current_vlm_output=None,
    )

    session_active_during_ai = []
    active_sessions = 0

    class MockAsyncSessionContext:
        def __init__(self):
            self.session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_invoice
            self.session.execute.return_value = mock_result

        async def __aenter__(self):
            nonlocal active_sessions
            active_sessions += 1
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            nonlocal active_sessions
            active_sessions -= 1

    session_call_count = 0
    def session_factory():
        nonlocal session_call_count
        session_call_count += 1
        return MockAsyncSessionContext()

    async def mock_categorize_accounting(*args, **kwargs):
        # AI call should see 0 active DB sessions!
        session_active_during_ai.append(active_sessions)
        await asyncio.sleep(0.01)
        return {
            "accounting": [
                {"account_id": "acc-1", "account_name": "Consulting", "confidence_score": 0.95}
            ]
        }

    async def mock_assess_tds(*args, **kwargs):
        session_active_during_ai.append(active_sessions)
        await asyncio.sleep(0.01)
        return {
            "tds_assessment": {
                "applicable": False,
                "section": "194C",
                "reason": "Threshold not met",
            }
        }

    with patch.object(invoice_processing, "AsyncSessionLocal", side_effect=session_factory), \
         patch("app.services.invoice_processing.accounting_service.categorize_accounting", side_effect=mock_categorize_accounting), \
         patch("app.services.invoice_processing.tds_service.assess_tds", side_effect=mock_assess_tds), \
         patch("app.services.invoice_processing.master_data_service.get_cached_chart_of_accounts", new_callable=AsyncMock) as mock_coa, \
         patch("app.services.invoice_processing.master_data_service.get_cached_taxes", new_callable=AsyncMock) as mock_tax, \
         patch("app.services.invoice_processing.sync_relational_journal", new_callable=AsyncMock):

        mock_coa.return_value = []
        mock_tax.return_value = []

        await invoice_processing.process_accounting_only_background(invoice_id)

    # 1. Verify that exactly 2 distinct short-lived sessions were opened:
    # Session 1: Read state & cached master data
    # Session 2: Persist results after inference
    assert session_call_count == 2
    # 2. Verify that while AI inference was executing, active DB sessions was strictly 0!
    assert len(session_active_during_ai) > 0
    assert all(count == 0 for count in session_active_during_ai)
    # 3. Verify that all sessions are cleanly closed when done
    assert active_sessions == 0


@pytest.mark.asyncio
async def test_downstream_accounting_releases_db_session_during_inference():
    """
    Verifies that downstream accounting processing for approved HITL invoices
    does NOT hold a DB session during AI inference.
    """
    invoice_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=invoice_id,
        tenant_id="test-tenant",
        status="ACCOUNTING_PROCESSING",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-TEST-002",
                "subtotal": 5000.0,
                "total_amount": 5900.0,
                "tax_total": 900.0,
                "vendor_gstin": "36AABCU9603R1ZM",
                "customer_gstin": "36AAACH7409R1ZZ",
                "place_of_supply": "36-Telangana",
            }
        },
    )

    session_active_during_ai = []
    active_sessions = 0

    class MockAsyncSessionContext:
        def __init__(self):
            self.session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_invoice
            self.session.execute.return_value = mock_result

        async def __aenter__(self):
            nonlocal active_sessions
            active_sessions += 1
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            nonlocal active_sessions
            active_sessions -= 1

    session_call_count = 0
    def session_factory():
        nonlocal session_call_count
        session_call_count += 1
        return MockAsyncSessionContext()

    async def mock_categorize_accounting(*args, **kwargs):
        session_active_during_ai.append(active_sessions)
        await asyncio.sleep(0.01)
        return {
            "accounting": [
                {"account_id": "acc-2", "account_name": "Legal Fees", "confidence_score": 0.9}
            ]
        }

    async def mock_assess_tds(*args, **kwargs):
        session_active_during_ai.append(active_sessions)
        await asyncio.sleep(0.01)
        return {
            "tds_assessment": {
                "applicable": True,
                "section": "194J",
                "rate": 10.0,
                "reason": "Professional fees",
            }
        }

    with patch.object(invoice_processing, "AsyncSessionLocal", side_effect=session_factory), \
         patch("app.services.invoice_processing.accounting_service.categorize_accounting", side_effect=mock_categorize_accounting), \
         patch("app.services.invoice_processing.tds_service.assess_tds", side_effect=mock_assess_tds), \
         patch("app.services.invoice_processing.master_data_service.get_cached_chart_of_accounts", new_callable=AsyncMock) as mock_coa, \
         patch("app.services.invoice_processing.master_data_service.get_cached_taxes", new_callable=AsyncMock) as mock_tax, \
         patch("app.services.invoice_processing.sync_relational_journal", new_callable=AsyncMock):

        mock_coa.return_value = []
        mock_tax.return_value = []

        await invoice_processing.process_accounting_downstream_background(invoice_id)

    # Verify session lifecycle
    assert session_call_count == 2
    assert len(session_active_during_ai) > 0
    assert all(count == 0 for count in session_active_during_ai)
    assert active_sessions == 0
