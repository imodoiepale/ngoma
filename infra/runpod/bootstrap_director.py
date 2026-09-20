#!/usr/bin/env python3
"""Bind Director models into the official RunPod ComfyUI template and restart it.

Run this ON the pod. It is the repeatable half of one_click.py:

  1. Write extra_model_paths.yaml next to main.py
  2. Replace ComfyUI/models/<folder> with a symlink to /workspace/epalle/models/<folder>
     so loaders (UpscaleModelLoader, LoraLoader, …) never see an empty [] while the
     file already exists on the volume
  3. Copy workflows into the template user directory
  4. Optionally install node packs and resume planned downloads
  5. Restart Comfy so path changes are actually loaded (Refresh in the UI is not enough)

Usage:
    python bootstrap_director.py              # bind + restart
    python bootstrap_director.py --full       # also nodes, H3 extras, priority downloads
    python bootstrap_director.py --full --download-all   # resume the entire plan
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

EPALLE = Path("/workspace/epalle")
MODELS = EPALLE / "models"
LOG_DIR = EPALLE / "logs"
COMFY_CANDIDATES = [
    Path("/workspace/runpod-slim/ComfyUI"),
    Path("/workspace/madapps/ComfyUI"),
    Path("/workspace/ComfyUI"),
    EPALLE / "ComfyUI",
]
# Every folder workflows actually load from. extra_model_paths + a real symlink.
MODEL_FOLDERS = [
    "checkpoints",
    "configs",
    "loras",
    "vae",
    "text_encoders",
    "diffusion_models",
    "unet",
    "clip",
    "clip_vision",
    "style_models",
    "embeddings",
    "diffusers",
    "vae_approx",
    "controlnet",
    "gligen",
    "upscale_models",
    "latent_upscale_models",
    "hypernetworks",
    "photomaker",
    "classifiers",
    "model_patches",
    "audio_encoders",
    "detection",
    "rife",
    "insightface",
    "ultralytics",
    "sams",
    "ipadapter",
    "animatediff_models",
    "animatediff_motion_lora",
    "onnx",
]
PLACEHOLDERS = {"put_checkpoints_here", "put_loras_here", "put_vae_here", ".gitkeep"}
MIN_FREE_GB_FOR_DOWNLOADS = 30
PRIORITY_DOWNLOADS = [
    "minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors",
    "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "1xSkinContrast-SuperUltraCompact.pth",
    "minimax_h3_t1_image_vae_step1597.safetensors",
    "minimax_h3_ref2va_pruned_fp8_scaled.safetensors",
    "flux-2-klein-9b-fp8.safetensors",
    "QuadView_klein9b_v1.safetensors",
    "4xNomosWebPhoto_RealPLKSR.safetensors",
]


def log(msg: str) -> None:
    print(msg, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "bootstrap-director.log").open("a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def find_comfy() -> Path:
    for root in COMFY_CANDIDATES:
        if (root / "main.py").is_file():
            return root
    raise SystemExit("COMFY_ROOT_NOT_READY")


def comfy_python(root: Path) -> Path:
    for candidate in (
        root / ".venv-cu128" / "bin" / "python",
        root / "venv" / "bin" / "python",
        EPALLE / "venv" / "bin" / "python",
        Path(sys.executable),
    ):
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def write_extra_paths(root: Path) -> Path:
    src = EPALLE / "extra_model_paths.yaml"
    dest = root / "extra_model_paths.yaml"
    if src.is_file():
        shutil.copy2(src, dest)
    else:
        dest.write_text(src.read_text(encoding="utf-8") if src.exists() else "", encoding="utf-8")
    log(f"extra_model_paths -> {dest}")
    return dest


def _is_placeholder(path: Path) -> bool:
    return path.name in PLACEHOLDERS or path.name.startswith("put_")


def bind_folder(name: str, comfy_models: Path) -> str:
    src = MODELS / name
    src.mkdir(parents=True, exist_ok=True)
    dest = comfy_models / name
    if dest.is_symlink():
        current = Path(os.readlink(dest))
        if current == src:
            return "ok"
        dest.unlink()
    elif dest.is_dir():
        for item in dest.iterdir():
            if _is_placeholder(item):
                continue
            target = src / item.name
            if not target.exists():
                shutil.move(str(item), str(target))
        shutil.rmtree(dest)
    elif dest.exists():
        dest.unlink()
    dest.symlink_to(src)
    return "linked"


def bind_models(root: Path) -> None:
    comfy_models = root / "models"
    comfy_models.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    extra = sorted({p.name for p in MODELS.iterdir() if p.is_dir()} | set(MODEL_FOLDERS))
    for name in extra:
        if name.startswith("."):
            continue
        status = bind_folder(name, comfy_models)
        log(f"bind {name}: {status}")


def copy_workflows(root: Path) -> None:
    dest = root / "user" / "default" / "workflows" / "EPALLE"
    dest.mkdir(parents=True, exist_ok=True)
    src = EPALLE / "workflows"
    if not src.is_dir():
        return
    count = 0
    for path in src.rglob("*.json"):
        if path.name.endswith(".ports.json") or path.name == "manifest.json":
            continue
        target = dest / path.name
        if not target.exists():
            shutil.copy2(path, target)
        count += 1
    log(f"workflows copied: {count} -> {dest}")


def volume_free_gb(path: Path | str = "/workspace") -> float | None:
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    return (st.f_bavail * st.f_frsize) / (1024 ** 3)


def kill_downloaders() -> None:
    if not shutil.which("pkill"):
        return
    for pattern in (
        "download_planned.py",
        "huggingface-cli",
        "huggingface_hub",
        "hf_transfer",
    ):
        subprocess.call(
            ["pkill", "-f", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def rotate_logs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for name in (
        "comfy-template.log",
        "bootstrap-director.log",
        "download-planned.log",
        "install-template-nodes.log",
    ):
        path = LOG_DIR / name
        if path.is_file() and path.stat().st_size > 20 * 1024 * 1024:
            path.write_text("", encoding="utf-8")
            log(f"truncated {path}")


def copy_h3_extras() -> None:
    for script in ("copy-h3-extras.py", "patch-kj-minimax.py"):
        path = EPALLE / script
        if not path.is_file():
            log(f"skip {script}: not on volume")
            continue
        log(f"running {script}")
        subprocess.call([sys.executable, str(path)])


def restart_comfy(root: Path) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "comfy-template.log"
    py = comfy_python(root)
    # Official template may be under supervisord; fall back to a direct listen.
    if shutil.which("supervisorctl"):
        subprocess.call(
            ["supervisorctl", "restart", "comfyui"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    for pattern in (
        f"{root}/.venv-cu128/bin/python main.py",
        f"{root}/venv/bin/python main.py",
        "python main.py --listen",
    ):
        if shutil.which("pkill"):
            subprocess.call(
                ["pkill", "-f", pattern],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    time.sleep(3)
    env = os.environ.copy()
    cmd = [
        str(py),
        "main.py",
        "--listen",
        "0.0.0.0",
        "--port",
        "8188",
        "--enable-cors-header",
    ]
    with log_path.open("a", encoding="utf-8") as fh:
        subprocess.Popen(cmd, cwd=str(root), stdout=fh, stderr=subprocess.STDOUT, env=env)
    log(f"restarted Comfy with {py}")
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            import urllib.request

            urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3)
            log("COMFY_UP")
            return
        except Exception:
            time.sleep(3)
    log("COMFY_DOWN after restart")


def verify_upscale() -> None:
    try:
        import json
        import urllib.request

        raw = urllib.request.urlopen("http://127.0.0.1:8188/object_info/UpscaleModelLoader", timeout=10).read()
        info = json.loads(raw)
        widget = (
            info.get("UpscaleModelLoader", {})
            .get("input", {})
            .get("required", {})
            .get("model_name")
        )
        names = []
        if isinstance(widget, list) and widget:
            if isinstance(widget[0], list):
                names = widget[0]
            elif widget[0] == "COMBO" and isinstance(widget[1], dict):
                names = widget[1].get("options") or []
        log(f"upscale_models listed: {names}")
        wanted = "4xNomosWebPhoto_RealPLKSR.safetensors"
        if wanted in names:
            log(f"OK {wanted}")
        else:
            disk = sorted(p.name for p in (MODELS / "upscale_models").glob("*") if p.is_file())
            log(f"MISSING in loader, on disk: {disk}")
    except Exception as exc:  # noqa: BLE001
        log(f"verify_upscale failed: {exc}")


def install_nodes() -> None:
    script = EPALLE / "install-template-nodes.py"
    if not script.is_file():
        log("skip nodes: install-template-nodes.py not on volume")
        return
    log("installing node packs")
    subprocess.call([sys.executable, str(script)])


def inherit_pid1_token() -> bool:
    """Copy HF_TOKEN from the container supervisor without printing it."""
    try:
        raw = Path("/proc/1/environ").read_bytes().split(b"\0")
    except OSError:
        return False
    for entry in raw:
        if entry.startswith(b"HF_TOKEN=") or entry.startswith(b"HUGGING_FACE_HUB_TOKEN="):
            value = entry.split(b"=", 1)[1].decode()
            if value:
                os.environ["HF_TOKEN"] = value
                os.environ["HUGGING_FACE_HUB_TOKEN"] = value
                return True
    return False


def start_downloads(download_all: bool) -> None:
    kill_downloaders()
    free = volume_free_gb()
    if free is not None:
        log(f"workspace free: {free:.1f} GB")
        if free < MIN_FREE_GB_FOR_DOWNLOADS:
            log(f"skip downloads: quota tight ({free:.1f} GB free, need {MIN_FREE_GB_FOR_DOWNLOADS})")
            return
    script = EPALLE / "download_planned.py"
    plan = EPALLE / "download-plan.json"
    if not script.is_file() or not plan.is_file():
        log("skip downloads: plan or downloader missing")
        return
    os.environ["EPALLE_MODELS"] = str(MODELS)
    os.environ["EPALLE_HF_CACHE"] = str(EPALLE / "cache" / "huggingface")
    log(f"HF_TOKEN from pid1: {'yes' if inherit_pid1_token() else 'no'}")
    py = Path("/workspace/runpod-slim/ComfyUI/.venv-cu128/bin/python")
    if not py.is_file():
        py = Path(sys.executable)
    cmd = [str(py), str(script), "--plan", str(plan)]
    if not download_all:
        cmd.extend(["--only", *PRIORITY_DOWNLOADS])
        log("starting priority downloads (not the full plan)")
    else:
        log("starting full planned downloads")
    log_path = LOG_DIR / "download-planned.log"
    log(f"starting downloads with {py}")
    with log_path.open("a", encoding="utf-8") as fh:
        subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=os.environ)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="also install nodes, H3 extras, priority downloads")
    parser.add_argument("--download-all", action="store_true", help="resume the entire download plan")
    parser.add_argument("--no-restart", action="store_true")
    args = parser.parse_args()

    kill_downloaders()
    rotate_logs()
    root = find_comfy()
    log(f"COMFY_ROOT={root}")
    write_extra_paths(root)
    bind_models(root)
    copy_workflows(root)
    if args.full:
        install_nodes()
        copy_h3_extras()
        start_downloads(download_all=args.download_all)
    if not args.no_restart:
        restart_comfy(root)
        verify_upscale()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
