"""Fetch recent stock candles and expose their close prices for sonification.

The live implementation uses Twelve Data's ``time_series`` API.  When no API
key is configured, callers can still exercise the complete sonification flow
with deterministic sample candles.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "https://api.twelvedata.com/time_series"
SUPPORTED_INTERVALS = {
    "1min",
    "5min",
    "15min",
    "30min",
    "45min",
    "1h",
    "2h",
    "4h",
    "1day",
    "1week",
    "1month",
}


class StockDataError(RuntimeError):
    """Raised when live candle data cannot be fetched or parsed."""


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


@dataclass(frozen=True)
class StockSeries:
    symbol: str
    interval: str
    candles: List[Candle]
    source: str

    @property
    def close_prices(self) -> List[float]:
        """Return the exact list format accepted by ``/sonify-data``."""
        return [candle.close for candle in self.candles]


def _sample_candles(symbol: str, interval: str, count: int) -> StockSeries:
    interval_deltas = {
        "1min": timedelta(minutes=1),
        "5min": timedelta(minutes=5),
        "15min": timedelta(minutes=15),
        "30min": timedelta(minutes=30),
        "45min": timedelta(minutes=45),
        "1h": timedelta(hours=1),
        "2h": timedelta(hours=2),
        "4h": timedelta(hours=4),
        "1day": timedelta(days=1),
        "1week": timedelta(weeks=1),
        "1month": timedelta(days=30),
    }
    # A repeatable upward trend with small pullbacks makes max/min and direction
    # easy to verify by ear while still exercising non-monotonic input.
    pullbacks = [0, 100, -50, 200, 400, 350]
    start = datetime(2026, 1, 2, 9, 0)
    candles: List[Candle] = []
    for index in range(count):
        close = 72000 + (index // len(pullbacks)) * 450 + pullbacks[index % len(pullbacks)]
        open_price = float(close - (50 if index % 2 == 0 else -50))
        candles.append(
            Candle(
                timestamp=(start + interval_deltas[interval] * index).isoformat(),
                open=open_price,
                high=float(max(open_price, close) + 100),
                low=float(min(open_price, close) - 100),
                close=float(close),
                volume=float(100_000 + index * 1_000),
            )
        )
    return StockSeries(symbol=symbol, interval=interval, candles=candles, source="sample")


def _parse_candles(payload: dict, symbol: str, interval: str, count: int) -> StockSeries:
    if payload.get("status") == "error" or "values" not in payload:
        message = payload.get("message", "API response does not contain candle values")
        raise StockDataError(str(message))

    candles: List[Candle] = []
    for value in payload["values"]:
        try:
            volume = value.get("volume")
            candles.append(
                Candle(
                    timestamp=str(value["datetime"]),
                    open=float(value["open"]),
                    high=float(value["high"]),
                    low=float(value["low"]),
                    close=float(value["close"]),
                    volume=float(volume) if volume not in (None, "") else None,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StockDataError(f"Invalid candle in API response: {exc}") from exc

    if not candles:
        raise StockDataError("API returned an empty candle list")

    # Twelve Data returns newest first. ISO-like timestamps sort correctly here.
    candles.sort(key=lambda candle: candle.timestamp)
    return StockSeries(symbol=symbol, interval=interval, candles=candles[-count:], source="twelve_data")


def fetch_recent_candles(
    symbol: str,
    interval: str = "5min",
    count: int = 30,
    *,
    api_key: Optional[str] = None,
    fallback_to_sample: bool = True,
    opener: Callable = urlopen,
) -> StockSeries:
    """Fetch chronological candles, using sample data when live access is unavailable.

    ``STOCK_API_KEY`` and optional ``STOCK_API_BASE_URL`` configure live access.
    Set ``fallback_to_sample=False`` when a live-data failure should be fatal.
    """
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("symbol must not be empty")
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 2 <= count <= 5000:
        raise ValueError("count must be between 2 and 5000")

    resolved_key = api_key or os.getenv("STOCK_API_KEY")
    if not resolved_key:
        if fallback_to_sample:
            return _sample_candles(symbol, interval, count)
        raise StockDataError("STOCK_API_KEY is not configured")

    base_url = os.getenv("STOCK_API_BASE_URL", DEFAULT_API_BASE_URL)
    query = urlencode(
        {
            "symbol": symbol,
            "interval": interval,
            "outputsize": count,
            "apikey": resolved_key,
            "format": "JSON",
        }
    )
    request = Request(f"{base_url}?{query}", headers={"Accept": "application/json"})
    try:
        with opener(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _parse_candles(payload, symbol, interval, count)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, StockDataError) as exc:
        if fallback_to_sample:
            return _sample_candles(symbol, interval, count)
        if isinstance(exc, StockDataError):
            raise
        raise StockDataError(f"Unable to fetch stock candles: {exc}") from exc


def get_close_prices(
    symbol: str,
    interval: str = "5min",
    count: int = 30,
    **kwargs,
) -> List[float]:
    """Return recent close prices ready for the existing sonification flow."""
    return fetch_recent_candles(symbol, interval, count, **kwargs).close_prices
