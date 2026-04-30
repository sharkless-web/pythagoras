from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware  # [추가됨] CORS 통신 모듈
from pydantic import BaseModel
from typing import List
import numpy as np
import engine
import config

app = FastAPI()

# [추가됨] 순수 HTML(프론트엔드)에서 백엔드로 요청을 보낼 수 있도록 보안 장벽(CORS) 해제
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
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