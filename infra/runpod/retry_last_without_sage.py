#!/usr/bin/env python3
"""Replay the latest failed ComfyUI prompt after removing KJ Sage patch nodes."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8188"
SAGE_TYPES = {"PathchSageAttentionKJ", "PatchSageAttentionKJ"}


def request(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def replace_links(value: object, replacements: dict[str, object]) -> object:
    if isinstance(value, list):
        if len(value) == 2 and str(value[0]) in replacements and isinstance(value[1], int):
            return replacements[str(value[0])]
        return [replace_links(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: replace_links(item, replacements) for key, item in value.items()}
    return value


def main() -> None:
    history = request("/history")
    candidates = []
    for prompt_id, entry in history.items():
        messages = entry.get("status", {}).get("messages", [])
        if any(message[0] == "execution_error" for message in messages):
            candidates.append((entry.get("prompt", [0])[0], prompt_id, entry))
    if not candidates:
        raise SystemExit("No failed prompt found")
    _, old_id, entry = max(candidates)
    graph = entry["prompt"][2]
    replacements: dict[str, object] = {}
    for node_id, node in graph.items():
        if node.get("class_type") in SAGE_TYPES:
            upstream = node.get("inputs", {}).get("model")
            if isinstance(upstream, list) and len(upstream) == 2:
                replacements[str(node_id)] = upstream
            else:
                # UI workflows can leave an unconnected patch node in the API prompt.
                replacements[str(node_id)] = None
    if not replacements:
        raise SystemExit(f"Latest failed prompt {old_id} contains no Sage patch node")
    linked_replacements = {key: value for key, value in replacements.items() if value is not None}
    fixed = replace_links(graph, linked_replacements)
    for node_id in replacements:
        fixed.pop(node_id, None)
    saved = Path("/workspace/epalle/workflows/api-tests/last-failed-pytorch-safe.json")
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text(json.dumps(fixed, indent=2) + "\n")
    result = request("/prompt", {"prompt": fixed})
    new_id = result["prompt_id"]
    print(json.dumps({"source_prompt": old_id, "new_prompt": new_id, "removed_sage_nodes": replacements, "saved": str(saved)}))
    deadline = time.time() + 1800
    while time.time() < deadline:
        state = request(f"/history/{new_id}").get(new_id)
        if state:
            messages = state.get("status", {}).get("messages", [])
            error = next((m[1] for m in messages if m[0] == "execution_error"), None)
            if error:
                print(json.dumps({"status": "error", "error": error}))
                raise SystemExit(2)
            if state.get("status", {}).get("completed"):
                outputs = {node: list(data.keys()) for node, data in state.get("outputs", {}).items()}
                print(json.dumps({"status": "success", "outputs": outputs}))
                return
        time.sleep(5)
    raise SystemExit("Timed out waiting for replay")


if __name__ == "__main__":
    main()
