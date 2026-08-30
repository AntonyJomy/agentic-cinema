#!/bin/bash
# Stop local ScriptClear API + frontend servers.
set -e
cd "$(dirname "$0")/.."
for port in 8000 8001 5173 5174 5175; do
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Stopping port $port (PIDs: $pids)"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  else
    echo "Port $port already free"
  fi
done
pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "vite --host 127.0.0.1" 2>/dev/null || true
sleep 1
echo "---"
for port in 8000 8001 5173 5174 5175; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "STILL RUNNING: $port"
  else
    echo "$port free"
  fi
done
