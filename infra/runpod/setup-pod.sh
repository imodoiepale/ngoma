#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/epalle/{models,projects,cache,manifests,logs,libraries,workflows,workflow-api,src,outputs}
ROOT=/workspace/epalle
if [ ! -d "$ROOT/ComfyUI" ]; then git clone https://github.com/Comfy-Org/ComfyUI.git "$ROOT/ComfyUI"; fi
cd "$ROOT/ComfyUI"
if [ ! -d "$ROOT/venv" ]; then python3 -m venv --system-site-packages "$ROOT/venv"; fi
PY="$ROOT/venv/bin/python"
$PY -m pip install -r requirements.txt
$PY -m pip install huggingface_hub runpod
for item in 'Comfy-Org/ComfyUI-Manager' 'rgthree/rgthree-comfy' 'Kosinkadink/ComfyUI-VideoHelperSuite' 'kijai/ComfyUI-KJNodes' 'kijai/ComfyUI-WanVideoWrapper' 'kijai/ComfyUI-SCAIL-Pose' 'ltdrdata/ComfyUI-Impact-Pack' 'Fannovel16/comfyui_controlnet_aux' 'Fannovel16/ComfyUI-Frame-Interpolation' 'yolain/ComfyUI-Easy-Use' 'ClownsharkBatwing/RES4LYF' 'pythongosssss/ComfyUI-Custom-Scripts' 'seitanism/ComfyUI-H3-Motion-Context-MultiRef' 'drozbay/MaskVidExperiments' 'Nekodificador/ComfyUI-NKD-Basic-Tools' 'Nekodificador/ComfyUI-NKD-Sigmas-Curve'; do
 name="${item##*/}"
 if [ ! -d "custom_nodes/$name" ]; then git clone "https://github.com/$item.git" "custom_nodes/$name"; fi
 if [ -f "custom_nodes/$name/requirements.txt" ]; then $PY -m pip install -r "custom_nodes/$name/requirements.txt"; fi
done
# MATRIX has no pip dependencies. Never overwrite it.
if [ ! -e custom_nodes/matrix-power-nodes ]; then
 git clone https://github.com/imodoiepale/matrix-power-nodes.git custom_nodes/matrix-power-nodes
fi
mkdir -p user/default/workflows/EPALLE
find /workspace/epalle/workflows -type f -name '*.json' -exec cp -n '{}' user/default/workflows/EPALLE/ \; 2>/dev/null || true
cat > extra_model_paths.yaml <<'PATHS'
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
$PY -m pip install -U ninja packaging
bash /workspace/epalle/install-sageattention.sh
if [ -n "${HF_TOKEN:-}" ] && [ -f /workspace/epalle/download-workflow-models.py ]; then
  $PY /workspace/epalle/download-workflow-models.py || true
fi
$PY -m pip freeze > "$ROOT/manifests/runtime-freeze.txt"
git rev-parse HEAD > "$ROOT/manifests/comfy-commit.txt"
for d in custom_nodes/*; do if [ -d "$d/.git" ]; then printf '%s ' "$d"; git -C "$d" rev-parse HEAD; fi; done > "$ROOT/manifests/node-commits.txt"
cat > "$ROOT/start-comfy.sh" <<'START'
#!/usr/bin/env bash
set -euo pipefail
cd /workspace/epalle/ComfyUI
ARGS=(--listen 0.0.0.0 --port 8188 --user-directory /workspace/epalle/ComfyUI/user --highvram)
if /workspace/epalle/venv/bin/python -c 'import sageattention' >/dev/null 2>&1; then ARGS+=(--use-sage-attention); fi
exec /workspace/epalle/venv/bin/python main.py "${ARGS[@]}"
START
chmod +x "$ROOT/start-comfy.sh"
printf 'SETUP_COMPLETE\n'

