#!/usr/bin/env bash
set -euo pipefail
ROOT=/workspace/epalle
PY="$ROOT/venv/bin/python"
cd "$ROOT/ComfyUI"
ARGS=(--listen 0.0.0.0 --port 8188 --user-directory "$ROOT/ComfyUI/user" --highvram)

# SageAttention 2.2.0 is compiled for SM80 against torch 2.9.1+cu128. Set
# EPALLE_USE_SAGE=0 only when diagnosing a model-specific compatibility problem.
if [ "${EPALLE_USE_SAGE:-1}" = "1" ]; then
  if "$PY" -c 'import sageattention' >/dev/null 2>&1; then
    echo "SageAttention enabled for the validated A100 runtime"
    ARGS+=(--use-sage-attention)
  else
    echo "EPALLE_USE_SAGE=1 but sageattention does not import; using PyTorch attention"
  fi
else
  echo "EPALLE_USE_SAGE=0; using PyTorch SDPA attention"
fi

exec "$PY" main.py "${ARGS[@]}"
