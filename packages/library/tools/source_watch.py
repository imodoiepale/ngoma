#!/usr/bin/env python3
"""Daily source watch for the EPALLE research archive.

Consumes manifests/monitored-sources.json, finds material that is not already in the
archive, downloads it with the vendored yt-dlp, rebuilds the search index, and writes a
run report.

Reports only changes. A watcher that says "nothing new" every day trains you to ignore
it, so a quiet run exits 0 and prints one line.

Usage:
    python source_watch.py --check      # list what is new, download nothing
    python source_watch.py              # download new items and reindex
    python source_watch.py --no-index   # download but skip the index rebuild
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
LIB = TOOLS.parent
MANIFEST = LIB / "manifests" / "monitored-sources.json"
COMPLETE = LIB / "manifests" / "video-complete.txt"
VIDEO_DIR = LIB / "videos"
REPORT_DIR = LIB / "manifests" / "watch-reports"
YTDLP = TOOLS / "yt-dlp"

# yt-dlp is vendored as a source checkout, so it runs as a module from that directory.
YTDLP_CMD = [sys.executable, "-m", "yt_dlp"]
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def have_ytdlp() -> bool:
    probe = subprocess.run(
        YTDLP_CMD + ["--version"], cwd=YTDLP, capture_output=True, text=True
    )
    return probe.returncode == 0


def known_ids() -> set[str]:
    """Everything already archived: the completion list plus what is on disk."""
    ids: set[str] = set()
    if COMPLETE.exists():
        for line in COMPLETE.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts and ID_RE.match(parts[-1]):
                ids.add(parts[-1])
    if VIDEO_DIR.exists():
        for child in VIDEO_DIR.iterdir():
            if child.is_dir() and ID_RE.match(child.name):
                ids.add(child.name)
    return ids


def list_remote(url: str, scope: str) -> list[dict]:
    """Enumerate a source without downloading. Flat playlist keeps this cheap."""
    args = YTDLP_CMD + ["--flat-playlist", "--dump-single-json", "--ignore-errors"]
    # For a single video we still want its uploader context, but not the whole channel.
    if scope == "all_new_public_videos":
        args += ["--playlist-end", "50"]
    args.append(url)
    probe = subprocess.run(args, cwd=YTDLP, capture_output=True, text=True, timeout=600)
    if probe.returncode != 0 and not probe.stdout.strip():
        raise RuntimeError((probe.stderr or "yt-dlp failed").strip()[:400])

    try:
        payload = json.loads(probe.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse yt-dlp output: {exc}") from exc

    entries = payload.get("entries")
    if entries is None:
        entries = [payload]
    items = []
    for entry in entries:
        if not entry:
            continue
        vid = entry.get("id") or ""
        if not ID_RE.match(vid):
            continue
        items.append({
            "id": vid,
            "title": entry.get("title") or "",
            "url": entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        })
    return items


def download(video_id: str, url: str) -> tuple[bool, str]:
    target = VIDEO_DIR / video_id
    target.mkdir(parents=True, exist_ok=True)
    args = YTDLP_CMD + [
        "--paths", str(target),
        "--output", "%(title)s [%(id)s].%(ext)s",
        "--format", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--write-info-json",
        "--write-description",
        "--write-thumbnail",
        "--write-subs", "--write-auto-subs", "--sub-langs", "en.*",
        "--write-comments", "--extractor-args", "youtube:max_comments=200,all,100",
        "--no-overwrites",
        "--retries", "3",
        url,
    ]
    probe = subprocess.run(args, cwd=YTDLP, capture_output=True, text=True, timeout=3600)
    if probe.returncode != 0:
        return False, (probe.stderr or "").strip()[-400:]
    return True, ""


def reindex() -> str:
    probe = subprocess.run(
        [sys.executable, str(TOOLS / "build_library_index.py")],
        capture_output=True, text=True, timeout=1800,
    )
    return (probe.stdout or probe.stderr).strip()[-300:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report new items without downloading")
    parser.add_argument("--no-index", action="store_true",
                        help="skip the index rebuild")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"error: {MANIFEST} missing", file=sys.stderr)
        return 2
    if not have_ytdlp():
        print(f"error: vendored yt-dlp not runnable at {YTDLP}", file=sys.stderr)
        return 2

    sources = json.loads(MANIFEST.read_text(encoding="utf-8")).get("sources", [])
    seen = known_ids()

    new_items: list[dict] = []
    failures: list[dict] = []
    unsupported: list[dict] = []

    for source in sources:
        platform, url = source.get("platform"), source.get("url")
        if platform != "youtube":
            # Instagram has no supported bulk enumeration path here; fetch_instagram.py
            # handles it against an authenticated session instead.
            unsupported.append({"url": url, "platform": platform,
                                "reason": "not enumerable by this watcher"})
            continue
        try:
            for item in list_remote(url, source.get("scope", "")):
                if item["id"] not in seen:
                    seen.add(item["id"])
                    new_items.append({**item, "from": url})
        except Exception as exc:  # noqa: BLE001 - one bad source must not stop the run
            failures.append({"url": url, "error": str(exc)[:300]})

    downloaded, download_failed = [], []
    if new_items and not args.check:
        for item in new_items:
            ok, error = download(item["id"], item["url"])
            (downloaded if ok else download_failed).append(
                {**item, **({"error": error} if error else {})}
            )
        if downloaded:
            with COMPLETE.open("a", encoding="utf-8") as handle:
                for item in downloaded:
                    handle.write(f"youtube {item['id']}\n")

    index_result = ""
    if downloaded and not args.no_index:
        index_result = reindex()

    report = {
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "check" if args.check else "download",
        "sources_checked": sum(1 for s in sources if s.get("platform") == "youtube"),
        "already_archived": len(known_ids()),
        "new_found": new_items,
        "downloaded": downloaded,
        "download_failed": download_failed,
        "source_failures": failures,
        "not_enumerable": unsupported,
        "index": index_result,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"watch-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Speak only when something happened.
    noteworthy = bool(new_items or failures or download_failed)
    if not noteworthy:
        print(f"no change ({report['already_archived']} archived, "
              f"{report['sources_checked']} sources checked)")
        return 0

    if new_items:
        print(f"{len(new_items)} new item(s):")
        for item in new_items:
            print(f"  {item['id']}  {item['title'][:80]}")
    if downloaded:
        print(f"downloaded {len(downloaded)}")
    if download_failed:
        print(f"download FAILED for {len(download_failed)}:", file=sys.stderr)
        for item in download_failed:
            print(f"  {item['id']}: {item.get('error','')[:160]}", file=sys.stderr)
    if failures:
        print(f"{len(failures)} source(s) could not be checked:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure['url']}: {failure['error'][:160]}", file=sys.stderr)
    if index_result:
        print(f"index: {index_result}")
    print(f"report: {report_path}")
    return 1 if (download_failed or failures) else 0


if __name__ == "__main__":
    sys.exit(main())
