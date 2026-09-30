"""
Forex & FX Exchange Rate Service
================================
Provides financial-grade foreign exchange rate retrieval, historical date snapping,
in-memory TTL caching, fallback resiliency, and Decimal conversion math for Sakshi Finance.

STRICT CONSTRAINTS:
- Use Decimal exclusively for all financial rates and currency calculations. Never use float.
- Default FX date is INVOICE DATE for foreign service invoices (configurable via FX_DATE_SOURCE).
- Extensible provider abstraction: ExchangeRate-API, Frankfurter, and Static Fallback.
- Audit trail support preserving system rates, overrides, and reasons.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
import re
import threading
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Currency precision constants
MONEY_QUANTIZE = Decimal("0.01")
RATE_QUANTIZE = Decimal("0.000001")

# Static fallback rates (INR per 1 foreign unit) for disaster recovery
STATIC_FALLBACK_RATES: Dict[str, Decimal] = {
    "USD": Decimal("87.123456"),
    "EUR": Decimal("92.500000"),
    "GBP": Decimal("110.250000"),
    "SGD": Decimal("65.400000"),
    "AED": Decimal("23.720000"),
    "JPY": Decimal("0.580000"),
    "CAD": Decimal("64.200000"),
    "AUD": Decimal("56.800000"),
    "INR": Decimal("1.000000"),
}


class ExchangeRateResult:
    """Encapsulates the result of an exchange rate lookup with full audit metadata."""

    def __init__(
        self,
        currency: str,
        rate: Decimal,
        rate_date: date,
        requested_date: date,
        source: str,
        is_fallback: bool = False,
        raw_data: Optional[Dict[str, Any]] = None,
    ):
        self.currency = currency.upper().strip()
        self.target_currency = "INR"
        self.rate = rate.quantize(RATE_QUANTIZE, rounding=ROUND_HALF_UP)
        self.rate_date = rate_date
        self.requested_date = requested_date
        self.source = source
        self.is_fallback = is_fallback
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency": self.currency,
            "target_currency": self.target_currency,
            "rate": str(self.rate),
            "rate_date": self.rate_date.isoformat(),
            "requested_date": self.requested_date.isoformat(),
            "source": self.source,
            "is_fallback": self.is_fallback,
            "raw_data": self.raw_data,
        }

    def __repr__(self) -> str:
        return f"<ExchangeRateResult {self.currency}/INR = {self.rate} ({self.source}, {self.rate_date})>"


class ForexProvider(ABC):
    """Abstract interface for foreign exchange rate providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def fetch_rate(self, currency: str, fx_date: date) -> Optional[ExchangeRateResult]:
        """Fetch exchange rate for currency to INR on fx_date."""
        pass


class RbiReferenceRateProvider(ForexProvider):
    """
    Official Reserve Bank of India (RBI / FBIL) Reference Rate Archive provider.
    Source: https://www.rbi.org.in/scripts/referenceratearchive.aspx
    Publishes official daily reference rates for USD, GBP, EUR, JPY, AED, IDR against INR.
    Automatically handles weekends and bank holidays by retrieving the closest preceding official business day.
    """

    RBI_ARCHIVE_URL = "https://www.rbi.org.in/scripts/referenceratearchive.aspx"
    SUPPORTED_CURRENCIES = {
        "USD": (1, Decimal("1")),
        "GBP": (2, Decimal("1")),
        "EUR": (3, Decimal("1")),
        "JPY": (4, Decimal("100")),
        "AED": (5, Decimal("1")),
        "IDR": (6, Decimal("10000")),
    }

    @property
    def name(self) -> str:
        return "RBI_REFERENCE_RATE_ARCHIVE"

    async def fetch_rate(self, currency: str, fx_date: date) -> Optional[ExchangeRateResult]:
        curr = currency.upper().strip()
        if curr == "INR":
            return ExchangeRateResult(
                currency="INR",
                rate=Decimal("1.000000"),
                rate_date=fx_date,
                requested_date=fx_date,
                source=self.name,
            )

        if curr not in self.SUPPORTED_CURRENCIES:
            logger.debug(f"Currency {curr} not in RBI Reference Rate Archive supported set: {list(self.SUPPORTED_CURRENCIES.keys())}")
            return None

        col_idx, divisor = self.SUPPORTED_CURRENCIES[curr]
        timeout = getattr(settings, "FX_REQUEST_TIMEOUT", 15.0)
        from_date = fx_date - timedelta(days=7)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True, verify=False) as client:
                r_get = await client.get(self.RBI_ARCHIVE_URL)
                if r_get.status_code != 200:
                    logger.warning(f"RBI Archive GET returned status {r_get.status_code}")
                    return None

                vs = re.search(r'id=\"__VIEWSTATE\"\s+value=\"([^\"]*)\"', r_get.text)
                vsg = re.search(r'id=\"__VIEWSTATEGENERATOR\"\s+value=\"([^\"]*)\"', r_get.text)
                ev = re.search(r'id=\"__EVENTVALIDATION\"\s+value=\"([^\"]*)\"', r_get.text)

                form_data = {
                    "__VIEWSTATE": vs.group(1) if vs else "",
                    "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
                    "__EVENTVALIDATION": ev.group(1) if ev else "",
                    "txtFromDate": from_date.strftime("%d/%m/%Y"),
                    "txtToDate": fx_date.strftime("%d/%m/%Y"),
                    "chkAll": "on",
                    "btnSubmit": " GO ",
                }

                r_post = await client.post(self.RBI_ARCHIVE_URL, data=form_data)
                if r_post.status_code != 200:
                    logger.warning(f"RBI Archive POST returned status {r_post.status_code}")
                    return None

                rows = re.findall(r"<tr[^>]*>(.*?)</tr>", r_post.text, re.DOTALL | re.IGNORECASE)
                rates_by_date = []
                for r in rows:
                    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.DOTALL | re.IGNORECASE)
                    cleaned = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                    if len(cleaned) >= 7 and re.match(r"^\d{2}/\d{2}/\d{4}$", cleaned[0]):
                        try:
                            d = datetime.strptime(cleaned[0], "%d/%m/%Y").date()
                            raw_val = cleaned[col_idx].replace(",", "")
                            if raw_val:
                                val = Decimal(raw_val) / divisor
                                rates_by_date.append((d, val, cleaned[0]))
                        except Exception:
                            continue

                # Sort by date descending
                rates_by_date.sort(key=lambda x: x[0], reverse=True)
                for d, rate_dec, d_str in rates_by_date:
                    if d <= fx_date:
                        return ExchangeRateResult(
                            currency=curr,
                            rate=rate_dec,
                            rate_date=d,
                            requested_date=fx_date,
                            source=self.name,
                            raw_data={
                                "portal": "Reserve Bank of India Reference Rate Archive",
                                "url": self.RBI_ARCHIVE_URL,
                                "rbi_published_date": d_str,
                            },
                        )
        except Exception as exc:
            logger.warning(f"RBI Reference Rate Archive lookup failed for {curr} on {fx_date}: {exc}")

        return None


class ExchangeRateApiProvider(ForexProvider):
    """
    ExchangeRate-API provider supporting historical and pair rate lookups.
    Docs: https://www.exchangerate-api.com/docs/historical-data-requests
    """

    @property
    def name(self) -> str:
        return "EXCHANGE_RATE_API"

    async def fetch_rate(self, currency: str, fx_date: date) -> Optional[ExchangeRateResult]:
        curr = currency.upper().strip()
        if curr == "INR":
            return ExchangeRateResult(
                currency="INR",
                rate=Decimal("1.000000"),
                rate_date=fx_date,
                requested_date=fx_date,
                source=self.name,
            )

        api_key = (
            getattr(settings, "EXCHANGE_RATE_API_KEY", None)
            or getattr(settings, "FX_EXCHANGE_RATE_API_KEY", "")
        )

        timeout = getattr(settings, "FX_REQUEST_TIMEOUT", 10.0)

        # Attempt historical pair endpoint if api_key is available
        if api_key:
            # Historical URL: https://v6.exchangerate-api.com/v6/{api_key}/history/{currency}/{year}/{month}/{day}
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/history/{curr}/{fx_date.year}/{fx_date.month}/{fx_date.day}"
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("result") == "success":
                            conversion_rates = data.get("conversion_rates", {})
                            if "INR" in conversion_rates:
                                rate_dec = Decimal(str(conversion_rates["INR"]))
                                return ExchangeRateResult(
                                    currency=curr,
                                    rate=rate_dec,
                                    rate_date=fx_date,
                                    requested_date=fx_date,
                                    source=self.name,
                                    raw_data={"result": data.get("result"), "base_code": curr},
                                )
            except Exception as e:
                logger.warning(f"ExchangeRate-API historical call failed for {curr} on {fx_date}: {e}")

            # Fallback to standard pair rate endpoint
            try:
                pair_url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{curr}/INR"
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(pair_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("result") == "success" and "conversion_rate" in data:
                            rate_dec = Decimal(str(data["conversion_rate"]))
                            return ExchangeRateResult(
                                currency=curr,
                                rate=rate_dec,
                                rate_date=fx_date,
                                requested_date=fx_date,
                                source=f"{self.name}_PAIR",
                                raw_data={"result": data.get("result"), "base_code": curr},
                            )
            except Exception as e:
                logger.warning(f"ExchangeRate-API pair call failed for {curr}: {e}")

        # Open Access (V4 endpoint) fallback if no key or key failed
        try:
            open_url = f"https://open.er-api.com/v6/latest/{curr}"
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(open_url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("result") == "success":
                        rates = data.get("rates", {})
                        if "INR" in rates:
                            rate_dec = Decimal(str(rates["INR"]))
                            return ExchangeRateResult(
                                currency=curr,
                                rate=rate_dec,
                                rate_date=fx_date,
                                requested_date=fx_date,
                                source=f"{self.name}_OPEN",
                                raw_data={"time_last_update_utc": data.get("time_last_update_utc")},
                            )
        except Exception as e:
            logger.warning(f"ExchangeRate-API open call failed for {curr}: {e}")

        return None


class FrankfurterProvider(ForexProvider):
    """
    Frankfurter API provider (European Central Bank reference rates).
    Docs: https://frankfurter.dev/
    """

    @property
    def name(self) -> str:
        return "FRANKFURTER"

    async def fetch_rate(self, currency: str, fx_date: date) -> Optional[ExchangeRateResult]:
        curr = currency.upper().strip()
        if curr == "INR":
            return ExchangeRateResult(
                currency="INR",
                rate=Decimal("1.000000"),
                rate_date=fx_date,
                requested_date=fx_date,
                source=self.name,
            )

        timeout = getattr(settings, "FX_REQUEST_TIMEOUT", 10.0)
        date_str = fx_date.strftime("%Y-%m-%d")
        url = f"https://api.frankfurter.dev/v1/{date_str}?from={curr}&to=INR"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("rates", {})
                    if "INR" in rates:
                        rate_dec = Decimal(str(rates["INR"]))
                        actual_date_str = data.get("date", date_str)
                        actual_date = date.fromisoformat(actual_date_str) if actual_date_str else fx_date
                        return ExchangeRateResult(
                            currency=curr,
                            rate=rate_dec,
                            rate_date=actual_date,
                            requested_date=fx_date,
                            source=self.name,
                            raw_data=data,
                        )
        except Exception as e:
            logger.warning(f"Frankfurter API call failed for {curr} on {date_str}: {e}")

        return None


class StaticFallbackProvider(ForexProvider):
    """
    Guaranteed static fallback provider using resilient reference rates.
    Ensures the application never crashes during network partitions.
    """

    @property
    def name(self) -> str:
        return "STATIC_FALLBACK"

    async def fetch_rate(self, currency: str, fx_date: date) -> Optional[ExchangeRateResult]:
        curr = currency.upper().strip()
        rate = STATIC_FALLBACK_RATES.get(curr, Decimal("1.000000") if curr == "INR" else Decimal("87.123456"))
        return ExchangeRateResult(
            currency=curr,
            rate=rate,
            rate_date=fx_date,
            requested_date=fx_date,
            source=self.name,
            is_fallback=True,
        )


class ForexService:
    """
    Central Forex Service managing provider orchestration, in-memory caching,
    recognition/processing date defaults, Decimal currency conversions, and auditability.
    """

    def __init__(self, provider: Optional[ForexProvider] = None):
        self._cache: Dict[Tuple[str, str, str], Tuple[ExchangeRateResult, float]] = {}
        self._lock = threading.Lock()
        self._provider = provider or self._resolve_configured_provider()
        self._rbi_provider = RbiReferenceRateProvider()
        self._er_api_provider = ExchangeRateApiProvider()
        self._frankfurter_provider = FrankfurterProvider()
        self._fallback_provider = StaticFallbackProvider()

    def _resolve_configured_provider(self) -> ForexProvider:
        provider_name = (
            getattr(settings, "FOREX_PROVIDER", None)
            or getattr(settings, "FX_PRIMARY_PROVIDER", "RBI")
        ).upper()

        if "RBI" in provider_name:
            return RbiReferenceRateProvider()
        if "FRANKFURTER" in provider_name:
            return FrankfurterProvider()
        return ExchangeRateApiProvider()

    def set_provider(self, provider: ForexProvider) -> None:
        """Allow dynamic provider injection (useful for tests and runtime configuration)."""
        self._provider = provider

    def resolve_fx_date(
        self,
        invoice_date: Optional[date] = None,
        processing_date: Optional[date] = None,
    ) -> date:
        """
        Resolves the appropriate FX date based on Finance rules.
        Default rule for FOREIGN_SERVICE invoices is INVOICE DATE.
        """
        date_source = getattr(settings, "FX_DATE_SOURCE", "INVOICE_DATE").upper()

        if date_source == "INVOICE_DATE":
            if invoice_date is not None:
                return invoice_date
            if processing_date is not None:
                return processing_date

        if date_source == "PROCESSING_DATE":
            if processing_date is not None:
                return processing_date
            if invoice_date is not None:
                return invoice_date

        if invoice_date is not None:
            return invoice_date

        if processing_date is not None:
            return processing_date

        # Default fallback to current UTC date (recognition date)
        return datetime.now(timezone.utc).date()

    @staticmethod
    def _normalize_currency(currency: Optional[str]) -> str:
        """Validates and standardizes currency code to 3-letter uppercase ISO."""
        if not currency or not str(currency).strip():
            return "INR"
        cleaned = str(currency).strip().upper()
        # Keep only alphabetic characters
        alphabetic = "".join(c for c in cleaned if c.isalpha())
        return alphabetic[:3] if len(alphabetic) >= 3 else (alphabetic or "INR")

    async def get_exchange_rate(
        self,
        currency: str,
        fx_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> ExchangeRateResult:
        """
        Retrieves exchange rate for foreign currency to INR on the given fx_date.
        Uses in-memory cache to prevent duplicate calls for (currency + fx_date + provider).
        """
        curr = self._normalize_currency(currency)
        target_date = fx_date or self.resolve_fx_date()

        # INR is always 1.000000
        if curr == "INR":
            return ExchangeRateResult(
                currency="INR",
                rate=Decimal("1.000000"),
                rate_date=target_date,
                requested_date=target_date,
                source="IDENTITY",
            )

        provider_name = self._provider.name
        cache_key = (curr, target_date.isoformat(), provider_name)
        now_ts = datetime.now(timezone.utc).timestamp()
        ttl = float(getattr(settings, "FX_CACHE_TTL_SECONDS", 86400))

        if not force_refresh:
            with self._lock:
                if cache_key in self._cache:
                    cached_result, cached_ts = self._cache[cache_key]
                    if (now_ts - cached_ts) < ttl:
                        return cached_result

        # Primary provider lookup
        result: Optional[ExchangeRateResult] = None
        try:
            result = await self._provider.fetch_rate(curr, target_date)
            if result is not None and result.rate <= Decimal("0.000000"):
                logger.warning(f"Provider {provider_name} returned non-positive rate {result.rate} for {curr}")
                result = None
        except Exception as exc:
            logger.error(f"Error fetching FX rate from {provider_name} for {curr} on {target_date}: {exc}")

        # Secondary / Multi-tier Fallback lookup if primary failed
        if result is None and not isinstance(self._provider, FrankfurterProvider):
            try:
                result = await self._frankfurter_provider.fetch_rate(curr, target_date)
                if result is not None and result.rate <= Decimal("0.000000"):
                    result = None
            except Exception:
                pass

        if result is None and not isinstance(self._provider, RbiReferenceRateProvider) and curr in RbiReferenceRateProvider.SUPPORTED_CURRENCIES:
            try:
                result = await self._rbi_provider.fetch_rate(curr, target_date)
                if result is not None and result.rate <= Decimal("0.000000"):
                    result = None
            except Exception:
                pass

        if result is None and not isinstance(self._provider, ExchangeRateApiProvider):
            try:
                result = await self._er_api_provider.fetch_rate(curr, target_date)
                if result is not None and result.rate <= Decimal("0.000000"):
                    result = None
            except Exception:
                pass

        if result is None:
            logger.warning(f"Using StaticFallbackProvider for {curr} on {target_date}")
            result = await self._fallback_provider.fetch_rate(curr, target_date)

        # Store in cache
        with self._lock:
            self._cache[cache_key] = (result, now_ts)

        return result

    def get_rate(
        self,
        currency: str,
        fx_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> ExchangeRateResult:
        """Synchronous wrapper for get_exchange_rate."""
        import asyncio
        curr = self._normalize_currency(currency)
        target_date = fx_date or self.resolve_fx_date()
        cache_key = (curr, target_date.isoformat(), self._provider.name)
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key][0]

        try:
            return asyncio.run(self.get_exchange_rate(currency, fx_date, force_refresh))
        except RuntimeError:
            # Event loop is already running in current thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    lambda: asyncio.run(self.get_exchange_rate(currency, fx_date, force_refresh))
                ).result(timeout=15.0)

    @staticmethod
    def convert_to_inr(original_amount: Decimal, exchange_rate: Decimal) -> Decimal:
        """
        Converts an original foreign amount to INR using Decimal arithmetic.
        Rounds to 2 decimal places with ROUND_HALF_UP.
        Example: 6400 USD * 87.123456 = 557590.1184 -> 557590.12 INR.
        """
        if not isinstance(original_amount, Decimal):
            original_amount = Decimal(str(original_amount))
        if not isinstance(exchange_rate, Decimal):
            exchange_rate = Decimal(str(exchange_rate))

        if exchange_rate <= Decimal("0.000000"):
            raise ValueError(f"Exchange rate must be strictly positive, got: {exchange_rate}")

        converted = original_amount * exchange_rate
        return converted.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)

    @staticmethod
    def apply_finance_override(
        original_rate: Decimal,
        override_rate: Optional[Decimal],
        override_reason: Optional[str],
    ) -> Tuple[Decimal, bool, Optional[str], Decimal]:
        """
        Calculates active FX rate and preserves audit metadata.
        Returns: (active_rate, is_overridden, reason, original_system_rate)
        """
        if not isinstance(original_rate, Decimal):
            original_rate = Decimal(str(original_rate))

        orig_dec = original_rate.quantize(RATE_QUANTIZE, rounding=ROUND_HALF_UP)
        if override_rate is not None:
            if not isinstance(override_rate, Decimal):
                override_rate = Decimal(str(override_rate))
            if override_rate > Decimal("0.000000"):
                ovr_dec = override_rate.quantize(RATE_QUANTIZE, rounding=ROUND_HALF_UP)
                is_overridden = ovr_dec != orig_dec
                return ovr_dec, is_overridden, override_reason if is_overridden else None, orig_dec

        return orig_dec, False, None, orig_dec


# Global singleton instance
forex_service = ForexService()
