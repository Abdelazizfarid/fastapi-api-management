#!/bin/bash
# Restart script for FastAPI server

cd /home/ubuntu/fastapi_app

# Find and kill existing uvicorn process
PID=$(ps aux | grep '[u]vicorn main:app' | awk '{print $2}')
if [ ! -z "$PID" ]; then
    kill $PID
    sleep 2
fi

# Start the server in background
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &

echo "Server restarted successfully"

