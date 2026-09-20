#!/usr/bin/env python3
"""One-click Director pod: official ComfyUI image + volume bind + nodes + models.

From the repo on your machine:

    python infra/runpod/one_click.py

If director-comfyui is already RUNNING this only bootstraps it (bind model folders,
restart Comfy, optionally resume downloads). If it is stopped or missing, this
provisions a new official `runpod/comfyui:cuda12.8` pod on the existing network
volume, waits for SSH, then bootstraps.

The network volume is the real template: models, node packs, and workflows live
there. Every new pod is the official Comfy image pointed at that volume so
UpscaleModelLoader / LoraLoader never see an empty list for files that are already
downloaded.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import provision_pod  # noqa: E402
from runpod_api import POD_ID, RunPod  # noqa: E402

KEYS = [
    Path.home() / ".ssh" / "director_runpod",
    HERE.parent / "epalle_runpod_ed25519",
]
REMOTE_FILES = [
    "bootstrap_director.py",
    "extra_model_paths.yaml",
    "install-template-nodes.py",
    "download_planned.py",
    "download-plan.json",
    "download-krea-missing.py",
    "copy-h3-extras.py",
    "patch-kj-minimax.py",
]


def ssh_key() -> Path:
    for key in KEYS:
        if key.is_file():
            return key
    raise SystemExit(
        "no SSH key found (tried ~/.ssh/director_runpod and infra/epalle_runpod_ed25519)"
    )


def ssh_base(ip: str, port: int) -> list[str]:
    return [
        "ssh",
        "-i",
        str(ssh_key()),
        "-p",
        str(port),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=15",
        f"root@{ip}",
    ]


def scp_base(ip: str, port: int) -> list[str]:
    return [
        "scp",
        "-i",
        str(ssh_key()),
        "-P",
        str(port),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=15",
    ]


def mapped_ssh(pod: dict) -> tuple[str, int]:
    ip = pod.get("publicIp") or ""
    mappings = pod.get("portMappings") or {}
    port = None
    if isinstance(mappings, dict):
        port = mappings.get("22") or mappings.get(22)
    elif isinstance(mappings, list):
        for item in mappings:
            if str(item.get("privatePort") or item.get("private")) == "22":
                port = item.get("publicPort") or item.get("public")
    if not ip or not port:
        raise SystemExit(f"pod has no SSH mapping yet: ip={ip!r} maps={mappings!r}")
    return ip, int(port)


def wait_ssh(ip: str, port: int, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ssh_base(ip, port) + ["echo", "SSH_OK"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and "SSH_OK" in (result.stdout or ""):
            print(f"ssh ready {ip}:{port}")
            return
        time.sleep(5)
    raise SystemExit(f"ssh not ready on {ip}:{port}")


def upload(ip: str, port: int) -> None:
    remote = "/workspace/epalle"
    subprocess.check_call(ssh_base(ip, port) + [f"mkdir -p {remote} {remote}/logs {remote}/models"])
    files = [str(HERE / name) for name in REMOTE_FILES if (HERE / name).is_file()]
    if not files:
        raise SystemExit("no bootstrap files to upload")
    subprocess.check_call(scp_base(ip, port) + files + [f"root@{ip}:{remote}/"])
    subprocess.check_call(
        ssh_base(ip, port)
        + ["sed -i 's/\\r$//' /workspace/epalle/*.py /workspace/epalle/*.yaml /workspace/epalle/*.sh 2>/dev/null || true"]
    )
    print(f"uploaded {len(files)} files to {remote}")
    subprocess.call(
        ssh_base(ip, port)
        + ["pkill -f download_planned.py; pkill -f huggingface-cli; pkill -f hf_transfer; true"]
    )


def run_bootstrap(ip: str, port: int, full: bool, download_all: bool) -> None:
    py = "python3"
    flag = " --full" if full else ""
    if download_all:
        flag += " --download-all"
    cmd = ssh_base(ip, port) + [f"{py} /workspace/epalle/bootstrap_director.py{flag}"]
    print("running bootstrap on pod...")
    subprocess.check_call(cmd)


def pick_pod(client: RunPod, create: bool) -> dict:
    pods = client.pods()
    running = [
        p
        for p in pods
        if p.get("desiredStatus") == "RUNNING"
        and "director" in (p.get("name") or "").lower()
    ]
    if running:
        return running[0]
    if not create:
        current = next((p for p in pods if p.get("id") == POD_ID), None)
        if current and current.get("desiredStatus") == "RUNNING":
            return current
        raise SystemExit("no running director pod; pass --create to provision one")
    print("no running director pod; provisioning official ComfyUI template...")
    options = provision_pod.available_gpus(client, provision_pod.DATACENTER, 40)
    if not options:
        raise SystemExit("no GPU available in the volume datacenter")
    created = provision_pod.create(client, options[0], False, provision_pod.VOLUME_ID)
    return provision_pod.wait_running(client, created["id"])


def print_urls(pod: dict) -> None:
    pod_id = pod.get("id")
    print("\n--- Director ComfyUI ---")
    print(f"pod       : {pod_id}")
    print(f"Comfy     : https://{pod_id}-8188.proxy.runpod.net")
    print(f"Jupyter   : https://{pod_id}-8888.proxy.runpod.net/lab?token=director")
    print(f"Files     : https://{pod_id}-8080.proxy.runpod.net")
    print("Studio    : http://localhost:3000")
    print(f"stop      : python infra/runpod/provision_pod.py --stop {pod_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="provision a pod if none is running")
    parser.add_argument("--full", action="store_true", help="install node packs, H3 extras, priority downloads")
    parser.add_argument("--download-all", action="store_true", help="resume the entire download plan")
    parser.add_argument("--bind-only", action="store_true", help="skip --full even if passed")
    args = parser.parse_args()

    client = RunPod()
    pod = pick_pod(client, create=args.create)
    ip, port = mapped_ssh(pod)
    print(f"pod {pod.get('id')}  {ip}:{port}")
    wait_ssh(ip, port)
    upload(ip, port)
    run_bootstrap(ip, port, full=args.full and not args.bind_only, download_all=args.download_all)
    print_urls(pod)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
