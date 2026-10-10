"""Validated chart boundary shared by CSV and future market providers."""
import csv
import io
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Candle(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("저가 ≤ 시가·종가 ≤ 고가여야 합니다")
        return self


class ChartData(BaseModel):
    symbol: str = Field(default="CSV", max_length=100)
    timeframe: str = Field(default="unknown", max_length=30)
    candles: list[Candle] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def chronological(self):
        dates = [c.timestamp for c in self.candles]
        try:
            if any(a >= b for a, b in zip(dates, dates[1:])):
                raise ValueError("시각은 중복 없이 과거부터 정렬되어야 합니다")
        except TypeError as exc:
            raise ValueError("시간대가 있는 시각과 없는 시각을 혼합할 수 없습니다") from exc
        return self


class ChartProvider(Protocol):
    def load(self) -> ChartData: ...


ALIASES = {
    "timestamp": ("timestamp", "time", "date", "datetime"),
    "open": ("open", "opening"), "high": ("high",), "low": ("low",),
    "close": ("close", "price"), "volume": ("volume", "vol"),
}


class CSVProvider:
    def __init__(self, text, mapping=None, symbol="CSV", timeframe="unknown"):
        self.text, self.mapping = text, mapping or {}
        self.symbol, self.timeframe = symbol, timeframe

    def inspect(self):
        reader = csv.DictReader(io.StringIO(self.text.lstrip("\ufeff")))
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)):
            raise ValueError("CSV 열 이름이 없거나 중복됩니다")
        canonical = {h.strip().lower(): h for h in headers}
        detected = {field: next((canonical[a] for a in aliases if a in canonical), "")
                    for field, aliases in ALIASES.items()}
        detected.update(self.mapping)
        if any(k not in ALIASES or v not in headers for k, v in self.mapping.items()):
            raise ValueError("선택한 CSV 열이 존재하지 않습니다")
        return reader, headers, detected

    def load(self):
        reader, _, mapping = self.inspect()
        if any(not mapping[k] for k in ALIASES):
            raise ValueError("시각, 시가, 고가, 저가, 종가, 거래량 열을 모두 선택하세요")
        if len(set(mapping.values())) != 6:
            raise ValueError("각 필드는 서로 다른 열을 선택해야 합니다")
        candles = []
        for row_number, row in enumerate(reader, 2):
            if len(candles) >= 10000:
                raise ValueError("최대 10,000개 봉까지 지원합니다")
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"{row_number}행의 열 개수가 맞지 않습니다")
            try:
                candles.append(Candle(**{k: row[v].strip() for k, v in mapping.items()}))
            except ValueError as exc:
                raise ValueError(f"{row_number}행: 올바른 날짜, 양수 OHLC, 0 이상 거래량 및 가격 범위를 확인하세요") from exc
        # Sorting CSV is explicit; duplicates and mixed zones remain errors.
        try:
            candles.sort(key=lambda c: c.timestamp)
        except TypeError as exc:
            raise ValueError("CSV 시각의 시간대를 통일하세요") from exc
        return ChartData(symbol=self.symbol, timeframe=self.timeframe, candles=candles)


def summarize_chart(chart: ChartData):
    candles = chart.candles
    first, last = candles[0], candles[-1]
    change = (last.close / first.close - 1) * 100
    largest = max(candles, key=lambda c: c.volume)
    return {"count": len(candles), "start": first.timestamp.isoformat(),
            "end": last.timestamp.isoformat(), "start_close": first.close,
            "end_close": last.close, "change_percent": change,
            "high": max(c.high for c in candles), "low": min(c.low for c in candles),
            "max_volume": largest.volume, "max_volume_timestamp": largest.timestamp.isoformat(),
            "direction": "상승" if change > 0 else "하락" if change < 0 else "동일"}


class ExistingStockProvider:
    """Adapt the existing Toss/sample result without changing its public API."""
    def __init__(self, series):
        self.series = series

    def load(self) -> ChartData:
        return ChartData(symbol=self.series.symbol, timeframe=self.series.interval,
                         candles=[Candle(**c.__dict__) for c in self.series.candles])
