"""See whether Comfy 403s the HTML UI for a RunPod-console Origin."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

BASE = "https://7oezgkushij7o1-8188.proxy.runpod.net"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0"
CTX = ssl.create_default_context()

CASES = [
    ("GET / no origin", "/", {}),
    ("GET / origin=proxy", "/", {"Origin": BASE}),
    ("GET / origin=runpod", "/", {"Origin": "https://www.runpod.io"}),
    ("GET /system_stats origin=runpod", "/system_stats", {"Origin": "https://www.runpod.io"}),
    ("GET /queue origin=runpod", "/queue", {"Origin": "https://www.runpod.io"}),
]


def one(name: str, path: str, extra: dict) -> None:
    headers = {"User-Agent": UA, "Accept": "*/*", **extra}
    req = urllib.request.Request(BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
            body = resp.read(70)
            print(json.dumps({
                "case": name,
                "status": resp.status,
                "ctype": resp.headers.get("content-type"),
                "body": body.decode("utf-8", "replace"),
            }))
    except urllib.error.HTTPError as exc:
        body = exc.read(160)
        print(json.dumps({
            "case": name,
            "status": exc.code,
            "ctype": exc.headers.get("content-type") if exc.headers else None,
            "body": body.decode("utf-8", "replace"),
        }))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"case": name, "error": type(exc).__name__, "msg": str(exc)[:200]}))


for item in CASES:
    one(*item)
