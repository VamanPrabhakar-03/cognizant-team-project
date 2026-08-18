#!/bin/sh
set -eu

cd /app/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &
backend_pid=$!

cleanup() {
  kill "$backend_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

exec nginx -g 'daemon off;'
