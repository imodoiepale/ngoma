#!/usr/bin/env python3
"""Audit model coverage: what every workflow asks for vs what is on the volume.

Walks every workflow JSON, extracts each model filename it references along with the
node type that references it, maps that node type to the ComfyUI model folder the file
must live in, then diffs against the actual inventory on the pod.

Answers "have we downloaded everything, into the right folders" with evidence instead
of assumption.

Usage:
    python audit_models.py --inventory pod-inventory.txt
    python audit_models.py --inventory pod-inventory.txt --json gap-report.json

Produce the inventory on the pod with:
    find /workspace/epalle/ComfyUI/models -type f -printf '%s\t%P\n'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKFLOW_DIR = HERE.parent / "libraries" / "workflows"

MODEL_SUFFIXES = (
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".onnx", ".gguf", ".sft", ".engine",
)

# Node class (or class substring) -> ComfyUI models/ subfolder.
NODE_FOLDER = {
    "CheckpointLoader": "checkpoints",
    "CheckpointLoaderSimple": "checkpoints",
    "ImageOnlyCheckpointLoader": "checkpoints",
    "unCLIPCheckpointLoader": "checkpoints",
    "VAELoader": "vae",
    "LoraLoader": "loras",
    "LoraLoaderModelOnly": "loras",
    "LoraModelLoader": "loras",
    "WanVideoLoraSelect": "loras",
    "UNETLoader": "diffusion_models",
    "UnetLoaderGGUF": "diffusion_models",
    "WanVideoModelLoader": "diffusion_models",
    "CLIPLoader": "text_encoders",
    "DualCLIPLoader": "text_encoders",
    "TripleCLIPLoader": "text_encoders",
    "CLIPLoaderGGUF": "text_encoders",
    "WanVideoTextEncode": "text_encoders",
    "LoadWanVideoT5TextEncoder": "text_encoders",
    "CLIPVisionLoader": "clip_vision",
    "LoadWanVideoClipTextEncoder": "clip_vision",
    "ControlNetLoader": "controlnet",
    "DiffControlNetLoader": "controlnet",
    "UpscaleModelLoader": "upscale_models",
    "SAMLoader": "sams",
    "Sam3Loader": "checkpoints",
    "SAM3": "checkpoints",
    "StyleModelLoader": "style_models",
    "GLIGENLoader": "gligen",
    "PhotoMakerLoader": "photomaker",
    "WanVideoVAELoader": "vae",
    "DownloadAndLoadFlorence2Model": "LLM",
    "RIFE": "rife",
    "InstantIDModelLoader": "instantid",
}

# Fallback by filename shape when the node class is unknown.
NAME_HINTS = [
    (re.compile(r"vae", re.I), "vae"),
    (re.compile(r"lora|_lora_|lightx2v", re.I), "loras"),
    (re.compile(r"clip_vision|clip-vit", re.I), "clip_vision"),
    (re.compile(r"umt5|t5xxl|qwen.*encoder|text_encoder|clip_l|clip_g", re.I),
     "text_encoders"),
    (re.compile(r"controlnet|control_", re.I), "controlnet"),
    (re.compile(r"upscal|esrgan|realesr", re.I), "upscale_models"),
    (re.compile(r"yolo|vitpose|sam\d|segment", re.I), "detection"),
    (re.compile(r"diffusion|unet|wan2|scail|minimax|flux|klein", re.I),
     "diffusion_models"),
]


def looks_like_model(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 300:
        return False
    lowered = value.lower().strip()
    if not lowered.endswith(MODEL_SUFFIXES):
        return False
    # Skip URLs and obvious prose.
    return not lowered.startswith(("http://", "https://"))


def folder_for(node_type: str, filename: str) -> str:
    for key, folder in NODE_FOLDER.items():
        if key.lower() in (node_type or "").lower():
            return folder
    for pattern, folder in NAME_HINTS:
        if pattern.search(filename):
            return folder
    return "unknown"


def extract(graph: dict) -> list[tuple[str, str]]:
    """Return (node_type, model_filename) pairs from a UI-format or API-format graph."""
    found: list[tuple[str, str]] = []

    def scan(value, node_type: str):
        if isinstance(value, str):
            if looks_like_model(value):
                found.append((node_type, value.strip()))
        elif isinstance(value, list):
            for item in value:
                scan(item, node_type)
        elif isinstance(value, dict):
            for item in value.values():
                scan(item, node_type)

    # UI format: {"nodes": [{"type": ..., "widgets_values": [...]}]}
    for node in graph.get("nodes") or []:
        if isinstance(node, dict):
            scan(node.get("widgets_values"), node.get("type") or "")
            scan(node.get("properties", {}).get("models"), node.get("type") or "")

    # API format: {"3": {"class_type": ..., "inputs": {...}}}
    for key, node in graph.items():
        if isinstance(node, dict) and "class_type" in node:
            scan(node.get("inputs"), node.get("class_type") or "")

    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True,
                        help="file of '<bytes>\\t<relpath>' lines from the pod")
    parser.add_argument("--json", help="write the full gap report here")
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    if not inventory_path.exists():
        print(f"error: {inventory_path} not found", file=sys.stderr)
        return 2

    present_by_name: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for line in inventory_path.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        size, rel = line.split("\t", 1)
        rel = rel.strip().replace("\\", "/")
        if not rel:
            continue
        try:
            present_by_name[Path(rel).name].append((int(size), rel))
        except ValueError:
            continue

    # workflow -> required (node_type, filename)
    required: dict[str, set[tuple[str, str]]] = defaultdict(set)
    parse_failures = []
    for path in sorted(WORKFLOW_DIR.rglob("*.json")):
        try:
            graph = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            parse_failures.append(f"{path.name}: {exc}")
            continue
        if not isinstance(graph, dict):
            continue
        rel = path.relative_to(WORKFLOW_DIR).as_posix()
        for node_type, filename in extract(graph):
            required[rel].add((node_type, filename))

    # Aggregate per model file.
    models: dict[str, dict] = {}
    for workflow, entries in required.items():
        for node_type, filename in entries:
            base = Path(filename.replace("\\", "/")).name
            record = models.setdefault(
                base,
                {"filename": filename, "folders": set(), "node_types": set(),
                 "workflows": set()},
            )
            record["folders"].add(folder_for(node_type, base))
            record["node_types"].add(node_type or "?")
            record["workflows"].add(workflow)

    have, missing = [], []
    for base, record in sorted(models.items()):
        matches = present_by_name.get(base)
        entry = {
            "file": base,
            "expected_folder": sorted(record["folders"]),
            "node_types": sorted(record["node_types"]),
            "used_by": sorted(record["workflows"]),
            "workflow_count": len(record["workflows"]),
        }
        if matches:
            entry["on_volume"] = [
                {"path": rel, "bytes": size, "gb": round(size / 1073741824, 2)}
                for size, rel in matches
            ]
            # Flag a file that exists but sits somewhere unexpected.
            actual_dirs = {Path(rel).parent.as_posix().split("/")[0] for _, rel in matches}
            expected = set(entry["expected_folder"]) - {"unknown"}
            entry["folder_ok"] = (not expected) or bool(actual_dirs & expected)
            have.append(entry)
        else:
            missing.append(entry)

    print("=" * 78)
    print(f"MODEL COVERAGE AUDIT  ({len(models)} distinct model files referenced by "
          f"{len(required)} workflows)")
    print("=" * 78)
    print(f"\nPRESENT: {len(have)}     MISSING: {len(missing)}\n")

    if missing:
        print("-" * 78)
        print("MISSING - referenced by a workflow but not on the volume")
        print("-" * 78)
        for entry in sorted(missing, key=lambda e: -e["workflow_count"]):
            print(f"\n  {entry['file']}")
            print(f"    goes in : models/{'|'.join(entry['expected_folder'])}/")
            print(f"    loader  : {', '.join(entry['node_types'][:3])}")
            print(f"    used by : {entry['workflow_count']} workflow(s)")
            for workflow in entry["used_by"][:4]:
                print(f"              {workflow}")

    misplaced = [e for e in have if not e.get("folder_ok")]
    if misplaced:
        print("\n" + "-" * 78)
        print("PRESENT BUT IN AN UNEXPECTED FOLDER")
        print("-" * 78)
        for entry in misplaced:
            print(f"  {entry['file']}")
            print(f"    expected models/{'|'.join(entry['expected_folder'])}/")
            for location in entry["on_volume"]:
                print(f"    actual   models/{location['path']}")

    print("\n" + "-" * 78)
    print("PRESENT")
    print("-" * 78)
    for entry in sorted(have, key=lambda e: -e["workflow_count"]):
        location = entry["on_volume"][0]
        print(f"  {location['gb']:>6.2f} GB  {location['path']:<62} "
              f"({entry['workflow_count']} wf)")

    if parse_failures:
        print("\nWorkflows that could not be parsed:")
        for failure in parse_failures:
            print(f"  {failure}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {"present": have, "missing": missing, "misplaced": misplaced,
                 "parse_failures": parse_failures},
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
