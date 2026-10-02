#!/bin/bash
set -e

echo "Starting Pythagoras at http://127.0.0.1:8001"
python -m uvicorn server:app --host 127.0.0.1 --port 8001 &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Open http://127.0.0.1:8001 in your browser. Press Ctrl+C to stop."
wait
