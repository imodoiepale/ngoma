#!/usr/bin/env python3
"""Install every Director workflow node pack into the official ComfyUI template."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

COMFY = Path("/workspace/runpod-slim/ComfyUI")
PY = COMFY / ".venv-cu128" / "bin" / "python"
CUSTOM = COMFY / "custom_nodes"
PACKS = Path("/workspace/epalle/node-packs")
LOG = Path("/workspace/epalle/logs/install-template-nodes.log")

ENGINE = [
    "Comfy-Org/ComfyUI-Manager",
    "rgthree/rgthree-comfy",
    "Kosinkadink/ComfyUI-VideoHelperSuite",
    "kijai/ComfyUI-KJNodes",
    "kijai/ComfyUI-WanVideoWrapper",
    "kijai/ComfyUI-SCAIL-Pose",
    "ltdrdata/ComfyUI-Impact-Pack",
    "ltdrdata/ComfyUI-Impact-Subpack",
    "ltdrdata/ComfyUI-Inspire-Pack",
    "Suzie1/ComfyUI_Comfyroll_CustomNodes",
    "Fannovel16/comfyui_controlnet_aux",
    "Fannovel16/ComfyUI-Frame-Interpolation",
    "yolain/ComfyUI-Easy-Use",
    "ClownsharkBatwing/RES4LYF",
    "pythongosssss/ComfyUI-Custom-Scripts",
    "facok/comfyui-krea2-controlnet",
    "princepainter/ComfyUI-PainterI2V",
    "FranckyB/ComfyUI-H3RefModPicker",
    "Luisacaotica/ComfyUI-MiniMaxH3Mod",
    "xmarre/ComfyUI-Spectrum-MiniMax-H3",
    "seitanism/ComfyUI-H3-Motion-Context-MultiRef",
    "LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler",
    "matlowai/ComfyUI-MAINodes",
    "drozbay/MaskVidExperiments",
    "Nekodificador/ComfyUI-NKD-Basic-Tools",
    "Nekodificador/ComfyUI-NKD-Sigmas-Curve",
]
LIBRARY = [
    "jags111/efficiency-nodes-comfyui",
    "cubiq/ComfyUI_FaceAnalysis",
    "cubiq/ComfyUI_essentials",
    "theUpsider/ComfyUI-Logic",
    "capitan01R/ComfyUI-Krea2T-Enhancer",
    "DoctorDiffusion/ComfyUI-MediaMixer",
    "Lightricks/ComfyUI-LTXVideo",
    "kijai/ComfyUI-WanAnimatePreprocess",
    "wallen0322/ComfyUI-WanAnimate-Enhancer",
    "Comfy-Org/Nvidia_RTX_Nodes_ComfyUI",
    "pollockjj/ComfyUI-MultiGPU",
    "ssitu/ComfyUI_UltimateSDUpscale",
    "Starnodes2024/ComfyUI_StarNodes",
    "bash-j/mikey_nodes",
    "WASasquatch/was-node-suite-comfyui",
    "PozzettiAndrea/ComfyUI-SAM3",
    "kijai/ComfyUI-SolAttn_triton",
]
ICY = ["icynodes", "ComfyUI-IcyQwen3", "ComfyUI-icyTikTokDownloader"]
REMOVE = [
    "betterimage_loader",
    "ICYLM",
    "icymegapixelresize",
    "ComfyUI-IcyHider-icekiub",
    "comfyui-unsafe-torch",
    "ComfyUI-H3-Motion-Context",
]


def log(msg: str) -> None:
    print(msg, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def existing() -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not CUSTOM.is_dir():
        return found
    for child in CUSTOM.iterdir():
        if child.is_dir():
            found[child.name.lower()] = child
    return found


def have(name: str) -> Path | None:
    return existing().get(name.lower())


def run(cmd: list[str], timeout: int = 600) -> int:
    proc = subprocess.run(cmd, cwd=str(COMFY), timeout=timeout)
    return proc.returncode


def pip_reqs(folder: Path) -> str:
    req = folder / "requirements.txt"
    if not req.is_file():
        return "skip"
    code = run([str(PY), "-m", "pip", "install", "-q", "-r", str(req)])
    return "ok" if code == 0 else "FAIL"


def clone(item: str) -> str:
    name = item.split("/")[-1]
    if have(name):
        dest = have(name)
        log(f"[have] {dest.name}")
        return pip_reqs(dest)
    dest = CUSTOM / name
    url = f"https://github.com/{item}.git"
    log(f"[clone] {item}")
    code = run(["git", "clone", "--recursive", "--depth", "1", url, str(dest)])
    if code != 0:
        log(f"[FAIL] clone {item}")
        return "FAIL"
    return pip_reqs(dest)


def main() -> int:
    if not (COMFY / "main.py").is_file():
        log("COMFY_MISSING")
        return 2
    if not PY.is_file():
        log("VENV_MISSING")
        return 2
    CUSTOM.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

    summary = {"engine_ok": 0, "library_ok": 0, "icy_ok": 0, "fail": []}

    log("=== engine ===")
    for item in ENGINE:
        result = clone(item)
        if result == "FAIL":
            summary["fail"].append(item)
        else:
            summary["engine_ok"] += 1

    log("=== library ===")
    for item in LIBRARY:
        result = clone(item)
        if result == "FAIL":
            summary["fail"].append(item)
        else:
            summary["library_ok"] += 1

    if not have("matrix-power-nodes"):
        log("[clone] imodoiepale/matrix-power-nodes")
        if run(["git", "clone", "--depth", "1",
                "https://github.com/imodoiepale/matrix-power-nodes.git",
                str(CUSTOM / "matrix-power-nodes")]) != 0:
            summary["fail"].append("imodoiepale/matrix-power-nodes")

    log("=== icekiub ===")
    for name in REMOVE:
        path = have(name)
        if path:
            shutil.rmtree(path, ignore_errors=True)
            log(f"[rm] {path.name}")
    for pack in ICY:
        src = PACKS / pack
        dest = have(pack) or (CUSTOM / pack)
        if not src.is_dir():
            log(f"[WARN] staged pack missing: {src}")
            summary["fail"].append(f"staged:{pack}")
            continue
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(src, CUSTOM / pack)
        pip_reqs(CUSTOM / pack)
        summary["icy_ok"] += 1
        log(f"[copy] {pack}")

    log("=== installed now ===")
    for name in sorted(p.name for p in CUSTOM.iterdir() if p.is_dir()):
        log(f"  {name}")
    log(f"SUMMARY engine={summary['engine_ok']}/{len(ENGINE)} "
        f"library={summary['library_ok']}/{len(LIBRARY)} "
        f"icy={summary['icy_ok']}/{len(ICY)} fail={summary['fail']}")
    return 0 if not summary["fail"] else 1


if __name__ == "__main__":
    sys.exit(main())
