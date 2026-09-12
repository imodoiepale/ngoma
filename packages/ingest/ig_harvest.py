"""Instagram reference harvester.

Fills the gap that `packages/library/tools/source_watch.py` honestly reports as
`not_enumerable`: it cannot list a profile's posts. OpenCLI can, because it drives a real
logged-in browser session rather than hitting an unauthenticated endpoint.

Route: agent-reach -> OpenCLI instagram adapter
    opencli instagram profile <user> -f json      # profile facts
    opencli instagram user <user> --limit N -f json   # recent posts
    opencli instagram download <url> --path DIR -f json

Scope discipline, inherited from the existing watcher:
  * public profiles only
  * no follow/like/comment/post — this module never calls a [write] subcommand
  * when enumeration is unavailable, record `not_enumerable` rather than working around it
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import (  # noqa: E402
    REPO, HarvestReport, MediaRef, Post, extract_hashtags, sha256_file, write_posts, write_report,
)

WRITE_SUBCOMMANDS = {
    "follow", "unfollow", "like", "unlike", "comment", "post", "note",
    "save", "unsave", "story", "login", "collection-create", "collection-delete",
}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
VID_EXT = {".mp4", ".mov", ".webm"}


class HarvestError(RuntimeError):
    pass


def _opencli(*args: str, timeout: int = 240) -> Any:
    """Run a READ-ONLY opencli instagram subcommand and parse JSON."""
    if args and args[0] in WRITE_SUBCOMMANDS:
        raise HarvestError(f"refusing to run write subcommand {args[0]!r}; this module is read-only")
    cmd = ["opencli", "instagram", *args, "-f", "json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        raise HarvestError("opencli is not on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise HarvestError(f"opencli timed out after {timeout}s: {' '.join(cmd)}") from e
    if r.returncode != 0:
        raise HarvestError(f"opencli failed ({r.returncode}): {(r.stderr or r.stdout).strip()[:400]}")
    out = r.stdout.strip()
    if not out:
        raise HarvestError(f"opencli returned nothing for: {' '.join(cmd)}")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        m = re.search(r"(\[.*\]|\{.*\})", out, re.S)
        if not m:
            raise HarvestError(f"could not parse opencli output: {out[:300]}")
        return json.loads(m.group(1))


def backend_ready() -> tuple[bool, str]:
    """Ask agent-reach whether the Instagram backend is actually live."""
    try:
        r = subprocess.run(["agent-reach", "doctor", "--json"],
                           capture_output=True, text=True, timeout=90,
                           encoding="utf-8", errors="replace")
        d = json.loads(r.stdout or "{}")["instagram"]
    except Exception as e:  # noqa: BLE001 - doctor is advisory; never fatal
        return False, f"could not run agent-reach doctor: {e}"
    ok = d.get("status") == "ok" and d.get("active_backend")
    return bool(ok), d.get("message", "")


def _shortcode(url: str) -> str:
    m = re.search(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else (url or "").rstrip("/").rsplit("/", 1)[-1]


def _kind(paths: list[Path], declared: str | None) -> str:
    if declared:
        d = declared.lower()
        if "carousel" in d or "sidecar" in d:
            return "carousel"
        if "video" in d or "reel" in d:
            return "video"
        if "image" in d or "photo" in d:
            return "image"
    if len(paths) > 1:
        return "carousel"
    if paths and paths[0].suffix.lower() in VID_EXT:
        return "video"
    if paths:
        return "image"
    return "unknown"


def harvest(handle: str, brand: str = "ongea-pesa", limit: int = 12,
            download: bool = True, dry_run: bool = False) -> HarvestReport:
    handle = handle.lstrip("@")
    out_root = REPO / "brands" / brand / "references" / handle
    media_dir = out_root / "media"
    report = HarvestReport(platform="instagram", target=handle, status="ok",
                           requested=limit, enumerated=0, downloaded=0, skipped_existing=0)

    ready, msg = backend_ready()
    if not ready:
        report.status = "not_enumerable"
        report.notes.append(
            "Instagram backend is not live. OpenCLI drives a real browser session, so the "
            "OpenCLI extension must be enabled in Chrome/Edge and logged in to instagram.com. "
            f"agent-reach says: {msg}"
        )
        if not dry_run:
            write_report(out_root / "harvest-report.json", report)
        return report

    if dry_run:
        report.notes.append(f"dry run — would enumerate {limit} posts from @{handle}")
        return report

    try:
        profile = _opencli("profile", handle)
        (out_root / "profile.json").parent.mkdir(parents=True, exist_ok=True)
        (out_root / "profile.json").write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    except HarvestError as e:
        report.notes.append(f"profile fetch failed (continuing): {e}")

    try:
        rows = _opencli("user", handle, "--limit", str(limit))
    except HarvestError as e:
        report.status = "failed"
        report.failures.append({"stage": "enumerate", "error": str(e)})
        write_report(out_root / "harvest-report.json", report)
        return report

    if isinstance(rows, dict):
        rows = rows.get("posts") or rows.get("items") or rows.get("data") or []
    report.enumerated = len(rows)
    if report.enumerated < limit:
        report.status = "partial"
        report.notes.append(
            f"only {report.enumerated} of {limit} requested posts were visible; "
            "Instagram limits what a session can enumerate")

    posts: list[Post] = []
    for row in rows:
        url = row.get("url") or row.get("link") or row.get("permalink") or ""
        code = _shortcode(url) or str(row.get("id") or row.get("index"))
        caption = row.get("caption") or row.get("text")
        media: list[MediaRef] = []
        notes: list[str] = []

        if download and url:
            dest = media_dir / code
            if dest.exists() and any(dest.iterdir()):
                report.skipped_existing += 1
            else:
                try:
                    dest.mkdir(parents=True, exist_ok=True)
                    _opencli("download", url, "--path", str(dest), timeout=420)
                    report.downloaded += 1
                except HarvestError as e:
                    notes.append(f"download failed: {e}")
                    report.failures.append({"stage": "download", "shortcode": code, "error": str(e)})
            files = sorted(
                f for f in dest.rglob("*")
                if f.is_file() and f.suffix.lower() in IMG_EXT | VID_EXT
            ) if dest.exists() else []
            for f in files:
                media.append(MediaRef(
                    path=str(f.relative_to(REPO)).replace("\\", "/"),
                    sha256=sha256_file(f), bytes=f.stat().st_size,
                    kind="video" if f.suffix.lower() in VID_EXT else "image",
                ))
        else:
            files = []

        posts.append(Post(
            platform="instagram", source_id=code, url=url, author=handle,
            caption=caption, posted_at=row.get("date") or row.get("taken_at"),
            kind=_kind([Path(m.path) for m in media], row.get("type")),
            likes=_int(row.get("likes")), comments=_int(row.get("comments")),
            hashtags=extract_hashtags(caption), media=media, notes=notes,
        ))

    added = write_posts(out_root / "posts.jsonl", posts)
    report.notes.append(f"{added} new post records written")
    write_report(out_root / "harvest-report.json", report)
    return report


def _int(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip().replace(",", "").lower()
    mult = {"k": 1_000, "m": 1_000_000}.get(s[-1:], 1)
    if mult > 1:
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Harvest public Instagram reference posts.")
    ap.add_argument("handles", nargs="+", help="one or more public IG handles")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--no-download", action="store_true", help="metadata only")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    print("Using agent-reach route: Instagram via the OpenCLI adapter (read-only).")
    rc = 0
    for h in a.handles:
        rep = harvest(h, a.brand, a.limit, download=not a.no_download, dry_run=a.dry_run)
        print(rep.summary())
        for n in rep.notes:
            print(f"    note: {n}")
        for f in rep.failures[:5]:
            print(f"    FAIL {f}")
        if rep.status in ("failed", "not_enumerable"):
            rc = 1
    raise SystemExit(rc)


if __name__ == "__main__":
    _cli()
