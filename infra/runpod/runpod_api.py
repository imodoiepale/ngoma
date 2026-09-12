#!/usr/bin/env python3
"""Reusable RunPod client for the EPALLE studio.

Replaces the ad-hoc scripts that were scattered through work/. Handles credential
loading, the REST API, the GraphQL API (still needed for serverless endpoint mutations),
pod lifecycle, capacity discovery and job submission.

Credentials, in precedence order:
  1. RUNPOD_API_KEY environment variable
  2. runpod-token.dpapi (Windows DPAPI, current user) -- searched in work/ then here

Usage:
    python runpod_api.py whoami
    python runpod_api.py volumes
    python runpod_api.py pods
    python runpod_api.py gpu-types [--datacenter US-KS-2]
    python runpod_api.py capacity --datacenter US-KS-2 --min-vram 40
    python runpod_api.py endpoint
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
TOKEN_CANDIDATES = [
    WORKSPACE / "work" / "runpod-token.dpapi",
    HERE / "runpod-token.dpapi",
]

REST_BASE = "https://rest.runpod.io/v1"
GRAPHQL_URL = "https://api.runpod.io/graphql"

# EPALLE fixed resources.
VOLUME_ID = "7y7jyghmua"
DATACENTER = "US-KS-2"
ENDPOINT_ID = "ugtmfoidpnh8pd"
TEMPLATE_ID = "s7eg4zafj9"
POD_ID = "eeoldxyxnd0o1z"

MAX_RETRIES = 4

# Cloudflare fronts api.runpod.io and blocks urllib's default signature with error
# 1010. Any conventional User-Agent gets through.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) epalle-runpod-client/1.0"


def decode_secret(raw: bytes) -> str:
    """Decode DPAPI plaintext.

    These blobs were written by PowerShell, whose strings are UTF-16LE, so the
    plaintext has a null byte after every character. Decoding that as UTF-8 yields a
    string full of NULs, which Cloudflare rejects with a bare HTTP 400 when it reaches
    an Authorization header. Detect the encoding rather than assuming UTF-8.
    """
    if len(raw) >= 2 and len(raw) % 2 == 0 and raw[1] == 0:
        try:
            return raw.decode("utf-16-le").lstrip("﻿")
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8-sig")


def read_dpapi(path: Path) -> str | None:
    """Decrypt a hex-encoded DPAPI blob. Windows only, current user only."""
    if not path.exists() or sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        raw = bytes.fromhex(path.read_text(encoding="utf-8").strip())
        blob_in = Blob(len(raw), ctypes.cast(ctypes.create_string_buffer(raw),
                                             ctypes.POINTER(ctypes.c_char)))
        blob_out = Blob()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return None
        try:
            return decode_secret(ctypes.string_at(blob_out.pbData, blob_out.cbData))
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception as exc:  # noqa: BLE001 - report and fall through to other sources
        print(f"warning: DPAPI decrypt of {path.name} failed: {exc}", file=sys.stderr)
        return None


def resolve_token() -> str:
    token = os.environ.get("RUNPOD_API_KEY")
    if token:
        return token.strip()
    for candidate in TOKEN_CANDIDATES:
        token = read_dpapi(candidate)
        if token:
            return token.strip()
    print(
        "error: no RunPod API key. Set RUNPOD_API_KEY, or place a DPAPI blob at one of:\n"
        + "\n".join(f"  {c}" for c in TOKEN_CANDIDATES),
        file=sys.stderr,
    )
    raise SystemExit(2)


class RunPodError(RuntimeError):
    def __init__(self, status: int, body: str, method: str, url: str):
        super().__init__(f"{method} {url} -> HTTP {status}: {body[:600]}")
        self.status = status
        self.body = body


class RunPod:
    def __init__(self, token: str | None = None, verbose: bool = False):
        self._token = token or resolve_token()
        self.verbose = verbose

    def _send(self, req: urllib.request.Request, method: str, url: str):
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    text = resp.read().decode("utf-8")
                    if self.verbose:
                        print(f"  {method} {url} -> {resp.status}", file=sys.stderr)
                    return json.loads(text) if text.strip() else {}
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")
                if exc.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RunPodError(exc.code, body, method, url) from exc
            except urllib.error.URLError as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc
        raise RuntimeError("unreachable")

    def rest(self, method: str, path: str, body=None):
        url = f"{REST_BASE}{path}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=payload, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", USER_AGENT)
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        return self._send(req, method, url)

    def graphql(self, query: str, variables: dict | None = None):
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(GRAPHQL_URL, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", USER_AGENT)
        result = self._send(req, "POST", GRAPHQL_URL)
        if result.get("errors"):
            raise RunPodError(200, json.dumps(result["errors"]), "POST", GRAPHQL_URL)
        return result.get("data") or {}

    # ------------------------------------------------------------------ read paths

    def whoami(self) -> dict:
        return self.graphql(
            "query { myself { id email clientBalance currentSpendPerHr } }"
        ).get("myself") or {}

    def volumes(self) -> list[dict]:
        result = self.rest("GET", "/networkvolumes")
        return result if isinstance(result, list) else (result.get("data") or [])

    def pods(self) -> list[dict]:
        result = self.rest("GET", "/pods")
        return result if isinstance(result, list) else (result.get("data") or [])

    def pod(self, pod_id: str) -> dict:
        return self.rest("GET", f"/pods/{pod_id}")

    def endpoints(self) -> list[dict]:
        result = self.rest("GET", "/endpoints")
        return result if isinstance(result, list) else (result.get("data") or [])

    def gpu_types(self) -> list[dict]:
        """Every GPU type, with per-datacenter stock status where the API exposes it."""
        data = self.graphql(
            """
            query {
              gpuTypes {
                id
                displayName
                memoryInGb
                secureCloud
                communityCloud
                lowestPrice(input: {gpuCount: 1}) {
                  minimumBidPrice
                  uninterruptablePrice
                  stockStatus
                }
              }
            }
            """
        )
        return data.get("gpuTypes") or []

    def datacenter_gpu_availability(self) -> list[dict]:
        """Per-datacenter GPU availability. Shape varies by API version."""
        try:
            data = self.graphql(
                """
                query {
                  dataCenters {
                    id
                    name
                    listed
                    gpuAvailability {
                      gpuTypeId
                      available
                      stockStatus
                    }
                  }
                }
                """
            )
            return data.get("dataCenters") or []
        except RunPodError as exc:
            print(f"warning: dataCenters query unavailable: {exc}", file=sys.stderr)
            return []

    # ----------------------------------------------------------------- write paths

    def start_pod(self, pod_id: str) -> dict:
        return self.rest("POST", f"/pods/{pod_id}/start")

    def stop_pod(self, pod_id: str) -> dict:
        return self.rest("POST", f"/pods/{pod_id}/stop")

    def create_pod(self, body: dict) -> dict:
        return self.rest("POST", "/pods", body=body)

    def update_endpoint_gpus(self, endpoint_id: str, gpu_ids: str) -> dict:
        """Widen the serverless endpoint's accepted GPU list. GraphQL only."""
        return self.graphql(
            """
            mutation ($input: EndpointInput!) {
              saveEndpoint(input: $input) {
                id name gpuIds workersMin workersMax networkVolumeId locations
              }
            }
            """,
            {"input": {"id": endpoint_id, "gpuIds": gpu_ids}},
        )


# ------------------------------------------------------------------------ commands


def cmd_whoami(client: RunPod, _args) -> int:
    me = client.whoami()
    print(json.dumps(me, indent=2))
    balance = me.get("clientBalance")
    if isinstance(balance, (int, float)) and balance < 5:
        print(f"\nWARNING: balance is {balance}. Pods will not start below the "
              "minimum reserve.", file=sys.stderr)
    return 0


def cmd_volumes(client: RunPod, _args) -> int:
    for volume in client.volumes():
        marker = "  <- EPALLE" if volume.get("id") == VOLUME_ID else ""
        print(f"{volume.get('id')}  {volume.get('size')} GB  "
              f"{volume.get('dataCenterId')}  {volume.get('name')!r}{marker}")
    return 0


def cmd_pods(client: RunPod, _args) -> int:
    pods = client.pods()
    if not pods:
        print("no pods")
        return 0
    for pod in pods:
        print(f"{pod.get('id')}  {pod.get('desiredStatus')}  "
              f"{pod.get('machine', {}).get('gpuTypeId') or pod.get('gpuTypeId')}  "
              f"{pod.get('name')!r}  ${pod.get('costPerHr')}/hr")
    return 0


def cmd_endpoint(client: RunPod, _args) -> int:
    for endpoint in client.endpoints():
        print(json.dumps(endpoint, indent=2))
    return 0


def cmd_gpu_types(client: RunPod, args) -> int:
    types = client.gpu_types()
    rows = []
    for gpu in types:
        vram = gpu.get("memoryInGb") or 0
        if vram < args.min_vram:
            continue
        price = gpu.get("lowestPrice") or {}
        rows.append(
            (
                vram,
                gpu.get("id"),
                gpu.get("displayName"),
                price.get("stockStatus"),
                price.get("uninterruptablePrice"),
                gpu.get("secureCloud"),
                gpu.get("communityCloud"),
            )
        )
    rows.sort(reverse=True)
    print(f"{'VRAM':>5}  {'id':<28} {'stock':<12} {'$/hr':<8} secure/community  name")
    for vram, gid, name, stock, price, secure, community in rows:
        print(f"{vram:>5}  {gid:<28} {str(stock):<12} {str(price):<8} "
              f"{str(secure):<6}/{str(community):<9} {name}")
    print(f"\n{len(rows)} GPU types with >= {args.min_vram} GB VRAM")
    return 0


def cmd_capacity(client: RunPod, args) -> int:
    """What can actually run in the datacenter holding our network volume."""
    print(f"Datacenter: {args.datacenter}   min VRAM: {args.min_vram} GB\n")
    centers = client.datacenter_gpu_availability()
    target = next((c for c in centers if c.get("id") == args.datacenter), None)

    vram_by_id = {g.get("id"): (g.get("memoryInGb") or 0) for g in client.gpu_types()}

    if target and target.get("gpuAvailability"):
        rows = []
        for entry in target["gpuAvailability"]:
            gid = entry.get("gpuTypeId")
            vram = vram_by_id.get(gid, 0)
            if vram < args.min_vram:
                continue
            rows.append((vram, gid, entry.get("available"), entry.get("stockStatus")))
        rows.sort(reverse=True)
        print(f"{'VRAM':>5}  {'id':<28} available  stock")
        for vram, gid, available, stock in rows:
            print(f"{vram:>5}  {gid:<28} {str(available):<10} {stock}")
        usable = [gid for _, gid, available, _ in rows if available]
        print(f"\n{len(usable)} usable now: {','.join(usable) if usable else '(none)'}")
        return 0 if usable else 1

    print("Per-datacenter availability not exposed by the API for this account.")
    print("Falling back to global stock status; datacenter fit is still unproven.\n")
    return cmd_gpu_types(client, args)


COMMANDS = {
    "whoami": cmd_whoami,
    "volumes": cmd_volumes,
    "pods": cmd_pods,
    "endpoint": cmd_endpoint,
    "gpu-types": cmd_gpu_types,
    "capacity": cmd_capacity,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--datacenter", default=DATACENTER)
    parser.add_argument("--min-vram", type=int, default=40)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    client = RunPod(verbose=args.verbose)
    try:
        return COMMANDS[args.command](client, args)
    except RunPodError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
