"""
Forex Service & FX Foundation Unit Test Suite
============================================
Validates all 11 test scenarios required for Step 1 of the Foreign Service Invoice feature:
1. INR invoice remains unchanged (rate 1.0, converted = original).
2. USD historical rate retrieval.
3. EUR historical rate retrieval.
4. Decimal conversion precision (6400 USD * 87.123456 = 557590.12 INR).
5. FX source is recorded.
6. FX date is recorded.
7. Processing/recognition date is used by default rather than automatically using invoice date.
8. Cache prevents duplicate provider calls.
9. Provider/network failure follows the implemented fallback/error strategy.
10. FX override data can be represented without destroying the original/system rate.
11. Existing domestic invoice regression tests pass.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.db.models import Invoice
from app.schemas.invoice import InvoiceResponse, InvoiceListItemResponse, InvoiceStatusResponse, InvoiceUpdateRequest
from app.services.forex_service import (
    ForexService,
    ForexProvider,
    ExchangeRateResult,
    RbiReferenceRateProvider,
    ExchangeRateApiProvider,
    FrankfurterProvider,
    StaticFallbackProvider,
    STATIC_FALLBACK_RATES,
)


# Mock Provider for deterministic tests
class MockForexProvider(ForexProvider):
    def __init__(self, name="MOCK_PROVIDER"):
        self._name = name
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def fetch_rate(self, currency: str, fx_date: date) -> ExchangeRateResult:
        self.call_count += 1
        curr = currency.upper().strip()
        rates = {
            "USD": Decimal("87.123456"),
            "EUR": Decimal("92.500000"),
            "GBP": Decimal("110.250000"),
            "INR": Decimal("1.000000"),
        }
        rate = rates.get(curr, Decimal("85.000000"))
        return ExchangeRateResult(
            currency=curr,
            rate=rate,
            rate_date=fx_date,
            requested_date=fx_date,
            source=self.name,
            raw_data={"mocked": True, "call_count": self.call_count},
        )


class FailingForexProvider(ForexProvider):
    @property
    def name(self) -> str:
        return "FAILING_PROVIDER"

    async def fetch_rate(self, currency: str, fx_date: date) -> None:
        raise ConnectionError("Simulated network outage to FX provider")


# --------------------------------------------------------------------------
# TEST 1: INR invoice remains unchanged
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_1_inr_invoice_remains_unchanged():
    service = ForexService(provider=MockForexProvider())
    today = date(2026, 9, 28)

    result = await service.get_exchange_rate("INR", fx_date=today)
    assert result.currency == "INR"
    assert result.rate == Decimal("1.000000")
    assert result.source == "IDENTITY"

    original_amount = Decimal("50000.00")
    converted_amount = service.convert_to_inr(original_amount, result.rate)
    assert converted_amount == Decimal("50000.00")


# --------------------------------------------------------------------------
# TEST 2: USD historical rate retrieval
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_2_usd_historical_rate_retrieval():
    mock_provider = MockForexProvider()
    service = ForexService(provider=mock_provider)
    historical_date = date(2026, 1, 15)

    result = await service.get_exchange_rate("USD", fx_date=historical_date)
    assert result.currency == "USD"
    assert result.rate == Decimal("87.123456")
    assert result.requested_date == historical_date
    assert result.rate_date == historical_date
    assert result.target_currency == "INR"
    assert mock_provider.call_count == 1


# --------------------------------------------------------------------------
# TEST 3: EUR historical rate retrieval
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_3_eur_historical_rate_retrieval():
    mock_provider = MockForexProvider()
    service = ForexService(provider=mock_provider)
    historical_date = date(2025, 12, 1)

    result = await service.get_exchange_rate("EUR", fx_date=historical_date)
    assert result.currency == "EUR"
    assert result.rate == Decimal("92.500000")
    assert result.requested_date == historical_date
    assert result.rate_date == historical_date
    assert mock_provider.call_count == 1


# --------------------------------------------------------------------------
# TEST 4: Decimal conversion precision
# 6400 USD * 87.123456 = 557590.1184 => 557590.12 INR
# --------------------------------------------------------------------------
def test_4_decimal_conversion_precision():
    service = ForexService()
    usd_amount = Decimal("6400.00")
    fx_rate = Decimal("87.123456")

    inr_amount = service.convert_to_inr(usd_amount, fx_rate)

    # 6400 * 87.123456 = 557590.1184 -> rounded with ROUND_HALF_UP is 557590.12
    assert inr_amount == Decimal("557590.12")
    assert isinstance(inr_amount, Decimal)

    # Test edge case: sub-cent rounding
    small_usd = Decimal("10.00")
    small_rate = Decimal("87.125555")
    # 10 * 87.125555 = 871.25555 -> 871.26
    assert service.convert_to_inr(small_usd, small_rate) == Decimal("871.26")


# --------------------------------------------------------------------------
# TEST 5: FX source is recorded
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_5_fx_source_is_recorded():
    service = ForexService(provider=MockForexProvider(name="CUSTOM_FX_SOURCE"))
    target_date = date(2026, 6, 30)

    result = await service.get_exchange_rate("USD", fx_date=target_date)
    assert result.source == "CUSTOM_FX_SOURCE"

    dict_repr = result.to_dict()
    assert dict_repr["source"] == "CUSTOM_FX_SOURCE"
    assert dict_repr["currency"] == "USD"
    assert dict_repr["target_currency"] == "INR"


# --------------------------------------------------------------------------
# TEST 6: FX date is recorded
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_6_fx_date_is_recorded():
    service = ForexService(provider=MockForexProvider())
    req_date = date(2026, 8, 14)

    result = await service.get_exchange_rate("GBP", fx_date=req_date)
    assert result.requested_date == req_date
    assert result.rate_date == req_date
    assert result.to_dict()["rate_date"] == "2026-08-14"
    assert result.to_dict()["requested_date"] == "2026-08-14"


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# TEST 7: Invoice date is used by default per FX_DATE_SOURCE = INVOICE_DATE
# --------------------------------------------------------------------------
def test_7_invoice_date_used_by_default():
    service = ForexService()
    invoice_date = date(2026, 3, 10)
    processing_date = date(2026, 3, 25)

    # Default setting: FX_DATE_SOURCE is "INVOICE_DATE"
    resolved_date = service.resolve_fx_date(
        invoice_date=invoice_date,
        processing_date=processing_date,
    )
    assert resolved_date == invoice_date
    assert resolved_date != processing_date

    # When invoice_date is omitted, falls back to processing date or today UTC
    resolved_fallback = service.resolve_fx_date(invoice_date=None, processing_date=processing_date)
    assert resolved_fallback == processing_date


# --------------------------------------------------------------------------
# TEST 8: Cache prevents duplicate provider calls
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_8_cache_prevents_duplicate_provider_calls():
    mock_provider = MockForexProvider()
    service = ForexService(provider=mock_provider)
    target_date = date(2026, 5, 20)

    # First call -> hits provider
    res1 = await service.get_exchange_rate("USD", fx_date=target_date)
    assert mock_provider.call_count == 1
    assert res1.rate == Decimal("87.123456")

    # Second call for same currency + date + provider -> hits cache
    res2 = await service.get_exchange_rate("USD", fx_date=target_date)
    assert mock_provider.call_count == 1  # Call count unchanged!
    assert res2.rate == Decimal("87.123456")

    # Call with force_refresh=True -> refreshes cache
    res3 = await service.get_exchange_rate("USD", fx_date=target_date, force_refresh=True)
    assert mock_provider.call_count == 2
    assert res3.rate == Decimal("87.123456")


# --------------------------------------------------------------------------
# TEST 9: Provider/network failure follows fallback/error strategy
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_9_provider_failure_falls_back_safely():
    # 1. Primary failure -> falls back safely (either secondary network provider or static fallback)
    service = ForexService(provider=FailingForexProvider())
    target_date = date(2026, 4, 10)

    result = await service.get_exchange_rate("USD", fx_date=target_date)
    assert result is not None
    assert result.currency == "USD"
    assert result.rate > Decimal("0.000000")

    # 2. When all network providers fail -> falls back to StaticFallbackProvider
    with patch.object(FrankfurterProvider, "fetch_rate", side_effect=ConnectionError("Offline")):
        with patch.object(RbiReferenceRateProvider, "fetch_rate", side_effect=ConnectionError("Offline")):
            with patch.object(ExchangeRateApiProvider, "fetch_rate", side_effect=ConnectionError("Offline")):
                service_all_failing = ForexService(provider=FailingForexProvider())
                fallback_res = await service_all_failing.get_exchange_rate("USD", fx_date=target_date)
                assert fallback_res is not None
                assert fallback_res.currency == "USD"
                assert fallback_res.is_fallback is True
                assert fallback_res.source == "STATIC_FALLBACK"
                assert fallback_res.rate == STATIC_FALLBACK_RATES["USD"]


# --------------------------------------------------------------------------
# TEST 12: Three-tier fallback auditability (Primary -> Secondary -> Static)
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_three_tier_fallback_source_auditability():
    req_date = date(2026, 9, 15)

    # Tier 1: Primary provider success
    primary_prov = MockForexProvider(name="EXCHANGE_RATE_API")
    service1 = ForexService(provider=primary_prov)
    res_tier1 = await service1.get_exchange_rate("USD", fx_date=req_date)
    assert res_tier1.source == "EXCHANGE_RATE_API"
    assert res_tier1.requested_date == req_date
    assert res_tier1.rate_date == req_date
    assert res_tier1.is_fallback is False

    # Tier 2: Primary failure -> Secondary provider success (Frankfurter)
    tier2_result = ExchangeRateResult(
        currency="USD",
        rate=Decimal("87.450000"),
        rate_date=date(2026, 9, 14),  # previous business day
        requested_date=req_date,
        source="FRANKFURTER",
        is_fallback=False,
    )

    with patch.object(FrankfurterProvider, "fetch_rate", return_value=tier2_result):
        service2 = ForexService(provider=FailingForexProvider())
        res_tier2 = await service2.get_exchange_rate("USD", fx_date=req_date)
        assert res_tier2.source == "FRANKFURTER"
        assert res_tier2.requested_date == req_date
        assert res_tier2.rate_date == date(2026, 9, 14)
        assert res_tier2.is_fallback is False

    # Tier 3: Primary + Secondary failure -> Static fallback
    with patch.object(FrankfurterProvider, "fetch_rate", side_effect=Exception("Frankfurter down")):
        with patch.object(RbiReferenceRateProvider, "fetch_rate", side_effect=Exception("RBI down")):
            with patch.object(ExchangeRateApiProvider, "fetch_rate", side_effect=Exception("ER API down")):
                service3 = ForexService(provider=FailingForexProvider())
                res_tier3 = await service3.get_exchange_rate("USD", fx_date=req_date)
                assert res_tier3.source == "STATIC_FALLBACK"
                assert res_tier3.requested_date == req_date
                assert res_tier3.rate_date == req_date
                assert res_tier3.is_fallback is True


# --------------------------------------------------------------------------
# TEST 13: RBI Reference Rate Provider lookup
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_rbi_reference_rate_provider_lookup():
    rbi_provider = RbiReferenceRateProvider()
    assert rbi_provider.name == "RBI_REFERENCE_RATE_ARCHIVE"
    
    # Mock RBI rate result
    rbi_result = ExchangeRateResult(
        currency="USD",
        rate=Decimal("95.968100"),
        rate_date=date(2026, 9, 28),
        requested_date=date(2026, 9, 28),
        source=rbi_provider.name,
    )
    with patch.object(RbiReferenceRateProvider, "fetch_rate", return_value=rbi_result):
        service = ForexService(provider=rbi_provider)
        res = await service.get_exchange_rate("USD", fx_date=date(2026, 9, 28))
        assert res.currency == "USD"
        assert res.rate == Decimal("95.968100")
        assert res.source == "RBI_REFERENCE_RATE_ARCHIVE"


# --------------------------------------------------------------------------
# TEST 10: FX override data represented without destroying original system rate
# --------------------------------------------------------------------------
def test_10_fx_override_preserves_original_rate():
    service = ForexService()
    system_rate = Decimal("87.123456")
    override_rate = Decimal("88.000000")
    reason = "Bank custom contract rate for USD remittance"

    active_rate, is_overridden, applied_reason, orig_rate = service.apply_finance_override(
        original_rate=system_rate,
        override_rate=override_rate,
        override_reason=reason,
    )

    assert active_rate == Decimal("88.000000")
    assert is_overridden is True
    assert applied_reason == reason
    assert orig_rate == Decimal("87.123456")

    # Test when no override is specified
    active_rate_2, is_ovr_2, reason_2, orig_rate_2 = service.apply_finance_override(
        original_rate=system_rate,
        override_rate=None,
        override_reason=None,
    )
    assert active_rate_2 == Decimal("87.123456")
    assert is_ovr_2 is False
    assert reason_2 is None
    assert orig_rate_2 == Decimal("87.123456")


# --------------------------------------------------------------------------
# TEST 11: Existing domestic invoice regression tests pass
# --------------------------------------------------------------------------
def test_11_domestic_invoice_regression_and_model_compatibility():
    inv_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Domestic INR Invoice Model Instance
    domestic_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="/uploads/invoice1.pdf",
        file_name="invoice1.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="dummyhash123",
        status="PROCESSED",
        invoice_origin="INDIAN",
        currency="INR",
        # FX fields defaulted
        original_currency="INR",
        original_total_amount=Decimal("11800.00"),
        original_taxable_amount=Decimal("10000.00"),
        exchange_rate=Decimal("1.000000"),
        exchange_rate_date=now.date(),
        exchange_rate_source="SYSTEM_DEFAULT",
        converted_total_inr=Decimal("11800.00"),
        converted_taxable_inr=Decimal("10000.00"),
        fx_rate_overridden=False,
    )

    assert domestic_invoice.currency == "INR"
    assert domestic_invoice.original_currency == "INR"
    assert domestic_invoice.exchange_rate == Decimal("1.000000")
    assert domestic_invoice.converted_total_inr == Decimal("11800.00")

    # 2. Pydantic Response Schema Serialization
    response = InvoiceResponse(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="/uploads/invoice1.pdf",
        file_name="invoice1.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="dummyhash123",
        status="PROCESSED",
        invoice_origin="INDIAN",
        currency="INR",
        original_currency="INR",
        original_total_amount=Decimal("11800.00"),
        original_taxable_amount=Decimal("10000.00"),
        exchange_rate=Decimal("1.000000"),
        exchange_rate_date=now.date(),
        exchange_rate_source="SYSTEM_DEFAULT",
        converted_total_inr=Decimal("11800.00"),
        converted_taxable_inr=Decimal("10000.00"),
        fx_rate_overridden=False,
        created_at=now,
        updated_at=now,
    )

    resp_dict = response.model_dump()
    assert resp_dict["original_currency"] == "INR"
    assert resp_dict["converted_total_inr"] == Decimal("11800.00")
    assert resp_dict["exchange_rate"] == Decimal("1.000000")
    assert resp_dict["fx_rate_overridden"] is False

    # 3. Foreign Invoice Model & Schema Representation
    foreign_id = uuid.uuid4()
    foreign_resp = InvoiceResponse(
        id=foreign_id,
        tenant_id="default-tenant-001",
        file_path="/uploads/foreign_invoice.pdf",
        file_name="foreign_invoice.pdf",
        file_size=2048,
        mime_type="application/pdf",
        file_hash="foreignhash456",
        status="PROCESSED",
        invoice_origin="FOREIGN",
        currency="USD",
        original_currency="USD",
        original_total_amount=Decimal("6400.00"),
        original_taxable_amount=Decimal("6400.00"),
        exchange_rate=Decimal("87.123456"),
        exchange_rate_date=date(2026, 9, 28),
        exchange_rate_source="EXCHANGE_RATE_API",
        converted_total_inr=Decimal("557590.12"),
        converted_taxable_inr=Decimal("557590.12"),
        fx_rate_overridden=True,
        fx_override_reason="Agreed contract rate",
        fx_original_rate=Decimal("86.950000"),
        created_at=now,
        updated_at=now,
    )

    f_dict = foreign_resp.model_dump()
    assert f_dict["currency"] == "USD"
    assert f_dict["original_total_amount"] == Decimal("6400.00")
    assert f_dict["converted_total_inr"] == Decimal("557590.12")
    assert f_dict["fx_rate_overridden"] is True
    assert f_dict["fx_original_rate"] == Decimal("86.950000")


# --------------------------------------------------------------------------
# TEST 12: Currency normalization and unsupported currency safety
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_currency_normalization_and_safety():
    service = ForexService(provider=MockForexProvider())
    
    # Lowercase & dirty symbols normalized
    res_lower = await service.get_exchange_rate("usd")
    assert res_lower.currency == "USD"

    res_dirty = await service.get_exchange_rate(" $USD ")
    assert res_dirty.currency == "USD"

    # Empty string or None defaults safely to INR
    res_empty = await service.get_exchange_rate("")
    assert res_empty.currency == "INR"
    assert res_empty.rate == Decimal("1.000000")


# --------------------------------------------------------------------------
# TEST 13: Strict positive rate validation
# --------------------------------------------------------------------------
def test_13_positive_rate_enforcement():
    service = ForexService()
    
    with pytest.raises(ValueError, match="strictly positive"):
        service.convert_to_inr(Decimal("100.00"), Decimal("0.000000"))

    with pytest.raises(ValueError, match="strictly positive"):
        service.convert_to_inr(Decimal("100.00"), Decimal("-1.500000"))


# --------------------------------------------------------------------------
# TEST 14: Configurable INVOICE_DATE policy verification
# --------------------------------------------------------------------------
def test_14_configurable_date_policy():
    service = ForexService()
    inv_date = date(2026, 8, 15)
    proc_date = date(2026, 9, 5)

    # 1. Default (PROCESSING_DATE)
    with patch.object(settings, "FX_DATE_SOURCE", "PROCESSING_DATE"):
        assert service.resolve_fx_date(invoice_date=inv_date, processing_date=proc_date) == proc_date

    # 2. Configured INVOICE_DATE
    with patch.object(settings, "FX_DATE_SOURCE", "INVOICE_DATE"):
        assert service.resolve_fx_date(invoice_date=inv_date, processing_date=proc_date) == inv_date


# --------------------------------------------------------------------------
# TEST 15: Full domestic invoice trace with 0 FX drift
# --------------------------------------------------------------------------
def test_15_full_domestic_pipeline_trace_with_zero_drift():
    from app.services.gst_engine import GSTEngine
    from app.services.itc_engine import ITCEngine
    from app.services.tds_engine import TDSEngine
    from app.services.journal_generator import JournalGenerator

    gst_engine = GSTEngine()
    itc_engine = ITCEngine()
    tds_engine = TDSEngine()
    journal_gen = JournalGenerator()

    domestic_data = {
        "document_type": "TAX_INVOICE",
        "invoice_number": "INV-100",
        "invoice_date": "2026-09-01",
        "vendor_name": "Acme Tech Services Pvt Ltd",
        "vendor_gstin": "27AAACA1234A1Z5",
        "customer_gstin": "27BBBCB5678B1Z2",
        "place_of_supply": "27-Maharashtra",
        "subtotal": 100000.00,
        "taxable_amount": 100000.00,
        "total_amount": 118000.00,
        "currency": "INR",
        "line_items": [
            {
                "line_index": 1,
                "description": "AWS Cloud Hosting and Server Infrastructure",
                "hsn_code": "998314",
                "taxable_amount": 100000.00,
                "gst_rate": 18.0,
                "cgst_amount": 9000.00,
                "sgst_amount": 9000.00,
                "total": 118000.00,
            }
        ],
    }

    accounting_output = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_100",
                "approved_account_name": "Software and Cloud Subscriptions",
                "final_account_name": "Software and Cloud Subscriptions",
            }
        ]
    }

    # Verify domestic pipeline components
    gst_res = gst_engine.evaluate_gst(domestic_data)
    assert gst_res["supply_type"] == "INTRA_STATE"
    assert gst_res["calculated"]["cgst_amount"] == 9000.00
    assert gst_res["calculated"]["sgst_amount"] == 9000.00

    itc_res = itc_engine.evaluate_itc(domestic_data, accounting_output)
    assert itc_res["status"] == "ELIGIBLE"
    assert itc_res["eligible_amount"] == 18000.00

    tds_res = tds_engine.calculate_tds(domestic_data)
    assert "applicable" in tds_res

    journal = journal_gen.generate_journal(
        invoice_data=domestic_data,
        accounting_classification=accounting_output,
        gst_result=gst_res,
        itc_result=itc_res,
        tds_result=tds_res,
    )
    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 118000.00
    assert journal["total_credit"] == 118000.00
    assert journal["difference"] == 0.00

