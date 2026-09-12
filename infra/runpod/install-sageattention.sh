#!/usr/bin/env bash
set -euo pipefail
ROOT=/workspace/epalle
PY="$ROOT/venv/bin/python"
# SageAttention compiles CUDA kernels for one compute capability, and the venv lives on
# the persistent network volume. So a pod on a different GPU architecture inherits a
# build that imports fine but fails at runtime. Verify the kernel actually executes on
# this GPU, and rebuild if it does not.
if "$PY" -c 'import sageattention' >/dev/null 2>&1; then
  if "$PY" - <<'PROBE' >/dev/null 2>&1
import torch
from sageattention import sageattn
q, k, v = (torch.randn(1, 4, 128, 128, dtype=torch.float16, device="cuda") for _ in range(3))
sageattn(q, k, v, is_causal=False)
torch.cuda.synchronize()
PROBE
  then
    "$PY" -c 'import torch, sageattention; print("SageAttention already working on", torch.cuda.get_device_name(0), torch.cuda.get_device_capability(), "->", sageattention.__file__)'
    exit 0
  fi
  echo "SageAttention is installed but its kernels do not run on this GPU" \
       "($($PY -c 'import torch; print(torch.cuda.get_device_capability())')). Rebuilding." >&2
  "$PY" -m pip uninstall -y sageattention >/dev/null 2>&1 || true
fi
# The runpod/pytorch image ships the CUDA toolkit under /usr/local/cuda* but does not
# put its bin directory on PATH, so a bare `command -v nvcc` wrongly concluded there
# was no compiler and silently fell back to PyTorch attention. Look for it before
# giving up.
# Pick the toolkit whose major version matches torch's CUDA build. Using a mismatched
# nvcc (e.g. 12.8 against a cu130 torch) fails the extension build outright, so the
# first nvcc on disk is not good enough -- it has to be the right one.
TORCH_CUDA_MAJOR="$($PY -c 'import torch; print((torch.version.cuda or "").split(".")[0])' 2>/dev/null || true)"
echo "torch is built for CUDA ${TORCH_CUDA_MAJOR:-unknown}"
for CANDIDATE in /usr/local/cuda-"${TORCH_CUDA_MAJOR}".* /usr/local/cuda-"${TORCH_CUDA_MAJOR}" /usr/local/cuda; do
  if [ -x "$CANDIDATE/bin/nvcc" ]; then
    CANDIDATE_MAJOR="$("$CANDIDATE/bin/nvcc" --version | sed -n 's/.*release \([0-9]*\)\..*/\1/p' | head -1)"
    if [ -z "$TORCH_CUDA_MAJOR" ] || [ "$CANDIDATE_MAJOR" = "$TORCH_CUDA_MAJOR" ]; then
      export CUDA_HOME="$CANDIDATE"
      export PATH="$CUDA_HOME/bin:$PATH"
      export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
      echo "Using nvcc $CANDIDATE_MAJOR at $CUDA_HOME/bin/nvcc"
      break
    fi
  fi
done
if ! command -v nvcc >/dev/null 2>&1; then
  echo "No nvcc matching CUDA ${TORCH_CUDA_MAJOR} found. Install it with:" >&2
  echo "  apt-get install -y cuda-nvcc-${TORCH_CUDA_MAJOR}-0 cuda-cudart-dev-${TORCH_CUDA_MAJOR}-0" >&2
  echo 'Keeping PyTorch attention. SageAttention was not installed.' >&2
  exit 0
fi
if ! command -v nvcc >/dev/null 2>&1; then
  echo 'NVCC is unavailable; keeping PyTorch attention. SageAttention was not installed.' >&2
  exit 0
fi
nvcc --version | tail -2
mkdir -p "$ROOT/src"
if [ ! -d "$ROOT/src/SageAttention/.git" ]; then
  git clone https://github.com/thu-ml/SageAttention.git "$ROOT/src/SageAttention"
else
  git -C "$ROOT/src/SageAttention" fetch --depth=1 origin main
  git -C "$ROOT/src/SageAttention" reset --hard origin/main
fi
CAPABILITY="$($PY -c 'import torch; print(".".join(map(str, torch.cuda.get_device_capability())))')"
export TORCH_CUDA_ARCH_LIST="$CAPABILITY"
export MAX_JOBS="${MAX_JOBS:-8}"
export EXT_PARALLEL=4
export NVCC_APPEND_FLAGS='--threads 8'
"$PY" -m pip install -U ninja packaging
"$PY" -m pip install --no-build-isolation --no-deps "$ROOT/src/SageAttention"
"$PY" -c 'import sageattention; print("SageAttention installed:", sageattention.__file__)'
