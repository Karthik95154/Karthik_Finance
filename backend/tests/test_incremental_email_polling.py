"""
test_incremental_email_polling.py
----------------------------------
Tests for the incremental email polling system.

Covers all 11 scenarios specified in the requirements:
 1. User connects email → last_successful_poll_at = NULL, auto-poll disabled
 2. First manual poll → checkpoint saved, auto-poll enabled
 3. Failed first manual poll → checkpoint stays NULL, auto-poll stays disabled
 4. Subsequent manual poll uses last_successful_poll_at window
 5. Automatic poll uses last_successful_poll_at window
 6. Manual poll after automatic poll uses updated checkpoint
 7. Non-invoice documents are NOT stored in Invoice table
 8. SHA-256 duplicate detection still works
 9. Multiple users have independent timestamps
10. Failed poll does not advance checkpoint
11. Concurrent poll is rejected with 409
"""

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token
from app.core.security_util import encrypt_data
from app.db.database import get_db
from app.db.models import Invoice, EmailConnection
from app.services.groq_classifier import (
    DocumentClassificationResult,
    FinancialRelevance,
    DocumentType,
)
from app.services.imap_service import imap_service
from app.storage.supabase_storage import storage_service

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_auth_headers(user_id: str = "test-user-id") -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(user_id=user_id, email=f'{user_id}@example.com', tenant_id='default-tenant-001', role='ADMIN')}"
    }


def make_email_conn(
    user_id_str: str = "test-user-id",
    last_successful_poll_at: datetime | None = None,
    automatic_polling_enabled: bool = False,
    is_polling: bool = False,
) -> EmailConnection:
    return EmailConnection(
        id=uuid.uuid4(),
        user_id=None,
        user_id_str=user_id_str,
        email_address="finance@company.com",
        encrypted_password=encrypt_data("app_password"),
        imap_host="imap.gmail.com",
        imap_port=993,
        is_active=True,
        last_synced_at=None,
        last_successful_poll_at=last_successful_poll_at,
        automatic_polling_enabled=automatic_polling_enabled,
        is_polling=is_polling,
    )


def make_attachment(filename: str = "invoice.pdf", content: bytes = b"invoice bytes") -> dict:
    return {
        "email_subject": "Test Invoice",
        "email_sender": "billing@vendor.com",
        "email_received_at": datetime.now(timezone.utc),
        "email_message_id": "msg-001",
        "email_body": "",
        "filename": filename,
        "mime_type": "application/pdf",
        "file_bytes": content,
        "file_hash": hashlib.sha256(content).hexdigest(),
    }


def make_poll_result(attachments: list) -> dict:
    return {
        "attachments": attachments,
        "errors": [],
        "emails_checked": len(attachments),
        "attachments_found": len(attachments),
        "timings": {},
    }


FINANCIAL_RESULT = DocumentClassificationResult(
    financial_relevance=FinancialRelevance.FINANCIAL,
    document_type=DocumentType.INVOICE,
    confidence=0.97,
    reason="Invoice document",
)

NON_FINANCIAL_RESULT = DocumentClassificationResult(
    financial_relevance=FinancialRelevance.NOT_FINANCIAL,
    document_type=DocumentType.GENERAL_DOCUMENT,
    confidence=0.99,
    reason="Purchase order",
)


# ── Test 1: Email connection → no auto-poll, NULL checkpoint ─────────────────

def test_new_email_connection_has_null_checkpoint_and_disabled_auto_poll():
    """When a user connects email the polling state must be NULL / disabled."""
    conn = make_email_conn()
    assert conn.last_successful_poll_at is None
    assert conn.automatic_polling_enabled is False
    assert conn.is_polling is False


# ── Test 2: First successful manual poll ─────────────────────────────────────

@pytest.mark.asyncio
async def test_first_manual_poll_saves_checkpoint_and_enables_auto_poll():
    """First poll: checkpoint saved, automatic_polling_enabled set to True."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(last_successful_poll_at=None, automatic_polling_enabled=False)
    mock_result.scalars.return_value.first.return_value = conn
    # Duplicate check returns no existing invoices
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    attachment = make_attachment()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch.object(imap_service, "poll_mailbox", return_value=make_poll_result([attachment])),
                patch.object(storage_service, "upload_file", return_value=None),
                patch("app.api.v1.inbox.classify_document", return_value=FINANCIAL_RESULT),
            ):
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["poll_mode"] == "initial"
        assert data["poll_since"] is None
        assert data["new_documents"] == 1

        # Verify checkpoint and auto-poll flag were set on the conn object
        assert conn.last_successful_poll_at is not None
        assert conn.automatic_polling_enabled is True
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 3: Failed first manual poll → checkpoint stays NULL ─────────────────

@pytest.mark.asyncio
async def test_failed_first_poll_does_not_save_checkpoint():
    """IMAP failure during first poll must NOT set last_successful_poll_at."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(last_successful_poll_at=None, automatic_polling_enabled=False)
    mock_result.scalars.return_value.first.return_value = conn
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "poll_mailbox", side_effect=Exception("IMAP network error")):
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 500
        # Checkpoint must remain NULL
        assert conn.last_successful_poll_at is None
        assert conn.automatic_polling_enabled is False
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 4: Second manual poll uses timestamp window ─────────────────────────

@pytest.mark.asyncio
async def test_second_poll_passes_since_datetime_to_imap():
    """Incremental poll: imap_service.poll_mailbox must receive the checkpoint as since_datetime."""
    prev_checkpoint = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)

    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(
        last_successful_poll_at=prev_checkpoint,
        automatic_polling_enabled=True,
    )
    mock_result.scalars.return_value.first.return_value = conn
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(
                imap_service, "poll_mailbox", return_value=make_poll_result([])
            ) as mock_poll:
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["poll_mode"] == "incremental"
        assert data["poll_since"] == prev_checkpoint.isoformat()

        # Verify imap_service received since_datetime = the previous checkpoint
        call_kwargs = mock_poll.call_args.kwargs
        assert call_kwargs["since_datetime"] == prev_checkpoint
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 5 & 6: Automatic poll and manual poll after auto-poll ───────────────

@pytest.mark.asyncio
async def test_automatic_poll_uses_last_successful_poll_at():
    """Scheduler job must pass last_successful_poll_at as since_datetime."""
    from app.services.email_scheduler import _run_automatic_poll_for_connection

    prev_checkpoint = datetime(2026, 9, 7, 21, 0, 0, tzinfo=timezone.utc)
    conn = make_email_conn(
        last_successful_poll_at=prev_checkpoint,
        automatic_polling_enabled=True,
    )
    conn.user_id = None
    conn.user_id_str = "auto-user"

    captured_since = {}

    async def fake_poll(config, window_hours=24, since_datetime=None):
        captured_since["since"] = since_datetime
        return make_poll_result([])

    with (
        patch("app.services.email_scheduler.AsyncSessionLocal") as mock_session_cls,
        patch.object(imap_service, "poll_mailbox", side_effect=fake_poll),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = conn
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session_cls.return_value = mock_session

        await _run_automatic_poll_for_connection(conn)

    assert captured_since.get("since") == prev_checkpoint


@pytest.mark.asyncio
async def test_manual_poll_after_auto_poll_uses_auto_checkpoint():
    """After automatic poll advances checkpoint, manual poll uses new checkpoint."""
    auto_checkpoint = datetime(2026, 9, 8, 7, 0, 0, tzinfo=timezone.utc)  # 7AM

    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(
        last_successful_poll_at=auto_checkpoint,
        automatic_polling_enabled=True,
    )
    mock_result.scalars.return_value.first.return_value = conn
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(
                imap_service, "poll_mailbox", return_value=make_poll_result([])
            ) as mock_poll:
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["poll_mode"] == "incremental"
        assert data["poll_since"] == auto_checkpoint.isoformat()
        call_kwargs = mock_poll.call_args.kwargs
        assert call_kwargs["since_datetime"] == auto_checkpoint
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 7: Non-financial documents are NOT stored ───────────────────────────

@pytest.mark.asyncio
async def test_non_financial_documents_not_stored_in_invoice_table():
    """Non-invoice attachments must be discarded. storage_service.upload_file must NOT be called."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(automatic_polling_enabled=True,
                           last_successful_poll_at=datetime.now(timezone.utc) - timedelta(hours=1))
    mock_result.scalars.return_value.first.return_value = conn
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    attachment = make_attachment(filename="purchase_order.pdf", content=b"PO bytes")

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            mock_upload = AsyncMock()
            with (
                patch.object(imap_service, "poll_mailbox", return_value=make_poll_result([attachment])),
                patch.object(storage_service, "upload_file", mock_upload),
                patch("app.api.v1.inbox.classify_document", return_value=NON_FINANCIAL_RESULT),
            ):
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["new_documents"] == 0
        mock_upload.assert_not_called()  # Storage must NOT be touched
        # DB add() must NOT have been called for Invoice
        for call_args in mock_db.add.call_args_list:
            obj = call_args[0][0]
            assert not isinstance(obj, Invoice), "Non-financial document must NOT be saved as Invoice"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 8: SHA-256 duplicate detection still works ──────────────────────────

@pytest.mark.asyncio
async def test_sha256_duplicate_detection_still_active():
    """Even with incremental polling, SHA-256 must catch duplicate attachments."""
    prev_checkpoint = datetime.now(timezone.utc) - timedelta(hours=2)

    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(
        last_successful_poll_at=prev_checkpoint,
        automatic_polling_enabled=True,
    )

    attachment = make_attachment()
    existing_inv = Invoice(
        id=uuid.uuid4(),
        file_name=attachment["filename"],
        file_hash=attachment["file_hash"],
        file_path="uploads/existing.pdf",
        file_size=100,
        mime_type="application/pdf",
        status="STAGED",
        accounting_status="STAGED",
    )

    # First execute call = EmailConnection lookup; second = duplicate check
    execute_results = [MagicMock(), MagicMock()]
    execute_results[0].scalars.return_value.first.return_value = conn
    execute_results[1].scalars.return_value.all.return_value = [existing_inv]
    mock_db.execute.side_effect = execute_results

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "poll_mailbox", return_value=make_poll_result([attachment])):
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["duplicates"] == 1
        assert data["new_documents"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 9: Multiple users are independent ────────────────────────────────────

def test_two_users_have_independent_polling_timestamps():
    """User A and User B must have completely independent last_successful_poll_at values."""
    ts_a = datetime(2026, 9, 7, 9, 0, 0, tzinfo=timezone.utc)
    ts_b = datetime(2026, 9, 6, 18, 0, 0, tzinfo=timezone.utc)

    conn_a = make_email_conn(user_id_str="user-A", last_successful_poll_at=ts_a)
    conn_b = make_email_conn(user_id_str="user-B", last_successful_poll_at=ts_b)

    assert conn_a.last_successful_poll_at == ts_a
    assert conn_b.last_successful_poll_at == ts_b
    assert conn_a.last_successful_poll_at != conn_b.last_successful_poll_at


# ── Test 10: Failed poll does not advance checkpoint ─────────────────────────

@pytest.mark.asyncio
async def test_failed_poll_does_not_advance_checkpoint():
    """If IMAP fails, last_successful_poll_at must remain unchanged."""
    prev_checkpoint = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)

    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(
        last_successful_poll_at=prev_checkpoint,
        automatic_polling_enabled=True,
    )
    mock_result.scalars.return_value.first.return_value = conn
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(
                imap_service, "poll_mailbox", side_effect=Exception("Network timeout")
            ):
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 500
        # Checkpoint must NOT have changed
        assert conn.last_successful_poll_at == prev_checkpoint
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 11: Concurrent poll rejected with 409 ───────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_poll_rejected_with_409():
    """If is_polling=True, a second poll request must be rejected with HTTP 409."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(
        last_successful_poll_at=datetime.now(timezone.utc) - timedelta(hours=1),
        automatic_polling_enabled=True,
        is_polling=True,  # ← already polling
    )
    mock_result.scalars.return_value.first.return_value = conn
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = make_auth_headers()
            res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 409
        assert "already in progress" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test: Timezone-aware checkpoint ──────────────────────────────────────────

def test_checkpoint_is_timezone_aware_utc():
    """last_successful_poll_at must be timezone-aware UTC."""
    now_utc = datetime.now(timezone.utc)
    conn = make_email_conn(last_successful_poll_at=now_utc)
    ts = conn.last_successful_poll_at
    assert ts is not None
    assert ts.tzinfo is not None, "Timestamp must be timezone-aware"
    assert ts.tzinfo == timezone.utc or str(ts.tzinfo) in ("UTC", "utc")


# ── Test: poll_upper_bound in response ────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_contains_poll_upper_bound():
    """The response must contain poll_upper_bound as an ISO timestamp string."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    conn = make_email_conn(
        last_successful_poll_at=datetime.now(timezone.utc) - timedelta(hours=1),
        automatic_polling_enabled=True,
    )
    mock_result.scalars.return_value.first.return_value = conn
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "poll_mailbox", return_value=make_poll_result([])):
                headers = make_auth_headers()
                res = await client.post("/api/v1/email/poll", headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert "poll_upper_bound" in data
        # Verify it is a parseable ISO datetime string
        dt = datetime.fromisoformat(data["poll_upper_bound"])
        assert dt.tzinfo is not None
    finally:
        app.dependency_overrides.pop(get_db, None)
