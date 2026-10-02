"""Toss Securities candle data adapter for the existing sonification engine."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "https://openapi.tossinvest.com"
SUPPORTED_INTERVALS = {"1m", "1d"}
SUPPORTED_RANKING_TYPES = {
    "MARKET_TRADING_AMOUNT",
    "MARKET_TRADING_VOLUME",
    "TOP_GAINERS",
    "TOP_LOSERS",
    "TOSS_SECURITIES_TRADING_AMOUNT",
    "TOSS_SECURITIES_TRADING_VOLUME",
}
SUPPORTED_MARKET_COUNTRIES = {"KR", "US"}
SUPPORTED_RANKING_DURATIONS = {"realtime", "1d", "1w", "1mo", "3mo", "6mo", "1y"}


class StockDataError(RuntimeError):
    """Raised when Toss Securities data cannot be fetched or parsed."""


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
        return [candle.close for candle in self.candles]


def _sample_candles(symbol: str, interval: str, count: int) -> StockSeries:
    step = timedelta(minutes=1) if interval == "1m" else timedelta(days=1)
    start = datetime(2026, 1, 2, 9, 0)
    pullbacks = [0, 100, -50, 200, 400, 350]
    candles: List[Candle] = []
    for index in range(count):
        close = 72000 + (index // len(pullbacks)) * 450 + pullbacks[index % len(pullbacks)]
        open_price = float(close - (50 if index % 2 == 0 else -50))
        candles.append(
            Candle(
                timestamp=(start + step * index).isoformat(),
                open=open_price,
                high=float(max(open_price, close) + 100),
                low=float(min(open_price, close) - 100),
                close=float(close),
                volume=float(100_000 + index * 1_000),
            )
        )
    return StockSeries(symbol=symbol, interval=interval, candles=candles, source="sample")


def get_sample_candles(symbol: str, interval: str = "1m", count: int = 30) -> StockSeries:
    """Return deterministic demo data without attempting a live API call."""
    symbol = symbol.strip().upper()
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 2 <= count <= 200:
        raise ValueError("count must be between 2 and 200")
    return _sample_candles(symbol, interval, count)


def _read_json(response) -> dict:
    try:
        return json.loads(response.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StockDataError("Toss Securities returned an invalid JSON response") from exc


def _issue_access_token(client_id: str, client_secret: str, base_url: str, opener: Callable) -> str:
    body = urlencode(
        {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    ).encode("utf-8")
    request = Request(
        f"{base_url}/oauth2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with opener(request, timeout=10) as response:
        payload = _read_json(response)
    token = payload.get("access_token")
    if not token:
        raise StockDataError(payload.get("error_description", "Access token was not returned"))
    return str(token)


def _parse_candles(payload: dict, symbol: str, interval: str, count: int) -> StockSeries:
    values = payload.get("result", {}).get("candles")
    if not isinstance(values, list):
        error = payload.get("error", {})
        raise StockDataError(error.get("message", "Candle data was not returned"))
    candles: List[Candle] = []
    for value in values:
        try:
            volume = value.get("volume")
            candles.append(
                Candle(
                    timestamp=str(value["timestamp"]),
                    open=float(value["openPrice"]),
                    high=float(value["highPrice"]),
                    low=float(value["lowPrice"]),
                    close=float(value["closePrice"]),
                    volume=float(volume) if volume not in (None, "") else None,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StockDataError(f"Invalid candle in Toss Securities response: {exc}") from exc
    if not candles:
        raise StockDataError("Toss Securities returned an empty candle list")
    candles.sort(key=lambda candle: candle.timestamp)
    return StockSeries(symbol=symbol, interval=interval, candles=candles[-count:], source="tossinvest")


def _friendly_http_error(error: HTTPError) -> str:
    if error.code == 401:
        return "토스증권 인증정보가 올바르지 않습니다. Client ID와 Secret을 확인하세요."
    if error.code == 403:
        return "토스증권이 현재 접속 IP를 허용하지 않았습니다. Open API 허용 IP 설정을 확인하세요."
    if error.code == 429:
        return "토스증권 API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요."
    return f"토스증권 API 요청에 실패했습니다. HTTP 상태 코드 {error.code}."


def _friendly_url_error(error: URLError) -> str:
    reason = error.reason
    error_number = getattr(reason, "winerror", None) or getattr(reason, "errno", None)
    if error_number == 10013:
        return (
            "Windows가 토스증권 외부 연결을 차단했습니다. "
            "API 서버를 일반 PowerShell에서 실행하거나 방화벽 정책을 확인하세요."
        )
    return "토스증권 서버에 연결할 수 없습니다. 인터넷 연결과 API 서버 실행 권한을 확인하세요."


def _parse_stock_names(payload: dict) -> Dict[str, str]:
    values = payload.get("result")
    if not isinstance(values, list):
        return {}
    return {
        str(value.get("symbol", "")).upper(): str(value.get("name") or value.get("symbol") or "")
        for value in values
        if value.get("symbol")
    }


def fetch_stock_rankings(
    ranking_type: str = "MARKET_TRADING_AMOUNT",
    market_country: str = "KR",
    duration: str = "realtime",
    count: int = 10,
    *,
    exclude_investment_caution: bool = True,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    opener: Callable = urlopen,
) -> dict:
    """Fetch a Toss market ranking and enrich entries with stock names."""
    ranking_type = ranking_type.strip().upper()
    market_country = market_country.strip().upper()
    duration = duration.strip().lower()
    if ranking_type not in SUPPORTED_RANKING_TYPES:
        raise ValueError(f"unsupported ranking type: {ranking_type}")
    if market_country not in SUPPORTED_MARKET_COUNTRIES:
        raise ValueError(f"unsupported market country: {market_country}")
    if duration not in SUPPORTED_RANKING_DURATIONS:
        raise ValueError(f"unsupported ranking duration: {duration}")
    if ranking_type in {"TOP_GAINERS", "TOP_LOSERS"} and duration == "realtime":
        raise ValueError("TOP_GAINERS and TOP_LOSERS do not support realtime duration")
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")

    resolved_id = client_id or os.getenv("TOSSINVEST_CLIENT_ID")
    resolved_secret = client_secret or os.getenv("TOSSINVEST_CLIENT_SECRET")
    if not resolved_id or not resolved_secret:
        raise StockDataError("TOSSINVEST_CLIENT_ID and TOSSINVEST_CLIENT_SECRET are required")

    base_url = os.getenv("TOSSINVEST_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    try:
        token = _issue_access_token(resolved_id, resolved_secret, base_url, opener)
        query = urlencode({
            "type": ranking_type,
            "marketCountry": market_country,
            "duration": duration,
            "excludeInvestmentCaution": str(exclude_investment_caution).lower(),
            "count": count,
        })
        request = Request(
            f"{base_url}/api/v1/rankings?{query}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        with opener(request, timeout=10) as response:
            payload = _read_json(response)
        result = payload.get("result", {})
        values = result.get("rankings")
        if not isinstance(values, list):
            error = payload.get("error", {})
            raise StockDataError(error.get("message", "Ranking data was not returned"))

        symbols = [str(value.get("symbol", "")).upper() for value in values if value.get("symbol")]
        names: Dict[str, str] = {}
        if symbols:
            stock_query = urlencode({"symbols": ",".join(symbols)})
            stock_request = Request(
                f"{base_url}/api/v1/stocks?{stock_query}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            with opener(stock_request, timeout=10) as response:
                names = _parse_stock_names(_read_json(response))

        rankings = []
        for value in values:
            try:
                symbol = str(value["symbol"]).upper()
                price = value.get("price") or {}
                rankings.append({
                    "rank": int(value["rank"]),
                    "symbol": symbol,
                    "name": names.get(symbol, symbol),
                    "currency": str(value.get("currency") or ("KRW" if market_country == "KR" else "USD")),
                    "last_price": float(price["lastPrice"]),
                    "base_price": float(price["basePrice"]),
                    "change_percent": float(price["changeRate"]) * 100.0,
                    "trading_volume": float(value.get("tradingVolume") or 0),
                    "trading_amount": float(value.get("tradingAmount") or 0),
                })
            except (KeyError, TypeError, ValueError) as exc:
                raise StockDataError(f"Invalid ranking in Toss Securities response: {exc}") from exc
        return {
            "type": ranking_type,
            "market_country": market_country,
            "duration": duration,
            "ranked_at": result.get("rankedAt"),
            "rankings": rankings,
            "source": "tossinvest",
        }
    except (HTTPError, URLError, TimeoutError, StockDataError) as exc:
        if isinstance(exc, HTTPError):
            raise StockDataError(_friendly_http_error(exc)) from exc
        if isinstance(exc, URLError):
            raise StockDataError(_friendly_url_error(exc)) from exc
        if isinstance(exc, StockDataError):
            raise
        raise StockDataError(f"Unable to fetch Toss Securities rankings: {exc}") from exc


def fetch_recent_candles(
    symbol: str,
    interval: str = "1m",
    count: int = 30,
    *,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    fallback_to_sample: bool = True,
    opener: Callable = urlopen,
) -> StockSeries:
    """Fetch chronological Toss candles or deterministic sample candles."""
    symbol = symbol.strip().upper()
    if not symbol or not all(char.isalnum() or char in ".-" for char in symbol):
        raise ValueError("symbol must contain only letters, numbers, period, or hyphen")
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 2 <= count <= 200:
        raise ValueError("count must be between 2 and 200")

    resolved_id = client_id or os.getenv("TOSSINVEST_CLIENT_ID")
    resolved_secret = client_secret or os.getenv("TOSSINVEST_CLIENT_SECRET")
    if not resolved_id or not resolved_secret:
        if fallback_to_sample:
            return _sample_candles(symbol, interval, count)
        raise StockDataError("TOSSINVEST_CLIENT_ID and TOSSINVEST_CLIENT_SECRET are required")

    base_url = os.getenv("TOSSINVEST_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    try:
        token = _issue_access_token(resolved_id, resolved_secret, base_url, opener)
        query = urlencode({"symbol": symbol, "interval": interval, "count": count, "adjusted": "true"})
        request = Request(
            f"{base_url}/api/v1/candles?{query}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        with opener(request, timeout=10) as response:
            return _parse_candles(_read_json(response), symbol, interval, count)
    except (HTTPError, URLError, TimeoutError, StockDataError) as exc:
        if fallback_to_sample:
            return _sample_candles(symbol, interval, count)
        if isinstance(exc, HTTPError):
            raise StockDataError(_friendly_http_error(exc)) from exc
        if isinstance(exc, URLError):
            raise StockDataError(_friendly_url_error(exc)) from exc
        if isinstance(exc, StockDataError):
            raise
        raise StockDataError(f"Unable to fetch Toss Securities candles: {exc}") from exc


def get_close_prices(symbol: str, interval: str = "1m", count: int = 30, **kwargs) -> List[float]:
    return fetch_recent_candles(symbol, interval, count, **kwargs).close_prices
