from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import numpy as np
import engine

app = FastAPI()

# 데이터 규격 정의: 클라이언트(Streamlit)와 서버 간의 데이터 송수신 약속
class SoundRequest(BaseModel):
    data: List[float]    # 가청화할 수치 데이터 리스트
    max_freq: float      # 사용자가 설정한 가청 주파수 상한선

@app.post("/sonify-data")
async def sonify_data(req: SoundRequest):
    """
    데이터 가청화 API 엔드포인트.
    JSON 포맷으로 받은 수치 데이터를 numpy 배열로 변환하여 사운드 엔진으로 전달함.
    """
    
    # 1. 수치 데이터를 사운드 파형(WAV)으로 변환
    # engine.generate_stereo_sound는 메모리 내 바이너리 스트림(BytesIO)을 반환함
    audio_vf = engine.generate_stereo_sound(np.array(req.data), req.max_freq)
    
    # 2. 생성된 오디오 데이터를 스트리밍 방식으로 반환
    # 파일 전체를 저장하지 않고 메모리에서 브라우저로 직접 전송하여 응답 속도 최적화
    return StreamingResponse(audio_vf, media_type="audio/wav")