#!/bin/bash
set -e

echo "Starting FastAPI server at http://127.0.0.1:8000"
python -m uvicorn server:app --host 127.0.0.1 --port 8000 &
API_PID=$!

echo "Starting web UI at http://127.0.0.1:5500"
python -m http.server 5500 --bind 127.0.0.1 &
WEB_PID=$!

cleanup() {
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Open http://127.0.0.1:5500 in your browser. Press Ctrl+C to stop."
wait
