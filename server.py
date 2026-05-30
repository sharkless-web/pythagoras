from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import engine
import config

app = FastAPI(title="Project Pythagoras Graph Accessibility API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SoundRequest(BaseModel):
    data: List[float]
    max_freq: float
    waveform: str = "sine"


class MixRequest(BaseModel):
    data_list: List[List[float]]
    max_freq: float
    waveform_list: List[str]


def resample_data(data: List[float], target_duration_sec: float, sample_rate: int) -> np.ndarray:
    target_length = int(target_duration_sec * sample_rate)
    original_indices = np.linspace(0, 1, len(data))
    target_indices = np.linspace(0, 1, target_length)
    return np.interp(target_indices, original_indices, data)


@app.post("/sonify-data")
async def sonify_data(req: SoundRequest):
    resampled_data = resample_data(req.data, config.TOTAL_PLAY_TIME, config.SAMPLE_RATE)
    audio_vf = engine.generate_stereo_sound(resampled_data, req.max_freq, req.waveform)
    return StreamingResponse(audio_vf, media_type="audio/wav")


@app.post("/mix-data")
async def mix_data(req: MixRequest):
    resampled_data_list = [resample_data(d, config.TOTAL_PLAY_TIME, config.SAMPLE_RATE) for d in req.data_list]
    max_freq_list = [req.max_freq] * len(resampled_data_list)
    audio_vf = engine.generate_mixed_sound(resampled_data_list, max_freq_list, req.waveform_list)
    return StreamingResponse(audio_vf, media_type="audio/wav")


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
