#!/usr/bin/env python3
"""Bypass KJNodes SageAttention patches in ComfyUI UI workflow JSON files."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SAGE_TYPES = {"PathchSageAttentionKJ", "PatchSageAttentionKJ"}


def patch_value(value: object) -> int:
    changed = 0
    if isinstance(value, dict):
        if value.get("type") in SAGE_TYPES and value.get("mode") != 4:
            value["mode"] = 4  # ComfyUI bypass mode; MODEL input passes to output.
            changed += 1
        for child in value.values():
            changed += patch_value(child)
    elif isinstance(value, list):
        for child in value:
            changed += patch_value(child)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--backup-root", type=Path, required=True)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup_root / f"sage-workflows-{stamp}"
    files_changed = nodes_changed = 0
    for root in args.roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.json")
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            count = patch_value(data)
            if not count:
                continue
            try:
                relative = path.relative_to(root)
            except ValueError:
                relative = Path(path.name)
            destination = backup / root.name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
            print(f"patched {count}: {path}")
            files_changed += 1
            nodes_changed += count
    print(f"files_changed={files_changed} nodes_bypassed={nodes_changed} backup={backup}")


if __name__ == "__main__":
    main()
