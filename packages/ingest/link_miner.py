"""Classify every link creators put under their videos.

A creator's description is where the business model shows: the free workflow on GitHub,
the paid Skool community, the RunPod referral, the affiliate link to the tool being
reviewed. `yt_learn` already saves each video's `.description` and `info.json`; this reads
those files (no network) and writes one row per link:

    {"video_id", "channel", "title", "url", "kind", "paid", "fetchable"}

`paid` means the link leads to something behind a paywall or membership. `fetchable` means
a free, direct workflow file that `workflow_fetch.py` may download. Paywalled material is
listed so a human can decide to buy it; it is never scraped.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import REPO  # noqa: E402

CORPUS = REPO / "packages" / "library" / "corpus" / "youtube"
OUT = CORPUS / "links.jsonl"

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")

# Rules match the HOSTNAME (and, where stated, the path). Matching the whole URL string let
# "https://youtu.be/x" and "https://huggingface.co/..." fall through to tool_or_site, because
# an anchored "(^|\.)host" never matches after "https://".
# (kind, hostname regex, path regex or None, paid) — first match wins.
RULES: list[tuple[str, str, str | None, bool]] = [
    ("workflow_json", r"^raw\.githubusercontent\.com$", r"\.json$", False),
    ("workflow_json", r"^github\.com$", r"^/[^/]+/[^/]+/blob/.+\.json$", False),
    ("workflow_json", r"^huggingface\.co$", r"/(resolve|blob)/.+\.json$", False),
    ("skool", r"(^|\.)skool\.com$", None, True),
    ("patreon", r"(^|\.)patreon\.com$", None, True),
    ("whop", r"(^|\.)whop\.com$", None, True),
    ("gumroad", r"(^|\.)(gumroad\.com|gum\.co)$", None, True),
    ("lemonsqueezy", r"(^|\.)lemonsqueezy\.com$", None, True),
    ("kofi", r"(^|\.)ko-fi\.com$", None, False),
    ("discord", r"(^|\.)(discord\.gg|discord\.com)$", None, False),
    ("runpod_referral", r"(^|\.)runpod\.io$", None, False),
    ("model_file", r"^(huggingface\.co|dl\.fbaipublicfiles\.com)$",
     r"\.(safetensors|pt|pth|ckpt|gguf|onnx|bin)$", False),
    ("github_repo", r"^github\.com$", r"^/[^/]+/[^/]+", False),
    ("huggingface", r"^huggingface\.co$", None, False),
    ("civitai", r"(^|\.)civitai\.(com|green)$", None, False),
    ("openart", r"(^|\.)openart\.ai$", None, False),
    ("drive", r"^(drive\.google\.com|docs\.google\.com|(www\.)?dropbox\.com|mega\.nz)$", None, False),
    ("pastebin", r"(^|\.)pastebin\.com$", None, False),
    ("social", r"(^|\.)(instagram\.com|tiktok\.com|x\.com|twitter\.com|linkedin\.com|"
               r"facebook\.com|threads\.net)$", None, False),
    ("youtube", r"(^|\.)(youtube\.com|youtu\.be)$", None, False),
    ("docs", r"^docs\.|(^|\.)readthedocs\.io$", None, False),
]
_COMPILED = [(k, re.compile(h, re.I), re.compile(p, re.I) if p else None, paid)
             for k, h, p, paid in RULES]
AFFILIATE_QS = re.compile(r"(^|&)(ref|via|aff|affiliate|fpr|coupon|utm_source|referral)=", re.I)
AFFILIATE_PATH = re.compile(r"/(ref|aff|a)/|^/x[0-9a-z]{6,}$", re.I)


def classify(url: str) -> tuple[str, bool]:
    """(kind, paid). Anything unmatched is `tool_or_site` — usually the product reviewed."""
    u = urlparse(url.rstrip(".,;:!"))
    host, path = (u.hostname or "").lower(), u.path or "/"
    for kind, hpat, ppat, paid in _COMPILED:
        if hpat.search(host) and (ppat is None or ppat.search(path)):
            return kind, paid
    if AFFILIATE_QS.search(u.query or "") or AFFILIATE_PATH.search(path):
        return "affiliate", False
    return "tool_or_site", False


def _video_records() -> list[dict[str, Any]]:
    out = []
    for info in sorted(CORPUS.glob("*/subs/*.info.json")):
        channel = info.parent.parent.name
        try:
            meta = json.loads(info.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        vid = meta.get("id") or info.name.split(".")[0]
        desc = meta.get("description")
        if not desc:
            d = info.with_name(f"{vid}.description")
            desc = d.read_text(encoding="utf-8", errors="replace") if d.exists() else ""
        out.append({"video_id": vid, "channel": channel, "title": meta.get("title"),
                    "view_count": meta.get("view_count"), "description": desc or ""})
    # videos mined before info.json slimming may only have a .description
    seen = {r["video_id"] for r in out}
    for d in sorted(CORPUS.glob("*/subs/*.description")):
        vid = d.name.split(".")[0]
        if vid not in seen:
            out.append({"video_id": vid, "channel": d.parent.parent.name, "title": None,
                        "view_count": None,
                        "description": d.read_text(encoding="utf-8", errors="replace")})
    return out


def mine_links() -> list[dict[str, Any]]:
    rows, seen = [], set()
    for rec in _video_records():
        for url in URL_RE.findall(rec["description"]):
            url = url.rstrip(".,;:!")
            key = (rec["video_id"], url)
            if key in seen:
                continue
            seen.add(key)
            kind, paid = classify(url)
            rows.append({"video_id": rec["video_id"], "channel": rec["channel"],
                         "title": rec["title"], "url": url, "kind": kind, "paid": paid,
                         "fetchable": kind == "workflow_json"})
    return rows


def main() -> None:
    rows = mine_links()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    by = defaultdict(Counter)
    for r in rows:
        by[r["channel"]][r["kind"]] += 1
    print(f"{len(rows)} links -> {OUT.relative_to(REPO)}")
    for ch, c in sorted(by.items()):
        print(f"  {ch:<20} " + ", ".join(f"{k} {n}" for k, n in c.most_common()))


if __name__ == "__main__":
    main()
