"""
Forex & RBI Reference Rates API Router
======================================
Provides live and historical exchange rates, statutory RBI currency feeds,
and currency conversion calculations for Sakshi Finance.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel

from app.core.security import AuthenticatedUser, get_current_user
from app.services.forex_service import forex_service, STATIC_FALLBACK_RATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forex", tags=["Forex & RBI Rates"])


class ForexRateItem(BaseModel):
    currency: str
    target_currency: str = "INR"
    rate: float
    rate_formatted: str
    rate_date: str
    source: str
    is_fallback: bool = False
    status: str = "LIVE"


class ForexRatesListResponse(BaseModel):
    base: str = "INR"
    date: str
    last_updated: str
    rates: List[ForexRateItem]
    rbi_reference_currencies: List[str]


class CurrencyConversionRequest(BaseModel):
    amount: float
    from_currency: str
    to_currency: str = "INR"
    date: Optional[str] = None


class CurrencyConversionResponse(BaseModel):
    original_amount: float
    from_currency: str
    to_currency: str
    rate: float
    converted_amount: float
    rate_date: str
    source: str


@router.get("/rates", response_model=ForexRatesListResponse)
async def get_forex_rates(
    rate_date: Optional[date] = Query(None, description="Optional date for historical rate lookup"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Fetches official RBI and market reference rates for primary international currencies against INR.
    """
    target_date = rate_date or date.today()
    supported_currencies = ["USD", "EUR", "GBP", "JPY", "SGD", "AED", "CAD", "AUD"]
    rbi_ref_currencies = ["USD", "EUR", "GBP", "JPY"]

    rate_items = []
    for curr in supported_currencies:
        try:
            res = await forex_service.get_exchange_rate(curr, target_date)
            rate_items.append(
                ForexRateItem(
                    currency=curr,
                    target_currency="INR",
                    rate=float(res.rate),
                    rate_formatted=f"₹{res.rate:.4f}",
                    rate_date=res.rate_date.isoformat(),
                    source=res.source,
                    is_fallback=res.is_fallback,
                    status="RBI_REFERENCE" if curr in rbi_ref_currencies else "MARKET_RATE",
                )
            )
        except Exception as e:
            logger.warning(f"Error fetching rate for {curr}: {e}")
            fallback_val = STATIC_FALLBACK_RATES.get(curr, Decimal("1.0"))
            rate_items.append(
                ForexRateItem(
                    currency=curr,
                    target_currency="INR",
                    rate=float(fallback_val),
                    rate_formatted=f"₹{fallback_val:.4f}",
                    rate_date=target_date.isoformat(),
                    source="Static Fallback (Disaster Recovery)",
                    is_fallback=True,
                    status="FALLBACK",
                )
            )

    return ForexRatesListResponse(
        base="INR",
        date=target_date.isoformat(),
        last_updated=datetime.now(timezone.utc).isoformat(),
        rates=rate_items,
        rbi_reference_currencies=rbi_ref_currencies,
    )


@router.post("/convert", response_model=CurrencyConversionResponse)
async def convert_currency(
    payload: CurrencyConversionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Converts foreign currency amount to INR using authoritative RBI exchange rates.
    """
    target_date = None
    if payload.date:
        try:
            target_date = date.fromisoformat(payload.date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    target_date = target_date or date.today()
    try:
        res = await forex_service.get_exchange_rate(payload.from_currency.upper(), target_date)
        amount_dec = Decimal(str(payload.amount))
        converted_dec = forex_service.convert_to_inr(amount_dec, res.rate)

        return CurrencyConversionResponse(
            original_amount=payload.amount,
            from_currency=payload.from_currency.upper(),
            to_currency=payload.to_currency.upper(),
            rate=float(res.rate),
            converted_amount=float(converted_dec),
            rate_date=res.rate_date.isoformat(),
            source=res.source,
        )
    except Exception as e:
        logger.error(f"Currency conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")

