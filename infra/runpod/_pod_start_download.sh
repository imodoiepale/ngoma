#!/usr/bin/env bash
# Start (or resume) the full planned model download on the volume.
# Token: inherit from the container init env if SSH stripped it.
set -euo pipefail
ROOT=/workspace/epalle
mkdir -p "$ROOT/logs" "$ROOT/models" "$ROOT/cache/huggingface" "$ROOT/manifests"

if [ -z "${HF_TOKEN:-}" ] && [ -r /proc/1/environ ]; then
  HF_TOKEN=$(python3 - <<'PY'
import os
raw = open("/proc/1/environ", "rb").read().split(b"\0")
for item in raw:
    if item.startswith(b"HF_TOKEN="):
        print(item.split(b"=", 1)[1].decode(), end="")
        break
PY
)
  export HF_TOKEN
fi
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}"
export EPALLE_MODELS="$ROOT/models"
export EPALLE_HF_CACHE="$ROOT/cache/huggingface"
export PYTHONUNBUFFERED=1

if [ -x "$ROOT/venv/bin/python" ]; then PY="$ROOT/venv/bin/python"
else PY=python3
fi
$PY -c "import huggingface_hub" 2>/dev/null || $PY -m pip install -q huggingface_hub

# Resume-safe: already-present files are skipped.
nohup "$PY" "$ROOT/download_planned.py" --plan "$ROOT/download-plan.json" \
  > "$ROOT/logs/download-planned.log" 2>&1 &
echo DOWNLOAD_PID=$!
sleep 3
tail -20 "$ROOT/logs/download-planned.log"
