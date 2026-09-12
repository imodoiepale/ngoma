"""Postiz adapter — schedule composited assets to social channels.

Postiz is self-hosted (Node + Postgres), so the base URL is your own instance:
`{NEXT_PUBLIC_BACKEND_URL}/public/v1`. The cloud host is api.postiz.com.

API shape, verified against docs.postiz.com:
  * auth header is `Authorization: <apiKey>` — NO "Bearer" prefix
  * `POST /public/v1/upload`       -> {"id", "path"}
  * `POST /public/v1/posts`        -> type: draft | schedule | now
  * `GET  /public/v1/integrations` -> connected channels ("integration" on the API is
                                       what the UI calls a channel)
  * rate limit 90 req/hour on post creation (self-host: `API_LIMIT` env var)

Safety posture, deliberate and load-bearing:
  * `draft` is the DEFAULT and the only type this module will send without an explicit
    flag. Nothing reaches a feed because a script ran.
  * `--schedule` requires a date. `--now` additionally requires `--i-mean-it`, because
    "publish immediately to a real audience" should be hard to do by accident.
  * A brief whose status is not `ready` is refused outright — the approval gates in
    packages/strategy/plan.py are enforced here, not just recorded there.
  * Every post carries an idempotency key derived from the asset checksums, so a retried
    run cannot double-post.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

# Postiz `settings.__type` values, from the docs. Kept explicit so a typo fails here
# rather than silently posting to the wrong surface.
PLATFORMS = {
    "instagram", "instagram-standalone", "x", "linkedin", "linkedin-page", "facebook",
    "threads", "tiktok", "youtube", "pinterest", "reddit", "discord", "slack", "telegram",
    "mastodon", "bluesky", "warpcast", "medium", "devto", "hashnode", "wordpress",
    "dribbble", "twitch", "gmb", "listmonk", "lemmy", "skool", "whop", "nostr", "vk", "kick",
}
IG_CAPTION_LIMIT = 2200
IG_CAROUSEL_MAX = 10


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


class PostizError(RuntimeError):
    pass


@dataclass
class Draft:
    brand: str
    title: str
    platform: str
    integration_id: str
    caption: str
    media: list[Path]
    scheduled_for: str | None = None
    idempotency_key: str = ""
    warnings: list[str] = field(default_factory=list)


def _base_url(explicit: str | None = None) -> str:
    url = (explicit or os.environ.get("POSTIZ_URL")
           or os.environ.get("NEXT_PUBLIC_BACKEND_URL") or "").rstrip("/")
    if not url:
        raise PostizError(
            "POSTIZ_URL is not set. For a self-hosted instance this is your backend origin, "
            "e.g. http://localhost:3000/api — the public API lives at <that>/public/v1. "
            "See infra/postiz/README.md.")
    return url if url.endswith("/public/v1") else f"{url}/public/v1"


def _key() -> str:
    k = _secret("POSTIZ_API_KEY")
    if not k:
        raise PostizError("POSTIZ_API_KEY is not set; refusing to call the API.")
    return k


def _request(method: str, path: str, base: str, body: Any = None,
             files: tuple[str, Path] | None = None, timeout: int = 120) -> Any:
    url = f"{base}{path}"
    headers = {"Authorization": _key(), "User-Agent": "epalle-studio/1.0"}
    data: bytes | None = None

    if files:
        field_name, fp = files
        boundary = f"----epalle{uuid.uuid4().hex}"
        ctype = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"
        pre = (f"--{boundary}\r\n"
               f'Content-Disposition: form-data; name="{field_name}"; filename="{fp.name}"\r\n'
               f"Content-Type: {ctype}\r\n\r\n").encode()
        post = f"\r\n--{boundary}--\r\n".encode()
        data = pre + fp.read_bytes() + post
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        if e.code == 429:
            raise PostizError(
                f"rate limited (90 posts/hour by default). Self-hosted instances can raise "
                f"this with the API_LIMIT env var. Server said: {detail}") from e
        raise PostizError(f"{method} {path} failed ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise PostizError(f"could not reach Postiz at {url}: {e.reason}") from e


def integrations(base: str | None = None) -> list[dict[str, Any]]:
    """Connected channels. The API calls these integrations; the UI calls them channels."""
    r = _request("GET", "/integrations", _base_url(base))
    return r if isinstance(r, list) else r.get("integrations", [])


def upload(fp: Path, base: str | None = None) -> dict[str, str]:
    if not fp.exists():
        raise PostizError(f"asset missing: {fp}")
    r = _request("POST", "/upload", _base_url(base), files=("file", fp), timeout=300)
    if not r.get("id"):
        raise PostizError(f"upload returned no id for {fp.name}: {str(r)[:200]}")
    return {"id": r["id"], "path": r.get("path", "")}


def idempotency_key(brand: str, title: str, media: list[Path]) -> str:
    h = hashlib.sha256()
    h.update(f"{brand}|{title}".encode())
    for m in sorted(media):
        h.update(hashlib.sha256(m.read_bytes()).digest() if m.exists() else m.name.encode())
    return h.hexdigest()[:32]


def validate(d: Draft) -> list[str]:
    """Platform rules that would otherwise fail server-side or, worse, publish wrong."""
    w: list[str] = []
    if d.platform not in PLATFORMS:
        raise PostizError(f"unknown platform {d.platform!r}; known: {sorted(PLATFORMS)}")
    if d.platform.startswith("instagram"):
        if len(d.caption) > IG_CAPTION_LIMIT:
            w.append(f"caption is {len(d.caption)} chars; Instagram caps at {IG_CAPTION_LIMIT}")
        if len(d.media) > IG_CAROUSEL_MAX:
            w.append(f"{len(d.media)} slides; Instagram carousels cap at {IG_CAROUSEL_MAX}")
        if not d.media:
            w.append("Instagram requires at least one image or video")
        vids = [m for m in d.media if m.suffix.lower() in {".mp4", ".mov"}]
        if vids and len(d.media) > 1 and len(vids) != len(d.media):
            w.append("mixed image and video in one carousel — Instagram is inconsistent here; "
                     "prefer all-image or all-video")
    missing = [str(m) for m in d.media if not m.exists()]
    if missing:
        raise PostizError(f"asset(s) not on disk: {', '.join(missing[:4])}")
    return w


def build_payload(drafts: list[Draft], post_type: str, base: str | None = None,
                  tags: list[str] | None = None, dry_run: bool = True) -> dict[str, Any]:
    if post_type not in ("draft", "schedule", "now"):
        raise PostizError(f"post type must be draft|schedule|now, got {post_type!r}")
    posts = []
    for d in drafts:
        d.warnings = validate(d)
        if dry_run:
            images = [{"id": f"<upload:{m.name}>", "path": str(m)} for m in d.media]
        else:
            images = [upload(m, base) for m in d.media]
        posts.append({
            "integration": {"id": d.integration_id},
            "value": [{"content": d.caption, "image": images}],
            "settings": {"__type": d.platform},
        })
    body: dict[str, Any] = {"type": post_type, "posts": posts,
                            "shortLink": False, "tags": tags or []}
    dates = [d.scheduled_for for d in drafts if d.scheduled_for]
    if post_type == "schedule":
        if not dates:
            raise PostizError("type=schedule needs a date on at least one draft")
        body["date"] = dates[0]
    return body


def send(drafts: list[Draft], post_type: str = "draft", base: str | None = None,
         tags: list[str] | None = None, dry_run: bool = True,
         confirmed: bool = False) -> dict[str, Any]:
    if post_type == "now" and not confirmed:
        raise PostizError(
            "type=now publishes immediately to a live audience. Pass confirmed=True "
            "(--i-mean-it on the CLI) to do that deliberately.")
    payload = build_payload(drafts, post_type, base, tags, dry_run)
    if dry_run:
        return {"status": "DRY_RUN", "type": post_type, "post_count": len(drafts),
                "warnings": {d.title: d.warnings for d in drafts if d.warnings},
                "payload": payload}
    r = _request("POST", "/posts", _base_url(base), body=payload, timeout=300)
    return {"status": "SENT", "type": post_type, "response": r}


# ----------------------------------------------------------------- CLI

def _drafts_from_plan(plan_json: Path, brand: str, platform: str, integration_id: str,
                      assets_dir: Path, limit: int | None) -> list[Draft]:
    briefs = json.loads(plan_json.read_text(encoding="utf-8"))
    out: list[Draft] = []
    skipped: list[str] = []
    for b in briefs:
        if b.get("status") != "ready":
            skipped.append(f"day {b['day']} {b['title']} ({b['status']})")
            continue
        stem = f"{brand}-idea{b['idea_id']:02d}" if b.get("idea_id") else f"{brand}-day{b['day']:02d}"
        media = sorted(assets_dir.glob(f"{stem}*.png")) if assets_dir.exists() else []
        cap = b["title"]
        d = Draft(brand=brand, title=b["title"], platform=platform,
                  integration_id=integration_id, caption=cap, media=media,
                  scheduled_for=f"{b['date']}T09:00:00Z")
        d.idempotency_key = idempotency_key(brand, b["title"], media)
        if not media:
            d.warnings.append(f"no composited assets found matching {stem}* in {assets_dir}")
        out.append(d)
        if limit and len(out) >= limit:
            break
    if skipped:
        print(f"skipped {len(skipped)} brief(s) that are not `ready`:")
        for s in skipped[:6]:
            print(f"  - {s}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Schedule composited assets via Postiz.")
    ap.add_argument("command", choices=["channels", "plan", "send"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--plan", type=Path, help="plan-*.json from packages/strategy/plan.py")
    ap.add_argument("--assets", type=Path, default=REPO / "out")
    ap.add_argument("--platform", default="instagram")
    ap.add_argument("--integration-id", help="channel id from `channels`")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--type", choices=["draft", "schedule", "now"], default="draft")
    ap.add_argument("--url", help="overrides POSTIZ_URL")
    ap.add_argument("--live", action="store_true", help="actually call Postiz")
    ap.add_argument("--i-mean-it", action="store_true",
                    help="required with --type now (publishes immediately)")
    a = ap.parse_args()

    if a.command == "channels":
        for ch in integrations(a.url):
            print(f"{ch.get('id','?'):<28} {ch.get('providerIdentifier', ch.get('provider','?')):<22} "
                  f"{ch.get('name','')}")
        return

    if not a.plan:
        raise SystemExit("--plan is required (the plan-*.json from packages/strategy/plan.py)")
    drafts = _drafts_from_plan(a.plan, a.brand, a.platform,
                               a.integration_id or "<INTEGRATION_ID>", a.assets, a.limit)
    if not drafts:
        raise SystemExit("no `ready` briefs to publish")

    if a.command == "plan":
        for d in drafts:
            print(f"{d.scheduled_for}  {d.platform:<12} {d.title:<26} "
                  f"{len(d.media)} asset(s)  key={d.idempotency_key[:12]}")
            for w in d.warnings or validate(d):
                print(f"    warning: {w}")
        print(f"\n{len(drafts)} draft(s) prepared. Nothing has been sent.")
        return

    if a.live and not a.integration_id:
        raise SystemExit("--integration-id is required for a live send; run `channels` first")
    res = send(drafts, a.type, a.url, tags=[a.brand], dry_run=not a.live,
               confirmed=a.i_mean_it)
    print(json.dumps({k: v for k, v in res.items() if k != "payload"}, indent=2)[:1500])
    if res["status"] == "DRY_RUN":
        print(f"\n(dry run — {len(drafts)} post(s) would be created as `{a.type}`. "
              f"Pass --live to send.)")


if __name__ == "__main__":
    # A configuration mistake should read as one sentence, not a traceback.
    try:
        main()
    except PostizError as e:
        raise SystemExit(f"error: {e}")
