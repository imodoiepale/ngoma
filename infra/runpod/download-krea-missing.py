#!/usr/bin/env python3
"""Download the four files Comfy reports missing for the Klein+Krea dataset graph."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("EPALLE_MODELS", "/workspace/epalle/models")
os.environ.setdefault("EPALLE_HF_CACHE", "/workspace/epalle/cache/huggingface")
HF_CACHE = Path(os.environ["EPALLE_HF_CACHE"])
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(HF_CACHE))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE / "hub"))

ROOT = Path(os.environ["EPALLE_MODELS"])

JOBS = [
    ("Comfy-Org/Krea-2", "diffusion_models/krea2_turbo_fp8_scaled.safetensors",
     ROOT / "diffusion_models" / "krea2_turbo_fp8_scaled.safetensors"),
    ("Comfy-Org/Krea-2", "text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
     ROOT / "text_encoders" / "qwen3vl_4b_fp8_scaled.safetensors"),
    ("wikeeyang/Krea2-Turbo-HD-V1", "Krea2-HD-vae.safetensors",
     ROOT / "vae" / "Krea2-HD-vae.safetensors"),
    ("honmamon/krea2", "Krea2-HD-vae.safetensors",
     ROOT / "vae" / "Krea2-HD-vae.safetensors"),
]


def token() -> str | None:
    t = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if t:
        return t
    try:
        raw = Path("/proc/1/environ").read_bytes().split(b"\0")
    except OSError:
        return None
    for item in raw:
        if item.startswith(b"HF_TOKEN="):
            return item.split(b"=", 1)[1].decode()
    return None


def main() -> int:
    from huggingface_hub import hf_hub_download
    tok = token()
    failed = []
    for repo, repo_path, dest in JOBS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and dest.stat().st_size > 1_000_000:
            print(f"[have] {dest} ({dest.stat().st_size} bytes)")
            continue
        print(f"[get ] {dest.name}  {repo} :: {repo_path}")
        try:
            staging = ROOT.parent / ".downloads"
            staging.mkdir(parents=True, exist_ok=True)
            fetched = Path(hf_hub_download(
                repo_id=repo, filename=repo_path, token=tok, local_dir=str(staging),
                repo_type="dataset" if repo.startswith("honmamon/") else None,
            ))
            if not fetched.exists():
                raise FileNotFoundError(f"hf_hub_download returned missing {fetched}")
            os.replace(fetched, dest)
            print(f"       ok {dest.stat().st_size} bytes")
        except Exception as exc:  # noqa: BLE001
            print(f"       FAIL {exc}")
            failed.append(dest.name)

    # Nomos upscaler is a GitHub release, not Hugging Face.
    nomos = ROOT / "upscale_models" / "4xNomosWebPhoto_RealPLKSR.safetensors"
    nomos.parent.mkdir(parents=True, exist_ok=True)
    if nomos.is_file() and nomos.stat().st_size > 1_000_000:
        print(f"[have] {nomos}")
    else:
        url = ("https://github.com/Phhofm/models/releases/download/"
               "4xNomosWebPhoto_RealPLKSR/4xNomosWebPhoto_RealPLKSR.safetensors")
        print(f"[get ] {nomos.name}  {url}")
        import urllib.request
        try:
            urllib.request.urlretrieve(url, nomos)
            print(f"       ok {nomos.stat().st_size} bytes")
        except Exception as exc:  # noqa: BLE001
            print(f"       FAIL {exc}")
            failed.append(nomos.name)

    print("FAILED" if failed else "ALL_OK", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
