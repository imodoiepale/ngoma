#!/bin/bash
set -eu
cd /workspace/runpod-slim/ComfyUI
# Do not match this script's own ssh/bash line.
pkill -f '/workspace/runpod-slim/ComfyUI/.venv-cu128/bin/python main.py' || true
sleep 3
. .venv-cu128/bin/activate
nohup python main.py --listen 0.0.0.0 --port 8188 --enable-cors-header \
  >> /workspace/epalle/logs/comfy-template.log 2>&1 &
echo STARTED
sleep 15
curl -sf --max-time 5 http://127.0.0.1:8188/system_stats >/dev/null && echo COMFY_UP || echo COMFY_DOWN
