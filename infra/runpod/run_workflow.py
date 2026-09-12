#!/usr/bin/env python3
"""Submit an API-format workflow to ComfyUI, poll to completion, report the outputs.

Runs on the pod. Gives a real pass/fail with evidence -- queued is not success, and a
prompt that validates but produces no image is reported as a failure, not a pass.

Usage:
    python run_workflow.py graph.json
    python run_workflow.py graph.json --timeout 900
    python run_workflow.py graph.json --host 127.0.0.1:8188
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def post(host: str, path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"http://{host}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def get(host: str, path: str) -> dict:
    with urllib.request.urlopen(f"http://{host}{path}", timeout=120) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph")
    parser.add_argument("--host", default="127.0.0.1:8188")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    client_id = str(uuid.uuid4())

    print(f"submitting {Path(args.graph).name} ({len(graph)} nodes) to {args.host}")
    try:
        result = post(args.host, "/prompt", {"prompt": graph, "client_id": client_id})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"REJECTED at validation (HTTP {exc.code}):", file=sys.stderr)
        try:
            detail = json.loads(body)
            print(json.dumps(detail, indent=2)[:3000], file=sys.stderr)
        except json.JSONDecodeError:
            print(body[:2000], file=sys.stderr)
        return 2

    prompt_id = result.get("prompt_id")
    if not prompt_id:
        print(f"no prompt_id returned: {result}", file=sys.stderr)
        return 2
    print(f"accepted, prompt_id={prompt_id}")

    started = time.time()
    last_note = ""
    while time.time() - started < args.timeout:
        history = get(args.host, f"/history/{prompt_id}")
        entry = history.get(prompt_id)
        if entry:
            status = entry.get("status") or {}
            completed = status.get("completed")
            messages = status.get("messages") or []

            if completed is False or status.get("status_str") == "error":
                print("\nFAILED during execution:", file=sys.stderr)
                for name, payload in messages:
                    if "error" in name.lower():
                        print(f"  {name}: {json.dumps(payload)[:1500]}", file=sys.stderr)
                return 1

            if completed:
                elapsed = round(time.time() - started, 1)
                outputs = entry.get("outputs") or {}
                images = [
                    img
                    for node in outputs.values()
                    for img in (node.get("images") or [])
                ]
                print(f"\nCOMPLETED in {elapsed}s")
                if not images:
                    print("but produced NO images -- treating as failure", file=sys.stderr)
                    print(json.dumps(outputs)[:800], file=sys.stderr)
                    return 1
                for img in images:
                    print(f"  output: {img.get('subfolder')}/{img.get('filename')} "
                          f"[{img.get('type')}]")
                return 0

        queue = get(args.host, "/queue")
        running = len(queue.get("queue_running") or [])
        pending = len(queue.get("queue_pending") or [])
        note = f"running={running} pending={pending}"
        if note != last_note:
            print(f"  [{int(time.time()-started):>4}s] {note}")
            last_note = note
        time.sleep(5)

    print(f"\nTIMEOUT after {args.timeout}s -- still not complete", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
