"""Pinterest reference harvester.

Seed input is `brands/<brand>/references/pinterest-seed.txt` — the 56 pin URLs you
collected (blank lines and duplicates tolerated). Boards and search URLs also work.

Backend: gallery-dl, which handles Pinterest pins, boards and sections natively and can
reuse a browser cookie jar for anything that needs a session. Installed on demand with
`uv tool install gallery-dl`.

Output is the same `posts.jsonl` shape as the Instagram harvester, deduped on image
sha256 so the same pin saved twice does not become two references.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import (  # noqa: E402
    REPO, HarvestReport, MediaRef, Post, sha256_file, write_posts, write_report,
)

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VID_EXT = {".mp4", ".m3u8", ".mov"}
PIN_RE = re.compile(r"pinterest\.[a-z.]+/pin/(\d+)", re.I)


class PinError(RuntimeError):
    pass


def gallery_dl_available() -> bool:
    return shutil.which("gallery-dl") is not None


def install_hint() -> str:
    return "gallery-dl is not installed. Install it with:  uv tool install gallery-dl"


def read_seed(path: Path) -> list[str]:
    if not path.exists():
        raise PinError(f"seed file not found: {path}")
    urls, seen = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        u = line.strip()
        if not u or u.startswith("#"):
            continue
        u = u.replace("http://", "https://")
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
    return urls


def _pin_id(url: str) -> str:
    m = PIN_RE.search(url)
    return m.group(1) if m else url.rstrip("/").rsplit("/", 1)[-1]


def _run_gallery_dl(url: str, dest: Path, cookies_from: str | None, timeout: int = 300) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["gallery-dl", "--dest", str(dest), "--write-metadata", "--no-part"]
    if cookies_from:
        cmd += ["--cookies-from-browser", cookies_from]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        raise PinError(f"gallery-dl timed out after {timeout}s on {url}") from e
    if r.returncode != 0:
        raise PinError(f"gallery-dl failed ({r.returncode}) on {url}: "
                       f"{(r.stderr or r.stdout).strip()[:300]}")
    return {"stdout": r.stdout, "stderr": r.stderr}


def _collect_media(dest: Path) -> list[Path]:
    if not dest.exists():
        return []
    return sorted(f for f in dest.rglob("*")
                  if f.is_file() and f.suffix.lower() in IMG_EXT | VID_EXT)


def _sidecar(f: Path) -> dict[str, Any]:
    for cand in (f.with_suffix(f.suffix + ".json"), f.with_suffix(".json")):
        if cand.exists():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    return {}


def harvest(urls: Iterable[str], brand: str = "ongea-pesa", collection: str = "pinterest",
            cookies_from: str | None = None, dry_run: bool = False) -> HarvestReport:
    urls = list(urls)
    out_root = REPO / "brands" / brand / "references" / collection
    report = HarvestReport(platform="pinterest", target=f"{len(urls)} urls", status="ok",
                           requested=len(urls), enumerated=len(urls),
                           downloaded=0, skipped_existing=0)

    if not gallery_dl_available():
        report.status = "blocked"
        report.notes.append(install_hint())
        if not dry_run:
            write_report(out_root / "harvest-report.json", report)
        return report

    if dry_run:
        report.notes.append(f"dry run — would fetch {len(urls)} pins into {out_root}")
        return report

    seen_hashes: set[str] = set()
    existing = out_root / "posts.jsonl"
    if existing.exists():
        for line in existing.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    for m in json.loads(line).get("media", []):
                        seen_hashes.add(m["sha256"])
                except (json.JSONDecodeError, KeyError):
                    pass

    posts: list[Post] = []
    for url in urls:
        pid = _pin_id(url)
        dest = out_root / "media" / pid
        if dest.exists() and _collect_media(dest):
            report.skipped_existing += 1
        else:
            try:
                _run_gallery_dl(url, dest, cookies_from)
                report.downloaded += 1
            except PinError as e:
                report.failures.append({"url": url, "error": str(e)})
                continue

        media, notes = [], []
        meta: dict[str, Any] = {}
        for f in _collect_media(dest):
            h = sha256_file(f)
            if h in seen_hashes:
                notes.append(f"duplicate image content, already referenced: {f.name}")
                continue
            seen_hashes.add(h)
            meta = meta or _sidecar(f)
            media.append(MediaRef(
                path=str(f.relative_to(REPO)).replace("\\", "/"),
                sha256=h, bytes=f.stat().st_size,
                kind="video" if f.suffix.lower() in VID_EXT else "image",
            ))
        if not media and not notes:
            report.failures.append({"url": url, "error": "no media files produced"})
            continue

        posts.append(Post(
            platform="pinterest", source_id=pid, url=url,
            author=(meta.get("pinner") or {}).get("username") if isinstance(meta.get("pinner"), dict) else meta.get("uploader"),
            caption=meta.get("description") or meta.get("grid_title") or meta.get("title"),
            posted_at=meta.get("created_at"),
            kind="video" if any(m.kind == "video" for m in media) else "image",
            media=media, notes=notes,
        ))

    if report.failures:
        report.status = "partial" if posts else "failed"
    added = write_posts(out_root / "posts.jsonl", posts)
    report.notes.append(f"{added} new pin records written")
    write_report(out_root / "harvest-report.json", report)
    return report


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Harvest Pinterest reference pins.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--seed", type=Path, default=None,
                    help="defaults to brands/<brand>/references/pinterest-seed.txt")
    ap.add_argument("--url", action="append", default=[], help="extra pin/board/search URL")
    ap.add_argument("--collection", default="pinterest")
    ap.add_argument("--cookies-from", help="browser for gallery-dl --cookies-from-browser (chrome, edge, firefox)")
    ap.add_argument("--limit", type=int, help="cap how many seed URLs to process")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    seed = a.seed or REPO / "brands" / a.brand / "references" / "pinterest-seed.txt"
    urls = read_seed(seed) if seed.exists() else []
    urls += a.url
    if a.limit:
        urls = urls[:a.limit]
    if not urls:
        raise SystemExit(f"no URLs — checked {seed} and --url")

    print(f"{len(urls)} unique Pinterest URLs from {seed.name}")
    rep = harvest(urls, a.brand, a.collection, a.cookies_from, a.dry_run)
    print(rep.summary())
    for n in rep.notes:
        print(f"    note: {n}")
    for f in rep.failures[:8]:
        print(f"    FAIL {f['url']}: {f['error'][:120]}")
    raise SystemExit(0 if rep.status in ("ok", "partial") else 1)


if __name__ == "__main__":
    _cli()
