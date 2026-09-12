#!/usr/bin/env python3
"""Disable the incompatible KJNodes Sage patch on Torch 2.11+ while preserving UI compatibility."""

from pathlib import Path
import shutil

path = Path("/workspace/epalle/ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/model_optimization_nodes.py")
backup = Path("/workspace/epalle/backups/kjnodes-model_optimization_nodes.py.pre-sage-guard")
source = path.read_text()
needle = "    def patch(self, model, sage_attention, allow_compile=False):\n        if sage_attention == \"disabled\":\n"
replacement = (
    "    def patch(self, model, sage_attention, allow_compile=False):\n"
    "        # EPALLE guard: SageAttention 2.2 fails on torch 2.11 custom-op tensors.\n"
    "        # Keep old/in-memory workflows runnable by passing MODEL through unchanged.\n"
    "        if tuple(int(x) for x in torch.__version__.split('+')[0].split('.')[:2]) >= (2, 11):\n"
    "            logging.warning(\"SageAttention patch bypassed on torch 2.11+; using PyTorch SDPA\")\n"
    "            return model,\n"
    "        if sage_attention == \"disabled\":\n"
)
if replacement in source:
    print("guard already installed")
elif needle not in source:
    raise SystemExit("target method signature not found; no file changed")
else:
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    path.write_text(source.replace(needle, replacement, 1))
    print(f"guard installed; backup={backup}")
