#!/usr/bin/env bash
# Point the official RunPod ComfyUI template at Director models + workflows.
# Prefer bootstrap_director.py (symlink every model folder). This shell path is
# the fallback used before Python is available.
set -eu
MODELS=/workspace/epalle/models
WF_SRC=/workspace/epalle/workflows
PATHS_FILE=/workspace/epalle/extra_model_paths.yaml

if [ -f /workspace/epalle/bootstrap_director.py ]; then
  python3 /workspace/epalle/bootstrap_director.py --no-restart
fi

for ROOT in /workspace/runpod-slim/ComfyUI /workspace/madapps/ComfyUI /workspace/ComfyUI; do
  if [ -f "$ROOT/main.py" ]; then
    echo "COMFY_ROOT=$ROOT"
    if [ -f "$PATHS_FILE" ]; then
      cp -f "$PATHS_FILE" "$ROOT/extra_model_paths.yaml"
    fi
    mkdir -p "$ROOT/user/default/workflows/EPALLE" "$ROOT/models"
    if [ -d "$WF_SRC" ]; then
      find "$WF_SRC" -type f -name '*.json' ! -name '*.ports.json' ! -name manifest.json \
        -exec cp -n '{}' "$ROOT/user/default/workflows/EPALLE/" \; 2>/dev/null || true
    fi
    if [ -d "$MODELS" ]; then
      for dir in "$MODELS"/*; do
        [ -d "$dir" ] || continue
        name=$(basename "$dir")
        dest="$ROOT/models/$name"
        if [ -L "$dest" ]; then
          continue
        fi
        mkdir -p "$dir"
        if [ -d "$dest" ]; then
          # Keep any non-placeholder files that landed in the container disk.
          find "$dest" -mindepth 1 -maxdepth 1 ! -name 'put_*' ! -name '.gitkeep' -exec mv -n '{}' "$dir/" \; || true
          rm -rf "$dest"
        fi
        ln -sfn "$dir" "$dest"
        echo "linked $name"
      done
    fi
    echo "BOUND models + workflows"
    exit 0
  fi
done
echo "COMFY_ROOT_NOT_READY"
exit 2
