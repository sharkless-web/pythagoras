from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()

# 음성 안내 파일들이 저장된 경로
ASSETS_DIR = "assets"

@app.get("/guide/{action}")
async def get_guide_voice(action: str):
    # 요청된 액션에 맞는 파일 경로 설정
    file_path = os.path.join(ASSETS_DIR, f"{action}.mp3")
    
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": "File not found"}

# 가청화 엔진 로직도 나중에 여기 @app.post로 옮기면 됩니다!