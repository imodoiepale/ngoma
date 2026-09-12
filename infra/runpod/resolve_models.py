#!/usr/bin/env python3
"""Resolve missing model filenames to concrete Hugging Face repo + path.

Reads model-gap-report.json, lists the file tree of every known upstream repo, and
matches each missing filename against those trees. Produces a download manifest for
what is resolvable and an explicit "cannot resolve" list for what is not, so nothing
gets silently substituted with a different file.

Usage:
    python resolve_models.py                      # resolve and write download-plan.json
    python resolve_models.py --show-unresolved    # only print what cannot be found
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from runpod_api import USER_AGENT

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
GAP_REPORT = HERE / "model-gap-report.json"
PLAN_PATH = HERE / "download-plan.json"

# Every upstream repo these workflows draw from.
REPOS = [
    "Comfy-Org/MiniMax-H3",
    "Kijai/MiniMax-H3-experimental",
    "Comfy-Org/SCAIL-2",
    "Comfy-Org/sam3.1",
    "Comfy-Org/flux2-klein-9B",
    "Kijai/WanVideo_comfy_fp8_scaled",
    "Kijai/WanVideo_comfy",
    "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
    "lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v",
    "Wan-AI/Wan2.2-Animate-14B",
    "Kijai/vitpose_comfy",
    "black-forest-labs/FLUX.2-klein-9b-fp8",
    "black-forest-labs/FLUX.2-klein-9b-kv",
    "yzd-v/DWPose",
    "hr16/yolox-onnx",
    "hr16/DWPose-TorchScript-BatchSize5",
    "styler00dollar/VSGAN-tensorrt-docker",
    "AlexWortega/RIFE",
]

# Models fetched automatically by their node at first use. Worth pre-fetching to avoid
# a stall mid-render, but not a blocking gap.
AUTO_DOWNLOAD = {
    "dw-ll_ucoco_384_bs5.torchscript.pt",
    "yolox_l.torchscript.pt",
    "rife47.pth",
    "model.onnx",
}

# Referenced by a workflow but with no dependable public source. These are the original
# creator's own trained LoRAs. Never silently substitute a different file.
CREATOR_PRIVATE = {
    "my_first_lora_v1_000000600_low_noise.safetensors",
    "Lora_lora_000000600.safetensors",
    "slop_twerk_LowNoise_merged3_7_v2.safetensors",
    "wan2.1_SCAIL_2_DPO_lora_bf16(1).safetensors",
}


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


def hf_token() -> str | None:
    token = _secret("HF_TOKEN")
    return token.strip() if token else None


def list_repo(repo: str, token: str | None) -> list[str]:
    url = f"https://huggingface.co/api/models/{repo}?full=true"
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return [f"__ERROR__ HTTP {exc.code}"]
    except Exception as exc:  # noqa: BLE001
        return [f"__ERROR__ {exc}"]
    return [entry["rfilename"] for entry in payload.get("siblings", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-unresolved", action="store_true")
    args = parser.parse_args()

    if not GAP_REPORT.exists():
        print(f"error: run audit_models.py first ({GAP_REPORT} missing)", file=sys.stderr)
        return 2

    gap = json.loads(GAP_REPORT.read_text(encoding="utf-8"))
    missing = gap["missing"]
    token = hf_token()
    print(f"HF token: {'loaded' if token else 'NOT AVAILABLE (gated repos will fail)'}\n")

    # filename -> [(repo, path)]
    index: dict[str, list[tuple[str, str]]] = {}
    repo_errors = {}
    for repo in REPOS:
        files = list_repo(repo, token)
        if files and files[0].startswith("__ERROR__"):
            repo_errors[repo] = files[0].replace("__ERROR__ ", "")
            print(f"  {repo:<58} {repo_errors[repo]}")
            continue
        print(f"  {repo:<58} {len(files)} files")
        for path in files:
            index.setdefault(Path(path).name, []).append((repo, path))

    resolved, unresolved, auto, private = [], [], [], []
    for entry in missing:
        name = entry["file"]
        folder = next((f for f in entry["expected_folder"] if f != "unknown"),
                      entry["expected_folder"][0])
        record = {
            "file": name,
            "folder": folder,
            "workflow_count": entry["workflow_count"],
            "used_by": entry["used_by"],
        }
        if name in CREATOR_PRIVATE:
            private.append(record)
            continue
        matches = index.get(name)
        if matches:
            repo, path = matches[0]
            record["repo"] = repo
            record["repo_path"] = path
            record["all_matches"] = matches
            resolved.append(record)
        elif name in AUTO_DOWNLOAD:
            auto.append(record)
        else:
            unresolved.append(record)

    print(f"\n{'='*76}")
    print(f"RESOLVED {len(resolved)}   AUTO-DOWNLOAD {len(auto)}   "
          f"CREATOR-PRIVATE {len(private)}   UNRESOLVED {len(unresolved)}")
    print("=" * 76)

    if resolved and not args.show_unresolved:
        print("\nDOWNLOADABLE")
        for record in sorted(resolved, key=lambda r: -r["workflow_count"]):
            print(f"  {record['file']}")
            print(f"      -> models/{record['folder']}/  from {record['repo']}")
    if auto and not args.show_unresolved:
        print("\nAUTO-DOWNLOADED BY THE NODE AT FIRST USE (not a blocking gap)")
        for record in auto:
            print(f"  {record['file']}  ({record['workflow_count']} wf)")
    if private:
        print("\nCREATOR-PRIVATE - no public source, do not substitute")
        for record in private:
            print(f"  {record['file']}  ({record['workflow_count']} wf)")
    if unresolved:
        print("\nUNRESOLVED - not found in any known repo")
        for record in sorted(unresolved, key=lambda r: -r["workflow_count"]):
            print(f"  {record['file']}  ({record['workflow_count']} wf) "
                  f"-> models/{record['folder']}/")

    PLAN_PATH.write_text(
        json.dumps(
            {"resolved": resolved, "auto_download": auto,
             "creator_private": private, "unresolved": unresolved,
             "repo_errors": repo_errors},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {PLAN_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
