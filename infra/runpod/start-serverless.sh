#!/usr/bin/env bash
set -euo pipefail
export EPALLE_ROOT=/runpod-volume/epalle
mkdir -p /workspace
if [ ! -e /workspace/epalle ]; then ln -s "$EPALLE_ROOT" /workspace/epalle; fi
exec "$EPALLE_ROOT/venv/bin/python" "$EPALLE_ROOT/handler.py"
