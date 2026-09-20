#!/usr/bin/env python3
"""Start download_planned.py on the pod using HF_TOKEN from pid 1 (RunPod env)."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

LOG = Path("/workspace/epalle/logs/download-planned.log")
PY = "/workspace/epalle/venv/bin/python"
PLAN = "/workspace/epalle/download-plan.json"


def inherit_pid1_token() -> bool:
    raw = Path("/proc/1/environ").read_bytes().split(b"\0")
    for entry in raw:
        if entry.startswith(b"HF_TOKEN="):
            value = entry.split(b"=", 1)[1].decode()
            os.environ["HF_TOKEN"] = value
            os.environ["HUGGING_FACE_HUB_TOKEN"] = value
            return True
    return False


def main() -> int:
    os.environ["EPALLE_MODELS"] = "/workspace/epalle/models"
    os.environ["EPALLE_HF_CACHE"] = "/workspace/epalle/cache/huggingface"
    Path("/workspace/epalle/models").mkdir(parents=True, exist_ok=True)
    Path("/workspace/epalle/cache/huggingface").mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    print("HF_from_pid1", "yes" if inherit_pid1_token() else "no")
    subprocess.call(["pkill", "-f", "download_planned.py"])
    time.sleep(1)
    log = LOG.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [PY, "/workspace/epalle/download_planned.py", "--plan", PLAN],
        stdout=log, stderr=subprocess.STDOUT, env=os.environ,
    )
    print("DOWNLOAD_PID", proc.pid)
    time.sleep(8)
    text = LOG.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines()[:25]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
