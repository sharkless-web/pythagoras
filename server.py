from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import numpy as np
import engine

app = FastAPI()

# 💡 422 에러 방지: 프론트에서 넘어올 데이터의 '규격'을 정확히 정의합니다.
class SoundRequest(BaseModel):
    data: List[float]
    max_freq: float

@app.post("/sonify-data")
async def sonify_data(req: SoundRequest):
    # 받은 데이터와 주파수를 기존 engine에 넘겨서 오디오 파일 생성
    audio_vf = engine.generate_stereo_sound(np.array(req.data), req.max_freq)
    
    # 생성된 WAV 파일을 프론트엔드로 전송
    return StreamingResponse(audio_vf, media_type="audio/wav")