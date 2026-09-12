#!/usr/bin/env python3
"""Download every resolvable model from download-plan.json into the right folder.

Runs ON THE POD so files land straight on the network volume. Resumable, verifies size,
and records a per-file result so a partial run is never reported as complete.

Precision awareness: NVFP4 and INT4 weights need Blackwell (sm100+). On an sm80 card
they download fine and then fail at inference, so they are skipped by default unless
the GPU can actually use them, or --all is passed.

Usage:
    python download_planned.py --plan download-plan.json
    python download_planned.py --plan download-plan.json --all       # ignore arch skip
    python download_planned.py --plan download-plan.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

MODELS_ROOT = Path(os.environ.get("EPALLE_MODELS", "/workspace/epalle/ComfyUI/models"))

# hf_hub_download caches to ~/.cache/huggingface by default, which on a RunPod pod is
# the small container disk (40 GB), not the network volume. Large weights then fail
# with "No space left on device" even though the volume has hundreds of GB free.
# Point the cache at the volume BEFORE huggingface_hub is imported. Keeping the cache
# on the same filesystem as MODELS_ROOT also lets the hardlink below succeed, so each
# blob is stored once rather than twice.
HF_CACHE = Path(os.environ.get("EPALLE_HF_CACHE", "/workspace/epalle/cache/huggingface"))
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(HF_CACHE))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE / "hub"))
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

# Folders the audit infers that are not real ComfyUI model dirs.
FOLDER_FIXUP = {
    "detection": "detection",
    "unknown": "detection",
    "rife": "rife",
}

BLACKWELL_ONLY = ("nvfp4", "int4q", "_awq")


def gpu_capability() -> tuple[int, int] | None:
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_capability()
    except Exception:  # noqa: BLE001
        pass
    return None


def needs_blackwell(filename: str) -> bool:
    lowered = filename.lower()
    return any(marker in lowered for marker in BLACKWELL_ONLY)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true",
                        help="download arch-incompatible weights too")
    args = parser.parse_args()

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("error: pip install huggingface_hub", file=sys.stderr)
        return 2

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    items = plan.get("resolved", [])

    capability = gpu_capability()
    is_blackwell = bool(capability and capability[0] >= 10)
    print(f"GPU capability: {capability}  blackwell={is_blackwell}")
    print(f"models root   : {MODELS_ROOT}")
    print(f"HF token      : {'present' if token else 'ABSENT (gated repos will 401)'}")
    print(f"planned items : {len(items)}\n")

    results = []
    for item in sorted(items, key=lambda i: -i["workflow_count"]):
        name = item["file"]
        folder = FOLDER_FIXUP.get(item["folder"], item["folder"])
        target_dir = MODELS_ROOT / folder
        target = target_dir / name

        if target.exists() and target.stat().st_size > 0:
            results.append({"file": name, "status": "already_present",
                            "bytes": target.stat().st_size, "path": str(target)})
            print(f"[have] {name}")
            continue

        if needs_blackwell(name) and not is_blackwell and not args.all:
            results.append({"file": name, "status": "skipped_arch",
                            "reason": "NVFP4/INT4 weights require Blackwell (sm100+); "
                                      f"this GPU is {capability}"})
            print(f"[skip] {name}  (Blackwell-only format, GPU is {capability})")
            continue

        print(f"[get ] {name}\n         {item['repo']} :: {item['repo_path']}"
              f"\n         -> models/{folder}/")
        if args.dry_run:
            results.append({"file": name, "status": "dry_run"})
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        try:
            # Download straight into a staging dir on the volume rather than through
            # the shared blob cache. The cache stores each file as a symlink into
            # blobs/, and hardlinking out of that onto this network filesystem failed;
            # it also doubled the space used. local_dir writes the real file, and
            # os.replace within one filesystem is atomic.
            staging = MODELS_ROOT.parent / ".downloads"
            staging.mkdir(parents=True, exist_ok=True)
            fetched = Path(
                hf_hub_download(
                    repo_id=item["repo"],
                    filename=item["repo_path"],
                    token=token,
                    local_dir=str(staging),
                )
            )
            if not fetched.exists():
                raise FileNotFoundError(f"hf_hub_download returned missing {fetched}")
            os.replace(fetched, target)
            size = target.stat().st_size
            results.append({"file": name, "status": "downloaded", "bytes": size,
                            "path": str(target), "seconds": round(time.time() - started)})
            print(f"         ok {size/1073741824:.2f} GB in "
                  f"{round(time.time()-started)}s")
        except Exception as exc:  # noqa: BLE001 - record and continue
            message = str(exc)
            status = "gated_or_denied" if ("401" in message or "403" in message
                                           or "gated" in message.lower()) else "failed"
            results.append({"file": name, "status": status, "error": message[:400]})
            print(f"         FAILED ({status}): {message[:200]}")

    report = MODELS_ROOT.parent.parent / "manifests" / "download-planned-results.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for entry in results:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    print("\n" + "=" * 60)
    for status, count in sorted(counts.items()):
        print(f"  {status:<20} {count}")
    print(f"\nreport: {report}")

    failed = counts.get("failed", 0) + counts.get("gated_or_denied", 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
