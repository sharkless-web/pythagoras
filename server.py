from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from chart_data import ChartData, ExistingStockProvider, summarize_chart
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import engine
import config
from spatial_audio import generate_spatial_audio
from stock_service import StockDataError, fetch_recent_candles, fetch_stock_rankings, get_sample_candles

app = FastAPI(title="Project Pythagoras Graph Accessibility API")
BASE_DIR = Path(__file__).resolve().parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SoundRequest(BaseModel):
    data: List[float]
    max_freq: float
    waveform: str = "sine"


class SpatialSoundRequest(BaseModel):
    prices: List[float]
    volumes: Optional[List[float]] = None
    timestamps: Optional[List[str]] = None
    min_frequency: float = config.DEFAULT_MIN_FREQ
    max_frequency: float = config.DEFAULT_MAX_FREQ
    min_amplitude: float = config.DEFAULT_MIN_AMPLITUDE
    max_amplitude: float = config.DEFAULT_MAX_AMPLITUDE
    duration_seconds: float = config.TOTAL_PLAY_TIME
    waveform: str = "sine"


def resample_data(data: List[float], target_duration_sec: float, sample_rate: int) -> np.ndarray:
    target_length = int(target_duration_sec * sample_rate)
    original_indices = np.linspace(0, 1, len(data))
    target_indices = np.linspace(0, 1, target_length)
    return np.interp(target_indices, original_indices, data)


STOCK_NAMES = {
    "005930": ("삼성전자", "KRW"),
    "000660": ("SK하이닉스", "KRW"),
    "035420": ("NAVER", "KRW"),
    "035720": ("카카오", "KRW"),
    "051910": ("LG화학", "KRW"),
    "AAPL": ("애플", "USD"),
    "MSFT": ("마이크로소프트", "USD"),
    "NVDA": ("엔비디아", "USD"),
    "TSLA": ("테슬라", "USD"),
}


@app.get("/stock-search")
def stock_search(q: str = ""):
    query = q.strip().lower()
    matches = [
        {"symbol": symbol, "name": name, "currency": currency}
        for symbol, (name, currency) in STOCK_NAMES.items()
        if not query or query in symbol.lower() or query in name.lower()
    ]
    return {"results": matches[:10]}


@app.get("/stock-rankings")
def stock_rankings(
    type: str = "MARKET_TRADING_AMOUNT",
    market_country: str = "KR",
    duration: str = "realtime",
    count: int = 10,
):
    try:
        return fetch_stock_rankings(type, market_country, duration, count)
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)
    except StockDataError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=503)


@app.get("/stock-candles")
def stock_candles(symbol: str = "005930", interval: str = "1m", count: int = 30, demo: bool = False):
    try:
        series = get_sample_candles(symbol, interval, count) if demo else fetch_recent_candles(
            symbol, interval, count, fallback_to_sample=False
        )
        closes = series.close_prices
        minimum, maximum = min(closes), max(closes)
        normalized = [(value - minimum) / (maximum - minimum) if maximum != minimum else 0.5 for value in closes]
        first, latest = closes[0], closes[-1]
        change = latest - first
        change_percent = (change / first * 100.0) if first else 0.0
        name, default_currency = STOCK_NAMES.get(series.symbol, (series.symbol, "KRW"))
        candle_currency = default_currency
        chart = ExistingStockProvider(series).load() if all(c.volume is not None for c in series.candles) else None
        return {
            "chart": chart.model_dump(mode="json") if chart else None,
            "summary": summarize_chart(chart) if chart else None,
            "symbol": series.symbol,
            "name": name,
            "currency": candle_currency,
            "interval": series.interval,
            "source": series.source,
            "candles": [candle.__dict__ for candle in series.candles],
            "close_prices": closes,
            "volumes": [candle.volume for candle in series.candles],
            "metrics": {
                "latest": latest,
                "change": change,
                "change_percent": change_percent,
                "high": max(c.high for c in series.candles),
                "low": min(c.low for c in series.candles),
                "latest_timestamp": series.candles[-1].timestamp,
            },
            "analysis": engine.analyze_timeseries(normalized),
        }
    except (ValueError, StockDataError) as exc:
        return JSONResponse({"detail": str(exc)}, status_code=503)


@app.post("/sonify-data")
async def sonify_data(req: SoundRequest):
    try:
        resampled_data = resample_data(req.data, config.TOTAL_PLAY_TIME, config.SAMPLE_RATE)
        audio_vf = engine.generate_stereo_sound(resampled_data, req.max_freq, req.waveform)
        return StreamingResponse(audio_vf, media_type="audio/wav")
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)


@app.post("/sonify-spatial")
async def sonify_spatial(req: SpatialSoundRequest):
    """Sonify aligned primary and supporting time-series data."""
    if req.volumes is not None and len(req.prices) != len(req.volumes):
        return JSONResponse(
            {"detail": "prices and volumes must have the same length"}, status_code=422
        )
    if req.timestamps is not None and len(req.prices) != len(req.timestamps):
        return JSONResponse(
            {"detail": "prices and timestamps must have the same length"}, status_code=422
        )
    try:
        audio_vf = generate_spatial_audio(
            req.prices,
            req.volumes,
            min_frequency=req.min_frequency,
            max_frequency=req.max_frequency,
            min_amplitude=req.min_amplitude,
            max_amplitude=req.max_amplitude,
            duration_seconds=req.duration_seconds,
            waveform_type=req.waveform,
        )
        return StreamingResponse(
            audio_vf,
            media_type="audio/wav",
            headers={"X-Data-Points": str(len(req.prices))},
        )
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)


@app.post("/analyze-graph-image")
async def analyze_graph_image(
    image: UploadFile = File(...),
    crop_x: Optional[int] = Form(None),
    crop_y: Optional[int] = Form(None),
    crop_width: Optional[int] = Form(None),
    crop_height: Optional[int] = Form(None),
    chart_type: str = Form("auto"),
    color_scheme: str = Form("red_up_blue_down"),
):
    try:
        image_bytes = await image.read()
        crop = None
        if None not in (crop_x, crop_y, crop_width, crop_height):
            crop = {"x": crop_x, "y": crop_y, "width": crop_width, "height": crop_height}
        result = engine.extract_timeseries_from_image(image_bytes, crop=crop, chart_type=chart_type, color_scheme=color_scheme)
        return JSONResponse(result)
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)
    except Exception as exc:
        return JSONResponse({"detail": f"그래프 이미지 분석 중 오류가 발생했습니다: {exc}"}, status_code=500)


class StockSoundRequest(ChartData):
    min_frequency: float = config.DEFAULT_MIN_FREQ
    max_frequency: float = config.DEFAULT_MAX_FREQ
    min_amplitude: float = config.DEFAULT_MIN_AMPLITUDE
    max_amplitude: float = config.DEFAULT_MAX_AMPLITUDE
    duration_seconds: float = 8
    waveform: str = "sine"
    start_index: int = 0
    end_index: Optional[int] = None
    mapping_mode: str = "trend"


@app.post("/sonify-stock")
def sonify_stock(request: StockSoundRequest):
    try:
        output = generate_spatial_audio(
            [c.close for c in request.candles], [c.volume for c in request.candles],
            min_frequency=request.min_frequency, max_frequency=request.max_frequency,
            min_amplitude=request.min_amplitude, max_amplitude=request.max_amplitude,
            duration_seconds=request.duration_seconds, waveform_type=request.waveform,
            start_index=request.start_index, end_index=request.end_index,
            mapping_mode=request.mapping_mode)
        return StreamingResponse(output, media_type="audio/wav")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# Only public assets are exposed, never repository files or environment files.
PUBLIC_FILES = {"index.html", "app.js", "navigator.js", "workspace.js", "tts.js", "style.css"}
@app.get("/")
def home():
    return FileResponse(BASE_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/{name}")
def public_file(name: str):
    if name not in PUBLIC_FILES:
        raise HTTPException(404)
    return FileResponse(BASE_DIR / name, headers={"Cache-Control": "no-cache"})
