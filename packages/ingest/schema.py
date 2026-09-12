"""Shared reference-asset schema.

Every harvester (Instagram, Pinterest, YouTube) writes the same `posts.jsonl` shape so
`packages/vision` and `packages/strategy` never need to know where an asset came from.

Schema precedent: libraries/manifests/fanuel-leul-public-profile.json, which models
`archive_status` / `media_status` honestly rather than pretending full coverage.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

REPO = Path(__file__).resolve().parents[2]

Platform = Literal["instagram", "pinterest", "youtube"]
MediaKind = Literal["image", "video", "carousel", "unknown"]
Status = Literal["ok", "partial", "not_enumerable", "blocked", "failed"]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class MediaRef:
    path: str                 # repo-relative
    sha256: str
    bytes: int
    kind: MediaKind
    width: int | None = None
    height: int | None = None


@dataclass
class Post:
    platform: Platform
    source_id: str            # shortcode / pin id / video id
    url: str
    author: str | None = None
    caption: str | None = None
    posted_at: str | None = None
    kind: MediaKind = "unknown"
    likes: int | None = None
    comments: int | None = None
    hashtags: list[str] = field(default_factory=list)
    media: list[MediaRef] = field(default_factory=list)
    harvested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class HarvestReport:
    platform: Platform
    target: str
    status: Status
    requested: int
    enumerated: int
    downloaded: int
    skipped_existing: int
    failures: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def summary(self) -> str:
        return (f"[{self.platform}] {self.target}: {self.status} - "
                f"enumerated {self.enumerated}/{self.requested}, "
                f"downloaded {self.downloaded}, skipped {self.skipped_existing}, "
                f"failed {len(self.failures)}")


def write_posts(path: Path, posts: Iterable[Post], append: bool = True) -> int:
    """Append posts to a .jsonl, deduping on (platform, source_id)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[tuple[str, str]] = set()
    if append and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                existing.add((r["platform"], r["source_id"]))
            except (json.JSONDecodeError, KeyError):
                continue
    n = 0
    with path.open("a" if append else "w", encoding="utf-8") as fh:
        for p in posts:
            if (p.platform, p.source_id) in existing:
                continue
            fh.write(p.to_json() + "\n")
            existing.add((p.platform, p.source_id))
            n += 1
    return n


def write_report(path: Path, report: HarvestReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")


def extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    import re
    return sorted({m.lower() for m in re.findall(r"#(\w{2,50})", text)})
