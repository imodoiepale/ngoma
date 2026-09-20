#!/usr/bin/env bash
# Report setup/download state and start ComfyUI on 8188 if it is not already up.
set -euo pipefail
ROOT=/workspace/epalle
echo "=== processes ==="
ps aux | grep -E 'setup-pod|download_planned|ComfyUI/main.py|jupyter' | grep -v grep || true
echo "=== setup complete count ==="
grep -c SETUP_COMPLETE "$ROOT/logs/setup-pod.log" 2>/dev/null || echo 0
echo "=== setup tail ==="
tail -12 "$ROOT/logs/setup-pod.log" 2>/dev/null || echo NO_SETUP_LOG
echo "=== download ==="
pgrep -af download_planned.py || echo DOWNLOAD_DEAD
tail -12 "$ROOT/logs/download-planned.log" 2>/dev/null || echo NO_DOWNLOAD_LOG
echo "=== models ==="
du -sh "$ROOT/models" 2>/dev/null || echo NO_MODELS
find "$ROOT/models" -type f 2>/dev/null | wc -l
echo "=== comfy tree ==="
test -f "$ROOT/ComfyUI/main.py" && echo COMFY_MAIN_YES || echo COMFY_MAIN_NO
test -x "$ROOT/venv/bin/python" && echo VENV_YES || echo VENV_NO
echo "=== listening ==="
(ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true) | grep -E '8188|8888|3000' || echo NONE

if [ ! -f "$ROOT/ComfyUI/main.py" ] || [ ! -x "$ROOT/venv/bin/python" ]; then
  echo "=== start skipped: ComfyUI or venv not ready ==="
  exit 0
fi

# Models live on the volume. Write the map now so Comfy can see them even if
# setup-pod.sh has not reached SETUP_COMPLETE yet.
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
  echo "=== wrote extra_model_paths.yaml ==="
fi

if curl -sf --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo "=== comfy already up ==="
  curl -s --max-time 5 http://127.0.0.1:8188/system_stats || true
  exit 0
fi

mkdir -p "$ROOT/logs" "$ROOT/ComfyUI/user"
if [ -x "$ROOT/start-comfy.sh" ]; then
  STARTER="$ROOT/start-comfy.sh"
else
  STARTER="$ROOT/_start_comfy_now.sh"
  cat > "$STARTER" <<'START'
#!/usr/bin/env bash
set -euo pipefail
ROOT=/workspace/epalle
cd "$ROOT/ComfyUI"
exec "$ROOT/venv/bin/python" main.py --listen 0.0.0.0 --port 8188 --user-directory "$ROOT/ComfyUI/user" --highvram
START
  chmod +x "$STARTER"
fi

nohup bash "$STARTER" > "$ROOT/logs/comfy.log" 2>&1 &
echo COMFY_PID=$!
sleep 8
echo "=== comfy log ==="
tail -30 "$ROOT/logs/comfy.log" || true
if curl -sf --max-time 5 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo "=== comfy listening ==="
else
  echo "=== comfy not listening yet (still booting or blocked) ==="
fi
