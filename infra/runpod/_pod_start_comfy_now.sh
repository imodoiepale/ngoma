#!/usr/bin/env bash
# Start ComfyUI on 8188 without waiting for SETUP_COMPLETE or remaining models.
set -eu
ROOT=/workspace/epalle
LOG="$ROOT/logs/comfy.log"
PY="$ROOT/venv/bin/python"
mkdir -p "$ROOT/logs" "$ROOT/ComfyUI/user"

if [ ! -f "$ROOT/ComfyUI/main.py" ]; then
  echo "COMFY_MAIN_MISSING"
  exit 1
fi
if [ ! -x "$PY" ]; then
  echo "VENV_MISSING"
  exit 1
fi

if [ ! -f "$ROOT/ComfyUI/extra_model_paths.yaml" ]; then
  cat > "$ROOT/ComfyUI/extra_model_paths.yaml" <<'PATHS'
epalle_persistent:
  base_path: /workspace/epalle/models
  checkpoints: checkpoints
  clip: clip
  clip_vision: clip_vision
  controlnet: controlnet
  diffusion_models: diffusion_models
  embeddings: embeddings
  loras: loras
  text_encoders: text_encoders
  vae: vae
PATHS
fi

# SAM3 prestartup failed without this; install only if missing so we do not block.
"$PY" -c "import comfy_env" 2>/dev/null || "$PY" -m pip install -q comfy-env || true

if curl -sf --max-time 4 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo "COMFY_ALREADY_UP"
  curl -s --max-time 8 http://127.0.0.1:8188/system_stats
  exit 0
fi

# Kill a half-started listener so we own 8188.
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8188/tcp >/dev/null 2>&1 || true
fi
sleep 1

export PYTHONUNBUFFERED=1
cd "$ROOT/ComfyUI"
nohup "$PY" main.py --listen 0.0.0.0 --port 8188 --user-directory "$ROOT/ComfyUI/user" --highvram \
  > "$LOG" 2>&1 &
echo "COMFY_PID=$!"

for i in $(seq 1 60); do
  if curl -sf --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
    echo "COMFY_UP after ${i}0s-ish poll $i"
    curl -s --max-time 8 http://127.0.0.1:8188/system_stats
    echo
    ss -lntp | grep 8188 || true
    exit 0
  fi
  sleep 5
done

echo "COMFY_NOT_UP_AFTER_300S"
echo "=== last 40 log lines ==="
tail -40 "$LOG" || true
exit 2
