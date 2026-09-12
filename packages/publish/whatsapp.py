"""WhatsApp Status via OpenWA.

Postiz does not support WhatsApp — its provider list has no WhatsApp `__type` — so Status
posting goes through a separate, deliberately narrow adapter.

This uses an **unofficial** WhatsApp automation path. That fact drives every design choice
here, and none of it is decoration:

  * One session, one number, one job at a time. Running OpenWA and Evolution API against
    the same number gets it banned.
  * Conservative daily caps and a minimum gap between sends. WhatsApp restricts accounts
    that send fast, repeat content, or retry in tight loops.
  * Human approval per send. Nothing goes to Status because a cron fired.
  * An idempotency key per item, persisted, so a retried run cannot double-post — there is
    no server-side dedupe to fall back on.
  * v4.76.0 is the pinned target. OpenWA's own docs call v5 alpha.

If WhatsApp is business-critical, the honest answer is the official WhatsApp Business
Platform, which does not expose Status at all. Status automation is inherently
unsupported; treat it as a channel you accept risk on, not one you depend on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

REPO = Path(__file__).resolve().parents[2]
STATE = REPO / "out" / "whatsapp-state.json"

StatusKind = Literal["text", "image", "video"]

# Deliberately cautious. These are not WhatsApp's published limits — there are none —
# they are a posture that keeps a number alive.
MAX_PER_DAY = 8
MIN_GAP_SECONDS = 600
MAX_CAPTION = 700


class WhatsAppError(RuntimeError):
    pass


@dataclass
class StatusItem:
    kind: StatusKind
    caption: str = ""
    media: Path | None = None
    brand: str = ""
    title: str = ""
    idempotency_key: str = ""
    warnings: list[str] = field(default_factory=list)


def _base() -> str:
    url = (os.environ.get("OPENWA_URL") or "").rstrip("/")
    if not url:
        raise WhatsAppError(
            "OPENWA_URL is not set (e.g. http://127.0.0.1:8002). See infra/openwa/README.md. "
            "Bind OpenWA to localhost or behind auth — an open instance is a hijacked "
            "WhatsApp account.")
    return url


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "User-Agent": "epalle-studio/1.0"}
    key = os.environ.get("OPENWA_API_KEY")
    if key:
        h["api_key"] = key
    return h


def _post(path: str, body: dict[str, Any], timeout: int = 180) -> Any:
    req = urllib.request.Request(f"{_base()}{path}", data=json.dumps(body).encode(),
                                 headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise WhatsAppError(f"POST {path} failed ({e.code}): "
                            f"{e.read().decode('utf-8','replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise WhatsAppError(f"could not reach OpenWA at {_base()}: {e.reason}") from e


def _load_state() -> dict[str, Any]:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"sent": {}, "log": []}


def _save_state(s: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def key_for(item: StatusItem) -> str:
    h = hashlib.sha256()
    h.update(f"{item.brand}|{item.kind}|{item.caption}".encode())
    if item.media and item.media.exists():
        h.update(hashlib.sha256(item.media.read_bytes()).digest())
    return h.hexdigest()[:32]


def session_ok() -> tuple[bool, str]:
    """Is a session actually paired? A reachable server with no session silently no-ops."""
    try:
        req = urllib.request.Request(f"{_base()}/session/status", headers=_headers())
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read() or "{}")
        state = str(d.get("data") or d.get("state") or d.get("status") or "").upper()
        return ("CONNECTED" in state or "AUTHENTICATED" in state), state or "unknown"
    except Exception as e:  # noqa: BLE001 - any failure means not usable
        return False, str(e)[:160]


def preflight(items: list[StatusItem], state: dict[str, Any]) -> list[str]:
    """Everything that would make a send unsafe, gathered before anything is sent."""
    problems: list[str] = []
    today = datetime.now(timezone.utc).date().isoformat()
    sent_today = sum(1 for v in state["sent"].values() if v.get("date", "").startswith(today))
    if sent_today + len(items) > MAX_PER_DAY:
        problems.append(f"{sent_today} already sent today and {len(items)} queued would "
                        f"exceed the {MAX_PER_DAY}/day cap")
    for it in items:
        it.idempotency_key = it.idempotency_key or key_for(it)
        if it.idempotency_key in state["sent"]:
            prev = state["sent"][it.idempotency_key]
            problems.append(f"{it.title or it.kind}: already sent {prev.get('date')} "
                            f"(idempotency key {it.idempotency_key[:12]})")
        if it.kind != "text":
            if not it.media:
                problems.append(f"{it.title or it.kind}: {it.kind} status needs a media file")
            elif not it.media.exists():
                problems.append(f"{it.title or it.kind}: media missing at {it.media}")
        if len(it.caption) > MAX_CAPTION:
            it.warnings.append(f"caption {len(it.caption)} chars; keeping under "
                               f"{MAX_CAPTION} reads better on Status")
    return problems


def send(items: list[StatusItem], dry_run: bool = True, confirmed: bool = False) -> dict[str, Any]:
    state = _load_state()
    problems = preflight(items, state)
    if dry_run:
        return {"status": "DRY_RUN", "items": len(items), "problems": problems,
                "warnings": {i.title or i.kind: i.warnings for i in items if i.warnings},
                "would_send": [{"kind": i.kind, "media": str(i.media) if i.media else None,
                                "caption": i.caption[:80], "key": i.idempotency_key[:12]}
                               for i in items]}
    if problems:
        return {"status": "BLOCKED", "problems": problems}
    if not confirmed:
        return {"status": "BLOCKED",
                "problems": ["WhatsApp Status posts to a real audience from your own number. "
                             "Pass --i-mean-it to send."]}
    ok, detail = session_ok()
    if not ok:
        return {"status": "BLOCKED",
                "problems": [f"no paired WhatsApp session ({detail}). Scan the QR first — "
                             f"see infra/openwa/README.md."]}

    results = []
    for i, it in enumerate(items):
        if i:
            time.sleep(MIN_GAP_SECONDS)   # pacing is the point, not a nicety
        route = {"text": "/status/send-text", "image": "/status/send-image",
                 "video": "/status/send-video"}[it.kind]
        body: dict[str, Any] = {"text" if it.kind == "text" else "caption": it.caption}
        if it.media:
            import base64
            body["file"] = ("data:" + ("video/mp4" if it.kind == "video" else "image/png")
                            + ";base64," + base64.b64encode(it.media.read_bytes()).decode())
        try:
            r = _post(route, body)
            state["sent"][it.idempotency_key] = {
                "date": datetime.now(timezone.utc).isoformat(), "kind": it.kind,
                "title": it.title, "response": str(r)[:200]}
            results.append({"title": it.title or it.kind, "status": "SENT"})
        except WhatsAppError as e:
            results.append({"title": it.title or it.kind, "status": "FAILED", "error": str(e)})
            break            # stop the batch; do not hammer a failing session
        finally:
            _save_state(state)
    return {"status": "DONE", "results": results}


def main() -> None:
    ap = argparse.ArgumentParser(description="Post WhatsApp Status via OpenWA.")
    ap.add_argument("command", choices=["status", "send"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--kind", choices=["text", "image", "video"], default="image")
    ap.add_argument("--caption", default="")
    ap.add_argument("--media", type=Path)
    ap.add_argument("--title", default="")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--i-mean-it", action="store_true",
                    help="required to actually post to your Status")
    a = ap.parse_args()

    if a.command == "status":
        ok, detail = session_ok()
        print(f"OpenWA session: {'CONNECTED' if ok else 'NOT USABLE'} ({detail})")
        st = _load_state()
        today = datetime.now(timezone.utc).date().isoformat()
        n = sum(1 for v in st["sent"].values() if v.get("date", "").startswith(today))
        print(f"sent today: {n}/{MAX_PER_DAY}   history: {len(st['sent'])} item(s)")
        raise SystemExit(0 if ok else 1)

    item = StatusItem(kind=a.kind, caption=a.caption, media=a.media,
                      brand=a.brand, title=a.title or a.kind)
    res = send([item], dry_run=not a.live, confirmed=a.i_mean_it)
    print(json.dumps(res, indent=2)[:1400])
    if res.get("status") == "DRY_RUN":
        print("\n(dry run — pass --live --i-mean-it to actually post)")


if __name__ == "__main__":
    # A configuration mistake should read as one sentence, not a traceback.
    try:
        main()
    except WhatsAppError as e:
        raise SystemExit(f"error: {e}")
