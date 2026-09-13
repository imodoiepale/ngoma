"""Download the free workflow files creators link under their videos.

Reads `corpus/youtube/links.jsonl` (from link_miner.py) and fetches only rows marked
`fetchable`: a direct .json file on GitHub or HuggingFace. Everything else — Skool,
Patreon, Discord, Drive folders — is a human decision and is only listed.

Guards, each because the alternative fails quietly:
- host allowlist, https only: a description link is untrusted input;
- 5 MB cap: a "workflow" that large is not one;
- must parse as a ComfyUI graph, or it is recorded as rejected, not saved;
- nothing is executed; the file is data, registered with its hash and source URL.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import REPO  # noqa: E402

sys.path.insert(0, str(REPO / "packages" / "library" / "tools"))
from register_workflow import MANIFEST, NotAWorkflow, graph_nodes, register  # noqa: E402

LINKS = REPO / "packages" / "library" / "corpus" / "youtube" / "links.jsonl"
DEST = REPO / "workflows" / "creators"
ALLOWED_HOSTS = {"raw.githubusercontent.com", "github.com", "huggingface.co"}
MAX_BYTES = 5 * 1024 * 1024


class FetchRefused(ValueError):
    pass


def direct_url(url: str) -> str:
    """Blob pages -> raw bytes. Refuses anything outside the allowlist."""
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise FetchRefused(f"host not allowed: {u.hostname!r} ({url})")
    if not u.path.lower().endswith(".json"):
        raise FetchRefused(f"not a .json file: {url}")
    if u.hostname == "github.com":
        m = re.match(r"^/([^/]+)/([^/]+)/blob/(.+)$", u.path)
        if not m:
            raise FetchRefused(f"not a GitHub file link: {url}")
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    if u.hostname == "huggingface.co":
        return f"https://huggingface.co{u.path.replace('/blob/', '/resolve/', 1)}"
    return url


def _slug(url: str) -> str:
    name = Path(urlparse(url).path).stem
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "workflow"


def fetch_one(row: dict[str, Any], opener=urllib.request.urlopen) -> dict[str, Any]:
    url = direct_url(row["url"])
    req = urllib.request.Request(url, headers={"User-Agent": "epalle-studio/1.0"})
    with opener(req, timeout=60) as resp:
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise FetchRefused(f"larger than {MAX_BYTES} bytes: {url}")
    try:
        graph_nodes(json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise NotAWorkflow(f"not JSON: {e}") from e
    sha = hashlib.sha256(raw).hexdigest()
    have = next((w["canonical"] for w in json.loads(MANIFEST.read_text(encoding="utf-8"))["workflows"]
                 if w["sha256"] == sha), None)
    if have:
        # The same bytes under a second path split one workflow into two graph nodes.
        return {"status": "already_have", "path": have, "packs": [], "unattributed": []}
    dest = DEST / row["channel"] / f"{row['video_id']}-{_slug(url)}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    entry = register(dest, [row["url"]])
    return {"status": "saved", "path": entry["canonical"], "packs": entry["node_packs"],
            "unattributed": entry.get("unattributed_node_types", [])}


def main() -> int:
    if not LINKS.exists():
        print("links.jsonl missing — run packages/ingest/link_miner.py first")
        return 2
    rows = [json.loads(line) for line in LINKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    todo = [r for r in rows if r.get("fetchable")]
    seen, report = set(), []
    for r in todo:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        try:
            res = fetch_one(r)
        except (FetchRefused, NotAWorkflow) as e:
            res = {"status": "rejected", "reason": str(e)}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            res = {"status": "failed", "reason": f"{type(e).__name__}: {e}"}
        report.append({"url": r["url"], "channel": r["channel"], "video_id": r["video_id"], **res})
        print(f"{res['status']:<9} {r['channel']:<18} {r['url'][:90]}")
    out = REPO / "packages" / "library" / "corpus" / "youtube" / "workflow-fetch-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {s: sum(1 for x in report if x["status"] == s) for s in ("saved", "rejected", "failed")}
    paid = sum(1 for r in rows if r.get("paid"))
    print(f"\n{counts} of {len(report)} free workflow links; {paid} paid links listed, not fetched")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
