#!/bin/bash

# 1. 백엔드(FastAPI) 서버를 백그라운드에서 실행
echo "🚀 Starting FastAPI Server..."
uvicorn server:app --host 0.0.0.0 --port 8000 & 

# 2. 잠시 대기 (서버가 완전히 뜰 시간 부여)
sleep 2

# 3. 프론트엔드(Streamlit) 실행
echo "🎧 Starting Streamlit UI..."
streamlit run main.py