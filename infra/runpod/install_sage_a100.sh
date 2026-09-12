#!/usr/bin/env bash
set -euo pipefail

ROOT=/workspace/epalle
VENV="$ROOT/venv"
LOG="$ROOT/logs/sage-install.log"
# The base image pins its original nightly Torch build globally. This migration
# intentionally installs a matched stable stack, so suppress that image constraint.
export PIP_CONSTRAINT=/dev/null
mkdir -p "$ROOT/logs" "$ROOT/backups"
exec > >(tee -a "$LOG") 2>&1

echo "[$(date -Is)] stopping ComfyUI"
tmux kill-session -t comfy 2>/dev/null || true
"$VENV/bin/pip" freeze > "$ROOT/backups/requirements-before-sage-$(date +%Y%m%dT%H%M%S).txt"

echo "[$(date -Is)] installing the matched PyTorch CUDA 12.8 stack"
"$VENV/bin/python" -m pip uninstall -y sageattention torch torchvision torchaudio || true
"$VENV/bin/python" -m pip install --no-cache-dir \
  torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 \
  --index-url https://download.pytorch.org/whl/cu128

echo "[$(date -Is)] building SageAttention 2.2.0 for A100 SM80"
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:$PATH"
export TORCH_CUDA_ARCH_LIST=8.0
export EXT_PARALLEL=4
export MAX_JOBS=16
export NVCC_APPEND_FLAGS="--threads 8"
git -C "$ROOT/src/SageAttention" fetch --tags origin
git -C "$ROOT/src/SageAttention" checkout d1a57a546c3d395b1ffcbeecc66d81db76f3b4b5
"$VENV/bin/python" -m pip install --no-cache-dir --no-build-isolation "$ROOT/src/SageAttention"

echo "[$(date -Is)] validating imports and kernels"
"$VENV/bin/python" - <<'PY'
import json
import torch
from sageattention import sageattn

assert torch.__version__.startswith("2.9.1+cu128"), torch.__version__
assert torch.cuda.get_device_capability() == (8, 0)
shapes = [(1, 8, 256, 128), (1, 8, 1024, 128), (2, 16, 512, 64), (1, 24, 2048, 128)]
results = []
for repeat in range(3):
    for shape in shapes:
        q = torch.randn(shape, device="cuda", dtype=torch.float16)
        k = torch.randn(shape, device="cuda", dtype=torch.float16)
        v = torch.randn(shape, device="cuda", dtype=torch.float16)
        out = sageattn(q, k, v, tensor_layout="HND")
        torch.cuda.synchronize()
        assert out.shape == q.shape and torch.isfinite(out).all()
        results.append({"repeat": repeat, "shape": shape, "ok": True})
print(json.dumps({"torch": torch.__version__, "cuda": torch.version.cuda,
                  "gpu": torch.cuda.get_device_name(), "tests": results}))
PY

echo "[$(date -Is)] enabling SageAttention and starting ComfyUI"
EPALLE_USE_SAGE=1 tmux new-session -d -s comfy \
  "export EPALLE_USE_SAGE=1; bash '$ROOT/start-comfy.sh' 2>&1 | tee '$ROOT/logs/comfyui-current.log'"
for _ in $(seq 1 180); do
  curl -sf --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null && break
  sleep 2
done
curl -sf --max-time 5 http://127.0.0.1:8188/system_stats >/dev/null
grep -E "Sage|attention|pytorch version" "$ROOT/logs/comfyui-current.log" | tail -12
echo "[$(date -Is)] installation complete"
