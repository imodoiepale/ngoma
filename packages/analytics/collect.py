"""Analytics ingestion — pull real performance data and normalise it.

Two sources, one shape:

  * **Postiz** `GET /public/v1/posts` — what was published, when, to which integration.
    It knows the schedule but carries little performance data.
  * **Instagram Graph API** `/{ig-user-id}/media` + `/{media-id}/insights` — the numbers
    that matter: reach, saves, shares, watch time, profile visits.

Both need credentials that do not exist yet, so this module also has a **fixture mode**.
That is not a shortcut around testing — it is the only way to exercise the attribution and
learning loop before a single post is live, and every fact it produces is tagged
`source: fixture` so it can never be mistaken for measured reality.

Normalised metric names, because the two APIs disagree with each other and with themselves:

    impressions reach likes comments saves shares video_views watch_time_s
    profile_visits follows engagement_rate

`engagement_rate` is computed here as (likes+comments+saves+shares)/reach, not taken from a
provider, because providers define it differently and a number you cannot reproduce is a
number you cannot compare.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "memory"))

GRAPH = "https://graph.facebook.com/v21.0"

METRICS = ["impressions", "reach", "likes", "comments", "saves", "shares",
           "video_views", "watch_time_s", "profile_visits", "follows"]

# Instagram renamed several of these across API versions and still returns a mix.
IG_ALIASES = {
    "impressions": "impressions", "reach": "reach", "likes": "likes",
    "comments": "comments", "saved": "saves", "saves": "saves", "shares": "shares",
    "video_views": "video_views", "plays": "video_views",
    "ig_reels_video_view_total_time": "watch_time_s",
    "ig_reels_avg_watch_time": "watch_time_s",
    "profile_visits": "profile_visits", "follows": "follows",
    "total_interactions": None,   # deliberately dropped: we compute engagement ourselves
}


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


class AnalyticsError(RuntimeError):
    pass


@dataclass
class PostMetrics:
    brand: str
    post_id: str
    platform: str
    published_at: str
    permalink: str | None = None
    media_type: str | None = None
    caption_hash: str | None = None
    campaign_id: str | None = None
    brief_day: int | None = None
    style_key: str | None = None
    lane: str | None = None
    varies: str | None = None
    parent_id: int | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    source: str = "unknown"

    @property
    def engagement_rate(self) -> float | None:
        m, reach = self.metrics, self.metrics.get("reach") or self.metrics.get("impressions")
        if not reach:
            return None
        inter = sum(m.get(k, 0) for k in ("likes", "comments", "saves", "shares"))
        return round(inter / reach, 4)


# ------------------------------------------------------------------ Instagram

def _get(url: str, params: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": "epalle-studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        if e.code in (400, 403):
            raise AnalyticsError(
                f"Instagram rejected the request ({e.code}). Usual causes: the account is "
                f"not a Professional account linked to a Facebook Page, the token lacks "
                f"instagram_manage_insights, or the app is still in development mode. "
                f"Graph said: {body}") from e
        raise AnalyticsError(f"Graph API {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise AnalyticsError(f"could not reach the Graph API: {e.reason}") from e


def instagram_media(ig_user_id: str, token: str, limit: int = 25) -> list[dict[str, Any]]:
    r = _get(f"{GRAPH}/{ig_user_id}/media",
             {"fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count",
              "limit": limit, "access_token": token})
    return r.get("data", [])


def instagram_insights(media_id: str, token: str, media_type: str) -> dict[str, float]:
    wanted = "reach,saved,shares" if media_type != "VIDEO" else \
             "reach,saved,shares,video_views,ig_reels_video_view_total_time"
    try:
        r = _get(f"{GRAPH}/{media_id}/insights",
                 {"metric": wanted, "access_token": token})
    except AnalyticsError:
        return {}          # insights are unavailable for older or non-eligible media
    out: dict[str, float] = {}
    for row in r.get("data", []):
        key = IG_ALIASES.get(row.get("name", ""))
        if not key:
            continue
        vals = row.get("values") or [{}]
        v = vals[0].get("value")
        if isinstance(v, (int, float)):
            out[key] = float(v) / (1000.0 if key == "watch_time_s" else 1.0)
    return out


def collect_instagram(brand: str, limit: int = 25) -> list[PostMetrics]:
    token = _secret("IG_ACCESS_TOKEN")
    ig_id = _secret("IG_USER_ID")
    if not (token and ig_id):
        raise AnalyticsError(
            "IG_ACCESS_TOKEN and IG_USER_ID are not set. Both come from a Meta app with an "
            "Instagram Professional account linked to a Facebook Page — see "
            "infra/postiz/README.md. Use --fixture to exercise the loop without them.")
    out = []
    for m in instagram_media(ig_id, token, limit):
        pm = PostMetrics(
            brand=brand, post_id=m["id"], platform="instagram",
            published_at=m.get("timestamp", ""), permalink=m.get("permalink"),
            media_type=m.get("media_type"), source="instagram_graph",
            caption_hash=hashlib.sha256((m.get("caption") or "").encode()).hexdigest()[:16],
            metrics={"likes": float(m.get("like_count") or 0),
                     "comments": float(m.get("comments_count") or 0)})
        pm.metrics.update(instagram_insights(m["id"], token, m.get("media_type", "IMAGE")))
        out.append(pm)
    return out


# ------------------------------------------------------------------ Postiz

def collect_postiz(brand: str, limit: int = 50) -> list[PostMetrics]:
    sys.path.insert(0, str(REPO / "packages" / "publish"))
    from postiz import _base_url, _request  # noqa: PLC0415

    week = (date.today() - timedelta(days=30)).isoformat()
    r = _request("GET", f"/posts?startDate={week}", _base_url())
    rows = r if isinstance(r, list) else r.get("posts", [])
    out = []
    for p in rows[:limit]:
        out.append(PostMetrics(
            brand=brand, post_id=str(p.get("id")), platform=str(
                (p.get("integration") or {}).get("providerIdentifier", "unknown")),
            published_at=str(p.get("publishDate") or p.get("createdAt") or ""),
            source="postiz", metrics={}))
    return out


# ------------------------------------------------------------------ fixture

def collect_fixture(brand: str, plan_json: Path, seed: int = 11) -> list[PostMetrics]:
    """Synthesise plausible performance for a real plan.

    Every record is tagged `source: fixture`. This exists so the attribution and learning
    loop can be exercised and debugged before a single post is live — not to stand in for
    measurement. Nothing derived from it should ever be reported as a result.

    The generator has a deliberate structure so attribution has something real to find:
    meme and accessibility grammars over-perform on saves, single-image posts under-perform
    on reach, and a mild recency decay is applied. If the analysis cannot recover those,
    the analysis is broken.
    """
    rng = random.Random(seed)
    briefs = json.loads(plan_json.read_text(encoding="utf-8"))
    boost = {"kenyan_meme_original": 1.45, "accessibility_story": 1.30,
             "chama_community_story": 1.18, "data_magazine_graphic": 0.92,
             "luxury_fashion_campaign": 0.80}
    out = []
    for b in briefs:
        if b.get("status") != "ready":
            continue
        k = boost.get(b["style_key"], 1.0)
        fmt_k = {"reel": 1.6, "carousel": 1.1, "single": 0.85}.get(b["format"], 1.0)
        reach = max(200, int(rng.gauss(2400, 600) * k * fmt_k))
        er = max(0.005, rng.gauss(0.042, 0.012) * k)
        inter = int(reach * er)
        saves = int(inter * rng.uniform(0.18, 0.42) * (1.4 if k > 1.2 else 1.0))
        m = {"reach": float(reach), "impressions": float(int(reach * rng.uniform(1.1, 1.5))),
             "likes": float(int(inter * 0.62)), "comments": float(int(inter * 0.11)),
             "saves": float(saves), "shares": float(int(inter * 0.09)),
             "profile_visits": float(int(reach * rng.uniform(0.01, 0.04))),
             "follows": float(int(reach * rng.uniform(0.001, 0.006)))}
        if b["format"] == "reel":
            m["video_views"] = float(int(reach * rng.uniform(1.2, 2.0)))
            m["watch_time_s"] = round(rng.uniform(3.5, 11.0), 1)
        out.append(PostMetrics(
            brand=brand, post_id=f"fixture-{b['day']:02d}", platform="instagram",
            published_at=f"{b['date']}T09:00:00Z", media_type=b["format"].upper(),
            campaign_id=f"{brand}-idea{b['idea_id']:02d}" if b.get("idea_id") else None,
            brief_day=b["day"], style_key=b["style_key"], lane=b["lane"],
            varies=b.get("varies"), parent_id=b.get("parent_id"),
            metrics=m, source="fixture"))
    return out


# ------------------------------------------------------------------ attribution

def attach_briefs(posts: list[PostMetrics], plan_json: Path) -> int:
    """Link real posts back to the brief that produced them, via campaign id."""
    briefs = {}
    for b in json.loads(plan_json.read_text(encoding="utf-8")):
        if b.get("idea_id"):
            briefs[f"idea{b['idea_id']:02d}"] = b
    n = 0
    for p in posts:
        key = next((k for k in briefs if p.campaign_id and k in p.campaign_id), None)
        if not key:
            continue
        b = briefs[key]
        p.brief_day, p.style_key, p.lane = b["day"], b["style_key"], b["lane"]
        p.varies, p.parent_id = b.get("varies"), b.get("parent_id")
        n += 1
    return n


def save(posts: list[PostMetrics], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        for p in posts:
            d = asdict(p)
            d["engagement_rate"] = p.engagement_rate
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect post performance into a normalised file.")
    ap.add_argument("source", choices=["instagram", "postiz", "fixture"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--plan", type=Path, help="plan-*.json, for attribution / fixture shape")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    if a.source == "fixture":
        if not a.plan:
            raise SystemExit("--plan is required for fixture mode")
        posts = collect_fixture(a.brand, a.plan, a.seed)
        print(f"NOTE: {len(posts)} SYNTHETIC records. Tagged source=fixture so nothing "
              f"downstream can mistake them for measurement.")
    elif a.source == "instagram":
        posts = collect_instagram(a.brand, a.limit)
        if a.plan:
            print(f"attributed {attach_briefs(posts, a.plan)}/{len(posts)} posts to briefs")
    else:
        posts = collect_postiz(a.brand, a.limit)

    out = a.out or REPO / "out" / "analytics" / f"{a.brand}-{a.source}.jsonl"
    save(posts, out)
    if posts:
        er = [p.engagement_rate for p in posts if p.engagement_rate is not None]
        reach = [p.metrics.get("reach", 0) for p in posts]
        print(f"{len(posts)} post(s) -> {out}")
        if er:
            print(f"engagement rate: median {sorted(er)[len(er)//2]:.3f}  "
                  f"range {min(er):.3f}-{max(er):.3f}")
        if any(reach):
            print(f"reach: median {sorted(reach)[len(reach)//2]:.0f}")
    else:
        print("no posts returned")


if __name__ == "__main__":
    try:
        main()
    except AnalyticsError as e:
        raise SystemExit(f"error: {e}")
