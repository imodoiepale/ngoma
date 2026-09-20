"""Probe the RunPod HTTP proxy without printing secrets. Reports who sent the 403."""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "common"))
import vault

POD = "7oezgkushij7o1"
URLS = [
    f"https://{POD}-8188.proxy.runpod.net/system_stats",
    f"https://{POD}-8188.proxy.runpod.net/queue",
    f"http://{POD}-8188.proxy.runpod.net/system_stats",
]

ctx = ssl.create_default_context()
token = (vault.get("RUNPOD_API_KEY") or "").strip()


def fetch(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
            body = resp.read(800)
            return {
                "url": url,
                "status": resp.status,
                "ctype": resp.headers.get("content-type"),
                "server": resp.headers.get("server"),
                "cf": resp.headers.get("cf-ray"),
                "via": resp.headers.get("via"),
                "body": body[:240].decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(800)
        return {
            "url": url,
            "status": exc.code,
            "ctype": exc.headers.get("content-type") if exc.headers else None,
            "server": exc.headers.get("server") if exc.headers else None,
            "cf": exc.headers.get("cf-ray") if exc.headers else None,
            "via": exc.headers.get("via") if exc.headers else None,
            "www-auth": exc.headers.get("www-authenticate") if exc.headers else None,
            "body": body[:240].decode("utf-8", "replace"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": type(exc).__name__, "msg": str(exc)[:200]}


ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0"
print("=== anonymous browser UA ===")
for url in URLS:
    print(json.dumps(fetch(url, {"User-Agent": ua, "Accept": "application/json,*/*"}), indent=2))

print("=== bearer (key present=%s) ===" % bool(token))
if token:
    print(json.dumps(
        fetch(URLS[0], {"User-Agent": ua, "Authorization": f"Bearer {token}", "Accept": "application/json"}),
        indent=2,
    ))
