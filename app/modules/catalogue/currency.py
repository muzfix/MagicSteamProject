"""
Currency conversion for card prices.

OMR and AED are both pegged to USD by their central banks — these rates are fixed
by policy and do not float. They are not fetched from an API.
  1 USD = 0.38450 OMR  (Central Bank of Oman, fixed since 1986)
  1 USD = 3.67250 AED  (UAE Central Bank, fixed since 1997)

EUR/USD is a floating rate. We fetch it from frankfurter.app (free, no API key,
open source) and cache it for 6 hours to avoid hitting the API on every request.
"""

from datetime import datetime, timedelta
from typing import Optional

import httpx

_USD_TO_OMR = 0.38450
_USD_TO_AED = 3.67250

_eur_to_usd: float = 1.08          # sensible fallback if API is unreachable
_rate_fetched_at: Optional[datetime] = None
_CACHE_HOURS = 6


def _get_eur_usd_rate() -> float:
    global _eur_to_usd, _rate_fetched_at
    if _rate_fetched_at and datetime.utcnow() - _rate_fetched_at < timedelta(hours=_CACHE_HOURS):
        return _eur_to_usd
    try:
        with httpx.Client(timeout=4) as client:
            r = client.get("https://api.frankfurter.app/latest?from=EUR&to=USD")
            r.raise_for_status()
            _eur_to_usd = float(r.json()["rates"]["USD"])
            _rate_fetched_at = datetime.utcnow()
    except Exception:
        pass  # keep the last known or fallback rate
    return _eur_to_usd


def add_local_prices(prices: Optional[dict]) -> Optional[dict]:
    """
    Takes a Scryfall prices dict and returns it with omr and aed keys added.
    Returns None if prices is None.
    """
    if not prices:
        return prices

    result = dict(prices)

    usd: Optional[float] = None
    try:
        if prices.get("usd"):
            usd = float(prices["usd"])
    except (ValueError, TypeError):
        pass

    if usd is None:
        try:
            if prices.get("eur"):
                usd = float(prices["eur"]) * _get_eur_usd_rate()
        except (ValueError, TypeError):
            pass

    if usd is not None:
        result["omr"] = round(usd * _USD_TO_OMR, 3)
        result["aed"] = round(usd * _USD_TO_AED, 3)
    else:
        result["omr"] = None
        result["aed"] = None

    return result
