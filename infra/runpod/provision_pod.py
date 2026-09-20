#!/usr/bin/env python3
"""Provision an EPALLE development pod on whatever GPU is actually available.

The original pod is pinned to a single GPU type (RTX A6000) on a host with no free
GPU, so it cannot resume. This script instead discovers live availability in the
datacenter that holds the network volume, picks the cheapest card meeting a VRAM
floor, and creates a pod attached to that volume.

A pod must run in the same datacenter as its network volume, so the datacenter is
fixed -- only the GPU type is negotiable.

Usage:
    python provision_pod.py --plan                 # show the choice, create nothing
    python provision_pod.py                        # create and wait for RUNNING
    python provision_pod.py --max-price 1.50       # refuse anything more expensive
    python provision_pod.py --status               # show current pods
    python provision_pod.py --stop <pod_id>        # stop a pod (ends GPU billing)

After a pod is RUNNING, bind models + restart Comfy with:
    python one_click.py
    python one_click.py --create --full            # provision if needed, install nodes, download gaps
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from runpod_api import DATACENTER, VOLUME_ID, RunPod, RunPodError

HERE = Path(__file__).resolve().parent
PUBKEY_PATH = HERE.parent / "epalle_runpod_ed25519.pub"
SPEC_PATH = HERE.parent / "runpod-pod-spec.json"
STATE_PATH = HERE / "active-pod.json"

# Official ComfyUI template (comfyui-base). Blackwell cards need the cuda12.8 tag.
# https://docs.runpod.io/tutorials/pods/comfyui
IMAGE = "runpod/comfyui:cuda12.8"
POD_NAME = "director-comfyui"
PORTS = ["8188/http", "8080/http", "8888/http", "22/tcp"]
CONTAINER_DISK_GB = 50
BOOT_TIMEOUT_S = 600


def available_gpus(client: RunPod, datacenter: str, min_vram: int) -> list[dict]:
    """Live availability in one datacenter, cheapest first."""
    prices, vram = {}, {}
    for gpu in client.gpu_types():
        gid = gpu.get("id")
        vram[gid] = gpu.get("memoryInGb") or 0
        low = gpu.get("lowestPrice") or {}
        prices[gid] = low.get("uninterruptablePrice")

    centers = client.datacenter_gpu_availability()
    target = next((c for c in centers if c.get("id") == datacenter), None)
    if not target or not target.get("gpuAvailability"):
        raise RuntimeError(
            f"could not read GPU availability for {datacenter}; refusing to guess"
        )

    options = []
    for entry in target["gpuAvailability"]:
        gid = entry.get("gpuTypeId")
        if not entry.get("available") or vram.get(gid, 0) < min_vram:
            continue
        options.append(
            {
                "id": gid,
                "vram": vram[gid],
                "price": prices.get(gid),
                "stock": entry.get("stockStatus"),
            }
        )
    # Unpriced options sort last rather than being treated as free.
    options.sort(key=lambda o: (o["price"] is None, o["price"] or 0))
    return options


def _hf_token() -> str:
    sys.path.insert(0, str(HERE.parents[1] / "packages" / "common"))
    import vault
    return (vault.get("HF_TOKEN") or "").strip()


def create(
    client: RunPod,
    gpu: dict,
    dry_run: bool,
    volume_id: str,
    image: str = IMAGE,
    name: str = POD_NAME,
) -> dict | None:
    if not PUBKEY_PATH.exists():
        raise RuntimeError(f"missing SSH public key at {PUBKEY_PATH}")
    if not volume_id:
        raise RuntimeError("network volume id is required (create the volume first)")

    env = {
        "PUBLIC_KEY": PUBKEY_PATH.read_text(encoding="utf-8").strip(),
        "JUPYTER_PASSWORD": "director",
    }
    hf = _hf_token()
    if hf:
        env["HF_TOKEN"] = hf
        env["HUGGING_FACE_HUB_TOKEN"] = hf

    body = {
        "name": name,
        "gpuTypeIds": [gpu["id"]],
        "gpuCount": 1,
        "imageName": image,
        "networkVolumeId": volume_id,
        "volumeMountPath": "/workspace",
        "containerDiskInGb": CONTAINER_DISK_GB,
        "ports": PORTS,
        "env": env,
        "supportPublicIp": True,
        "computeType": "GPU",
        "cloudType": "SECURE",
    }

    redacted_env = {"PUBLIC_KEY": "<ssh public key>", "JUPYTER_PASSWORD": "<set>"}
    if hf:
        redacted_env["HF_TOKEN"] = "<set>"
        redacted_env["HUGGING_FACE_HUB_TOKEN"] = "<set>"
    redacted = {**body, "env": redacted_env}
    print(json.dumps(redacted, indent=2))

    if dry_run:
        print("\n--plan given, nothing created")
        return None

    print(f"\ncreating pod on {gpu['id']} at ${gpu['price']}/hr ...")
    pod = client.create_pod(body)
    pod_id = pod.get("id")
    if not pod_id:
        raise RuntimeError(f"create returned no id: {json.dumps(pod)[:400]}")

    # Persist the spec without secrets, and the active pod for later steps.
    SPEC_PATH.write_text(json.dumps(redacted, indent=2) + "\n", encoding="utf-8")
    STATE_PATH.write_text(
        json.dumps(
            {
                "pod_id": pod_id,
                "gpu": gpu["id"],
                "price_per_hr": gpu["price"],
                "datacenter": DATACENTER,
                "network_volume": volume_id,
                "image": image,
                "name": name,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"created pod {pod_id}")
    return pod


def wait_running(client: RunPod, pod_id: str) -> dict:
    print(f"waiting for {pod_id} to report RUNNING (timeout {BOOT_TIMEOUT_S}s)...")
    deadline = time.time() + BOOT_TIMEOUT_S
    last = None
    while time.time() < deadline:
        pod = client.pod(pod_id)
        status = pod.get("desiredStatus")
        ip = pod.get("publicIp") or ""
        if status != last:
            print(f"  status={status} publicIp={ip or '(pending)'}")
            last = status
        if status == "RUNNING" and ip:
            return pod
        time.sleep(10)
    print(f"timeout: pod {pod_id} did not reach RUNNING with a public IP",
          file=sys.stderr)
    return client.pod(pod_id)


def describe(pod: dict) -> None:
    print("\n--- pod ---")
    print(f"id        : {pod.get('id')}")
    print(f"status    : {pod.get('desiredStatus')}")
    print(f"cost      : ${pod.get('costPerHr')}/hr")
    print(f"publicIp  : {pod.get('publicIp') or '(none)'}")
    print(f"vcpu/ram  : {pod.get('vcpuCount')} vCPU / {pod.get('memoryInGb')} GB")
    for mapping in pod.get("portMappings") or []:
        print(f"port map  : {mapping}")
    if isinstance(pod.get("portMappings"), dict):
        for private, public in pod["portMappings"].items():
            print(f"port map  : {private} -> {public}")
    print(
        "\nSSH:\n  ssh -i ../epalle_runpod_ed25519 -p <mapped-22-port> "
        f"root@{pod.get('publicIp') or '<ip>'}"
    )
    print("\nRemember to stop the pod when you are done:")
    print(f"  python provision_pod.py --stop {pod.get('id')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true",
                        help="show the selection and request body, create nothing")
    parser.add_argument("--status", action="store_true", help="list pods and exit")
    parser.add_argument("--stop", metavar="POD_ID", help="stop a pod and exit")
    parser.add_argument("--min-vram", type=int, default=40)
    parser.add_argument("--max-price", type=float, default=None,
                        help="refuse to create above this hourly price")
    parser.add_argument("--gpu", help="force a specific GPU type id")
    parser.add_argument("--datacenter", default=DATACENTER)
    parser.add_argument("--volume-id", default=VOLUME_ID,
                        help="network volume to attach (required for create)")
    parser.add_argument("--image", default=IMAGE,
                        help="container image (official ComfyUI template by default)")
    parser.add_argument("--name", default=POD_NAME)
    args = parser.parse_args()

    client = RunPod()

    if args.status:
        pods = client.pods()
        if not pods:
            print("no pods")
        for pod in pods:
            print(f"{pod.get('id')}  {pod.get('desiredStatus'):<8} "
                  f"${pod.get('costPerHr')}/hr  {pod.get('name')!r}  "
                  f"ip={pod.get('publicIp') or '-'}")
        return 0

    if args.stop:
        print(json.dumps(client.stop_pod(args.stop), indent=2))
        print(f"stopped {args.stop}; GPU billing ends, network volume persists")
        return 0

    options = available_gpus(client, args.datacenter, args.min_vram)
    print(f"Available in {args.datacenter} with >= {args.min_vram} GB VRAM:")
    for option in options:
        print(f"  {option['vram']:>3} GB  ${option['price']}/hr  "
              f"stock={option['stock']}  {option['id']}")
    if not options:
        print(
            f"\nNo GPU with >= {args.min_vram} GB VRAM is available in "
            f"{args.datacenter} right now. The network volume pins the datacenter, so "
            "the only options are to wait or to lower --min-vram.",
            file=sys.stderr,
        )
        return 1

    if args.gpu:
        chosen = next((o for o in options if o["id"] == args.gpu), None)
        if not chosen:
            print(f"\n{args.gpu!r} is not currently available here", file=sys.stderr)
            return 1
    else:
        chosen = options[0]

    print(f"\nselected: {chosen['id']} ({chosen['vram']} GB) at ${chosen['price']}/hr")

    if args.max_price is not None and (chosen["price"] or 0) > args.max_price:
        print(
            f"refusing: ${chosen['price']}/hr exceeds --max-price {args.max_price}",
            file=sys.stderr,
        )
        return 1

    try:
        pod = create(
            client, chosen, args.plan, args.volume_id,
            image=args.image, name=args.name,
        )
    except RunPodError as exc:
        print(f"create failed: {exc}", file=sys.stderr)
        return 1
    if pod is None:
        return 0

    describe(wait_running(client, pod["id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
