#!/usr/bin/env python3
"""Install native MiniMax H3 extras the stock 0.26.2 template does not ship.

Copying nodes_minimax_h3.py alone is not enough: those nodes import
comfy.ldm.minimax and comfy.text_encoders.minimax, which arrive in Comfy
0.33+. On a git checkout of the official image this script fetches tag
v0.33.4 (the range the H3 graphs expect) so the extras actually import.
It does not install extra H3 motion-context forks or comfyui-unsafe-torch.
"""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path
import shutil

SRC = Path("/workspace/epalle/ComfyUI")
DST = Path("/workspace/runpod-slim/ComfyUI")
H3_TAG = "v0.33.4"
COMFY_RAW = f"https://raw.githubusercontent.com/comfyanonymous/ComfyUI/{H3_TAG}/"
KJ_RAW = "https://raw.githubusercontent.com/kijai/ComfyUI-KJNodes/main/"

copies = [
    ("comfy_extras/nodes_minimax_h3.py", "comfy_extras/nodes_minimax_h3.py", COMFY_RAW),
    ("comfy_extras/nodes_minimax_music.py", "comfy_extras/nodes_minimax_music.py", COMFY_RAW),
    (
        "custom_nodes/ComfyUI-KJNodes/nodes/minimax_nodes.py",
        "custom_nodes/ComfyUI-KJNodes/nodes/minimax_nodes.py",
        KJ_RAW,
    ),
]


def fetch(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        if not data or b"404" in data[:80]:
            print("FETCH_EMPTY", url)
            return False
        dest.write_bytes(data)
        print("FETCHED", dest, dest.stat().st_size)
        return True
    except Exception as exc:  # noqa: BLE001
        print("FETCH_FAIL", url, exc)
        return False


def ensure_h3_core() -> None:
    te = DST / "comfy/text_encoders/minimax.py"
    ldm = DST / "comfy/ldm/minimax/model.py"
    if te.is_file() and ldm.is_file():
        print("H3_CORE_PRESENT")
        return
    git_dir = DST / ".git"
    if not git_dir.exists():
        print("H3_CORE_NO_GIT")
        return
    print(f"fetching Comfy {H3_TAG} for MiniMax H3 core")
    code = subprocess.call(["git", "fetch", "origin", f"tag", H3_TAG, "--depth", "1"], cwd=str(DST))
    if code != 0:
        print("H3_TAG_FETCH_FAIL")
        return
    code = subprocess.call(["git", "checkout", "--force", "FETCH_HEAD"], cwd=str(DST))
    print("H3_CHECKOUT", "ok" if code == 0 else "FAIL")


ensure_h3_core()

# ModelAttentionBackend lives in nodes_model_advanced.py — copy only if dest lacks the class.
src_adv = SRC / "comfy_extras/nodes_model_advanced.py"
dst_adv = DST / "comfy_extras/nodes_model_advanced.py"
if src_adv.is_file() and dst_adv.is_file():
    if "class ModelAttentionBackend" not in dst_adv.read_text(errors="replace"):
        copies.append(
            (
                "comfy_extras/nodes_model_advanced.py",
                "comfy_extras/nodes_model_advanced.py",
                COMFY_RAW,
            )
        )

for rel_src, rel_dst, raw_base in copies:
    s, d = SRC / rel_src, DST / rel_dst
    if s.is_file():
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        print("COPIED", rel_dst, d.stat().st_size)
        continue
    url = raw_base + rel_src.replace("custom_nodes/ComfyUI-KJNodes/", "")
    if raw_base == KJ_RAW:
        url = raw_base + "nodes/minimax_nodes.py"
    fetch(url, d)

kj_init = DST / "custom_nodes/ComfyUI-KJNodes/__init__.py"
if kj_init.is_file() and (DST / "custom_nodes/ComfyUI-KJNodes/nodes/minimax_nodes.py").is_file():
    text = kj_init.read_text(encoding="utf-8", errors="replace")
    if "minimax_nodes" not in text:
        print("KJ_INIT_NO_MINIMAX_IMPORT")
    else:
        print("KJ_INIT_HAS_MINIMAX")
print("DONE")
