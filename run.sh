#!/bin/bash

echo "🚀 FastAPI 서버를 시작합니다..."
# 1. 백엔드 서버를 백그라운드(&)에서 실행
uvicorn server:app --reload &

# 2. 서버가 뜰 때까지 2초 대기
sleep 2

echo "🌐 웹 브라우저를 엽니다..."
# 3. Mac 기본 브라우저로 HTML 파일 열기 (run -> open)
open index.html