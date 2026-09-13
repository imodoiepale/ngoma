"""YouTube creator learner.

Downloads subtitles (never the video by default — 23 archived videos already cost 942 MB)
and mines them into structured, citable ComfyUI knowledge:

    workflow names · node packs · model files · sampler settings · claimed results

That structured layer is what makes the corpus useful to the graph. A raw VTT dump is
just more text; `{"model": "flux-2-klein-9b-fp8", "video": "abc", "t": "14:22"}` is a fact
the strategy layer can act on and a human can verify by jumping to the timestamp.

Backend: yt-dlp (agent-reach reports it live and zero-config for YouTube).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import REPO, HarvestReport, write_report  # noqa: E402

CHANNELS = Path(__file__).resolve().parent / "channels.yaml"
LIB = REPO / "packages" / "library"
CORPUS = LIB / "corpus" / "youtube"

# ---- extraction vocabulary -------------------------------------------------
# Seeded from what the workflow manifest actually contains, so the extractor
# recognises the packs and models this studio really uses.

MODEL_RE = re.compile(
    r"\b([A-Za-z0-9][\w.\-]{3,60}\.(?:safetensors|ckpt|pt|pth|onnx|gguf))\b", re.I)

# Speech never contains ".safetensors". These are the spoken forms, mapped to the
# canonical name used in workflows/manifest.json so transcript facts JOIN to real graphs.
SPOKEN_MODELS: dict[str, str] = {
    "flux 2 klein": "flux-2-klein", "flux two klein": "flux-2-klein", "klein": "flux-2-klein",
    "flux krea": "flux-krea", "flux dev": "flux-dev", "flux schnell": "flux-schnell",
    "qwen image edit": "qwen-image-edit", "qwen image": "qwen-image", "qwen edit": "qwen-image-edit",
    "z image": "z-image-turbo", "z-image": "z-image-turbo", "zimage": "z-image-turbo",
    "wan 2.2": "wan-2.2", "wan two two": "wan-2.2", "wan 2.1": "wan-2.1", "wan animate": "wan-animate",
    "scail": "scail-2", "skail": "scail-2", "scale two": "scail-2",
    "ltx 2": "ltx-2", "ltx two": "ltx-2", "ltx video": "ltx-video", "ltxv": "ltx-video",
    "minimax": "minimax-h3", "h3": "minimax-h3",
    "nano banana pro": "nano-banana-pro", "nano banana": "nano-banana",
    "gpt image": "gpt-image-2", "seedream": "seedream", "ideogram": "ideogram",
    "hunyuan": "hunyuan", "cogvideo": "cogvideo", "animatediff": "animatediff",
    "sdxl": "sdxl", "illustrious": "illustrious", "pony": "pony",
    "sam 3": "sam3", "sam three": "sam3", "chroma": "chroma",
    "veo": "veo", "kling": "kling", "runway": "runway", "sora": "sora", "midjourney": "midjourney",
}

NODEPACK_HINTS = [
    "kjnodes", "kj nodes", "rgthree", "comfyroll", "video helper suite", "videohelpersuite",
    "impact pack", "impact subpack", "inspire pack", "controlnet aux", "easy use", "res4lyf",
    "wan video wrapper", "wanvideowrapper", "wan animate", "frame interpolation", "ltx video",
    "sam 3", "essentials", "face analysis", "ultimate sd upscale", "multi gpu", "multigpu",
    "custom scripts", "pythongosssss", "star nodes", "painter i2v", "rtx nodes",
    "unsafe torch", "efficiency nodes", "was node suite", "ipadapter", "ip adapter",
    "controlnet", "face detailer", "facedetailer", "ultralytics", "rife", "sage attention",
    "sageattention", "teacache", "triton", "xformers", "flash attention",
]

TECHNIQUE_HINTS = [
    "lora training", "lora", "character consistency", "face swap", "faceswap", "inpaint",
    "outpaint", "upscale", "img2img", "image to image", "text to image", "image to video",
    "text to video", "video to video", "first frame last frame", "keyframe", "depth map",
    "openpose", "pose transfer", "motion transfer", "latent", "denoise", "refiner",
    "prompt travel", "regional prompting", "batch", "dataset", "captioning", "detailer",
    "refmod", "ref mod", "reference to video", "identity", "audio ref",
]

# DGI Kaos and the UGC-format material carry creative vocabulary, which is what actually
# feeds packages/strategy. Without this the miner only sees the engineering half.
CREATIVE_HINTS = [
    "ugc", "hook", "b-roll", "broll", "voiceover", "voice over", "carousel", "reel",
    "thumbnail", "call to action", "cta", "storyboard", "shot list", "aspect ratio",
    "vertical", "9:16", "4:5", "talking head", "testimonial", "unboxing", "problem solution",
    "before after", "before and after", "day in the life", "green screen", "product demo",
    "split screen", "jump cut", "match cut", "camera move", "orbit", "dolly", "push in",
    "pan", "tilt", "close up", "wide shot", "low angle", "volumetric lighting", "golden hour",
    "colour grade", "color grade", "retention", "watch time", "engagement", "scroll stopper",
]

SETTING_RE = re.compile(
    r"\b(steps?|cfg|denoise|sampler|scheduler|resolution|frames?|fps|shift|guidance|seed|"
    r"strength|weight|batch size)\b"
    r"[^.\n]{0,30}?\b(\d+(?:\.\d+)?|euler[\w ]*|dpm[\w+ ]*|ddim|lcm|beta|karras|simple|normal)\b",
    re.I)
VRAM_RE = re.compile(
    r"\b(\d{1,3})\s?(?:gb|gigs?|gigabytes?)\b[^.\n]{0,24}\b(vram|ram|memory|card)\b", re.I)
VERSION_RE = re.compile(
    r"\b(python|torch|pytorch|cuda|triton|sage ?attention|comfy ?ui)\s?v?(\d+\.\d+(?:\.\d+)?)\b", re.I)
VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})|^([\w-]{11})$")
GPU_RE = re.compile(
    r"\b(rtx\s?\d{4}\s?(?:ti|super)?|a100|h100|a6000|a40|l40|4090|5090|3090)\b", re.I)


class YTError(RuntimeError):
    pass


def load_channels() -> dict[str, Any]:
    return yaml.safe_load(CHANNELS.read_text(encoding="utf-8"))


def _ytdlp(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["yt-dlp", *args], capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        raise YTError("yt-dlp is not on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise YTError(f"yt-dlp timed out after {timeout}s") from e


def list_videos(url: str, limit: int) -> list[dict[str, Any]]:
    r = _ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", str(limit), url])
    if r.returncode != 0:
        raise YTError(f"could not enumerate {url}: {(r.stderr or '').strip()[:300]}")
    out = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id"):
            out.append({"id": d["id"], "title": d.get("title"),
                        "duration": d.get("duration"), "url": d.get("url") or
                        f"https://www.youtube.com/watch?v={d['id']}"})
    # yt-dlp does not honour --playlist-end on a channel URL: it walks every tab
    # (videos, shorts, live) and returns all of them. Enforce the cap ourselves.
    return out[:limit]


def fetch_subs(video_id: str, dest: Path, langs: list[str]) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    if list(dest.glob(f"{video_id}*.vtt")):
        return sorted(dest.glob(f"{video_id}*.vtt"))
    _ytdlp([
        "--skip-download", "--write-sub", "--write-auto-sub",
        "--sub-langs", ",".join(langs), "--sub-format", "vtt",
        "--write-info-json", "--write-description",
        "-o", str(dest / "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ], timeout=420)
    return sorted(dest.glob(f"{video_id}*.vtt"))


def vtt_to_cues(p: Path) -> list[tuple[str, str]]:
    """Return (timestamp, text) cues with YouTube's rolling window collapsed.

    Auto-generated subtitles repeat: cue N is "A", cue N+1 is "A B", cue N+2 is "B C".
    Naive de-duplication keeps all three and triples every fact. Here each cue is reduced
    to the part that is genuinely new relative to what has already been emitted.
    """
    import html

    raw_cues: list[tuple[str, str]] = []
    ts, buf = None, []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if "-->" in line:
            if ts and buf:
                raw_cues.append((ts, " ".join(buf).strip()))
            ts = line.split("-->")[0].strip().split(".")[0]
            buf = []
        elif line and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
            txt = re.sub(r"<[^>]+>", "", line)          # inline karaoke timing tags
            txt = html.unescape(txt)
            txt = re.sub(r"^\s*(?:>>+|-)\s*", "", txt)   # speaker markers
            txt = txt.replace("\ufffd", "")              # mojibake from lossy decode
            if txt.strip():
                buf.append(txt.strip())
    if ts and buf:
        raw_cues.append((ts, " ".join(buf).strip()))

    cues: list[tuple[str, str]] = []
    tail = ""
    for ts, text in raw_cues:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if tail:
            # strip the longest suffix of `tail` that prefixes `text`
            words, tw = text.split(), tail.split()
            for k in range(min(len(words), len(tw)), 0, -1):
                if tw[-k:] == words[:k]:
                    words = words[k:]
                    break
            text = " ".join(words).strip()
        if not text:
            continue
        cues.append((ts, text))
        tail = (tail + " " + text).strip()
        tail = " ".join(tail.split()[-40:])
    return cues


def mine(cues: list[tuple[str, str]], video_id: str, title: str | None) -> dict[str, Any]:
    """Pull structured, timestamped, citable facts out of a transcript."""
    facts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str, ts: str, quote: str) -> None:
        k = (kind, value.lower())
        if k in seen:
            return
        seen.add(k)
        facts[kind].append({"value": value, "t": ts, "video": video_id, "quote": quote[:180]})

    # The title is high-signal and often names the model the whole video is about.
    haystack = [("00:00:00", title or "")] + cues

    for ts, text in haystack:
        low = " " + re.sub(r"[^a-z0-9.: ]+", " ", text.lower()) + " "
        for m in MODEL_RE.finditer(text):
            add("model_file", m.group(1), ts, text)
        for spoken, canon in SPOKEN_MODELS.items():
            if f" {spoken} " in low:
                add("model", canon, ts, text)
        for hint in NODEPACK_HINTS:
            if f" {hint} " in low:
                add("node_pack", hint, ts, text)
        for hint in TECHNIQUE_HINTS:
            if f" {hint} " in low:
                add("technique", hint, ts, text)
        for hint in CREATIVE_HINTS:
            if f" {hint} " in low:
                add("creative", hint, ts, text)
        for m in SETTING_RE.finditer(text):
            add("setting", f"{m.group(1).lower()}={m.group(2).lower()}", ts, text)
        for m in VRAM_RE.finditer(text):
            add("hardware", f"{m.group(1)}GB {m.group(2).lower()}", ts, text)
        for m in VERSION_RE.finditer(text):
            add("version", f"{re.sub(r'[ ]', '', m.group(1).lower())} {m.group(2)}", ts, text)
        for m in GPU_RE.finditer(text):
            add("gpu", re.sub(r"\s+", " ", m.group(1).lower()), ts, text)

    return {
        "video_id": video_id,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "cue_count": len(cues),
        "facts": dict(facts),
        "fact_count": sum(len(v) for v in facts.values()),
    }


def merge_facts(records: list[dict[str, Any]],
                corpus: Path | None = None) -> tuple[Path, dict[str, dict[str, int]]]:
    """Upsert mined videos into facts.jsonl by video_id, then rebuild the rollup from all of it.

    This used to rewrite facts.jsonl with only the current run's videos, so
    `--channel kiubai` silently deleted every other channel's facts, and the graph with
    them. A partial run is not the corpus.
    """
    corpus = corpus or CORPUS
    corpus.mkdir(parents=True, exist_ok=True)
    idx = corpus / "facts.jsonl"
    merged: dict[str, dict[str, Any]] = {}
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                merged[r["video_id"]] = r
    for r in records:
        merged[r["video_id"]] = r
    with idx.open("w", encoding="utf-8") as fh:
        for r in merged.values():
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in merged.values():
        for kind, items in r["facts"].items():
            for it in items:
                counts[kind][it["value"]] += 1
    rollup = {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in counts.items()}
    (corpus / "rollup.json").write_text(json.dumps(rollup, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    return idx, rollup


def video_id_of(url_or_id: str) -> str:
    m = VIDEO_ID_RE.search(url_or_id.strip())
    if not m:
        raise YTError(f"not a YouTube video URL or id: {url_or_id!r}")
    return m.group(1) or m.group(2)


def _channel_key_for(meta: dict[str, Any]) -> str:
    """The channels.yaml key when the channel is registered, else a slug of its handle."""
    cid = meta.get("channel_id") or ""
    for c in load_channels().get("channels", []):
        if cid and cid in (c.get("url") or ""):
            return c["key"]
    handle = (meta.get("uploader_id") or meta.get("channel") or "unsorted").lstrip("@")
    return re.sub(r"[^a-z0-9]+", "-", handle.lower()).strip("-") or "unsorted"


def learn_video(url_or_id: str, channel_key: str | None = None) -> HarvestReport:
    """Mine one video (a link someone sends) into the same corpus the channel runs build."""
    vid = video_id_of(url_or_id)
    report = HarvestReport(platform="youtube", target=vid, status="ok", requested=1,
                           enumerated=1, downloaded=0, skipped_existing=0)
    langs = load_channels().get("subtitle_langs", ["en"])
    staging = CORPUS / "_incoming"
    try:
        fetch_subs(vid, staging, langs)
    except YTError as e:
        report.status = "failed"
        report.failures.append({"video": vid, "stage": "subtitles", "error": str(e)})
        return report
    info = staging / f"{vid}.info.json"
    meta = json.loads(info.read_text(encoding="utf-8")) if info.exists() else {}
    if not meta.get("title"):
        # yt-dlp sometimes writes the subtitles but not the info.json (seen on 2K6-OtV_Vbc),
        # which filed the video under "unsorted" with a null title. Ask for metadata directly.
        r = _ytdlp(["-J", "--skip-download", f"https://www.youtube.com/watch?v={vid}"], timeout=300)
        try:
            meta = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
        except json.JSONDecodeError:
            meta = {}
    if not meta.get("title"):
        report.status = "partial"
        report.notes.append("WARNING: no video metadata; title and channel are unknown")
    key = channel_key or _channel_key_for(meta)
    cdir = CORPUS / key / "subs"
    cdir.mkdir(parents=True, exist_ok=True)
    for f in staging.glob(f"{vid}*"):
        f.replace(cdir / f.name)
    if meta:
        # A raw yt-dlp info.json is ~760 KB, almost all of it stream-format lists.
        keep = ("id", "title", "channel", "channel_id", "uploader_id", "upload_date",
                "duration", "view_count", "like_count", "comment_count", "tags",
                "categories", "chapters", "description", "webpage_url")
        (cdir / f"{vid}.info.json").write_text(
            json.dumps({k: meta.get(k) for k in keep}, indent=2, ensure_ascii=False),
            encoding="utf-8")
    subs = sorted(cdir.glob(f"{vid}*.vtt"))
    if not subs:
        report.status = "failed"
        report.failures.append({"video": vid, "error": "no subtitle track; needs faster-whisper fallback"})
        return report

    best = sorted(subs, key=lambda p: (".en-orig." not in p.name, ".en." not in p.name))[0]
    rec = mine(vtt_to_cues(best), vid, meta.get("title"))
    rec.update({
        "channel": key,
        "channel_name": meta.get("channel"),
        "upload_date": meta.get("upload_date"),
        "duration_s": meta.get("duration"),
        "view_count": meta.get("view_count"),
        "links": re.findall(r"https?://\S+", meta.get("description") or ""),
        "subtitle_file": str(best.relative_to(REPO)).replace("\\", "/"),
    })
    idx, _ = merge_facts([rec])
    report.downloaded = 1
    report.notes.append(f"{vid} \"{meta.get('title')}\" ({meta.get('channel')}): "
                        f"{rec['fact_count']} facts -> {idx.relative_to(REPO)}")
    for kind, items in sorted(rec["facts"].items()):
        report.notes.append(f"{kind}: " + ", ".join(sorted({i["value"] for i in items}))[:180])
    return report


def learn(channel_keys: Iterable[str] | None = None, tiers: Iterable[str] = ("core",),
          max_videos: int | None = None, dry_run: bool = False) -> HarvestReport:
    cfg = load_channels()
    langs = cfg.get("subtitle_langs", ["en"])
    limit = max_videos or cfg.get("default_max_videos", 25)
    wanted = [
        c for c in cfg["channels"]
        if (channel_keys and c["key"] in channel_keys) or (not channel_keys and c["tier"] in tiers)
    ]
    report = HarvestReport(platform="youtube", target=f"{len(wanted)} channels", status="ok",
                           requested=len(wanted) * limit, enumerated=0,
                           downloaded=0, skipped_existing=0)
    if not wanted:
        report.status = "failed"
        report.notes.append(f"no channels matched keys={list(channel_keys or [])} tiers={list(tiers)}")
        return report

    if dry_run:
        report.notes.append(
            f"dry run — would enumerate up to {limit} videos each from: "
            + ", ".join(c["key"] for c in wanted))
        return report

    all_facts: list[dict[str, Any]] = []
    for ch in wanted:
        cdir = CORPUS / ch["key"]
        try:
            vids = list_videos(ch["url"], limit)
        except YTError as e:
            report.failures.append({"channel": ch["key"], "stage": "enumerate", "error": str(e)})
            continue
        report.enumerated += len(vids)
        for v in vids:
            try:
                subs = fetch_subs(v["id"], cdir / "subs", langs)
            except YTError as e:
                report.failures.append({"channel": ch["key"], "video": v["id"], "error": str(e)})
                continue
            if not subs:
                report.failures.append({"channel": ch["key"], "video": v["id"],
                                        "error": "no subtitle track; needs faster-whisper fallback"})
                continue
            report.downloaded += 1
            # prefer the original-language English track when several exist
            best = sorted(subs, key=lambda p: (".en-orig." not in p.name, ".en." not in p.name))[0]
            rec = mine(vtt_to_cues(best), v["id"], v["title"])
            rec["channel"] = ch["key"]
            rec["subtitle_file"] = str(best.relative_to(REPO)).replace("\\", "/")
            all_facts.append(rec)

    idx, rollup = merge_facts(all_facts)

    report.notes.append(f"{len(all_facts)} videos mined -> {idx.relative_to(REPO)}")
    for kind, v in rollup.items():
        report.notes.append(f"{kind}: {len(v)} distinct")
    if report.failures:
        report.status = "partial"
    write_report(CORPUS / "harvest-report.json", report)
    return report


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Mine ComfyUI knowledge from creator transcripts.")
    ap.add_argument("--channel", action="append", default=[], help="channel key (repeatable)")
    ap.add_argument("--tier", action="append", default=[], choices=["core", "proposed"])
    ap.add_argument("--max-videos", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--video", action="append", default=[],
                    help="mine one video URL or id (repeatable); merges into the corpus")
    a = ap.parse_args()

    if a.video:
        bad = 0
        for v in a.video:
            rep = learn_video(v, a.channel[0] if a.channel else None)
            print(rep.summary())
            for n in rep.notes:
                print(f"    {n}")
            for f in rep.failures:
                print(f"    FAIL {f}")
            bad += rep.status != "ok"
        raise SystemExit(1 if bad else 0)

    if a.list:
        cfg = load_channels()
        for c in cfg["channels"]:
            print(f"{c['key']:<20} {c['tier']:<9} {c['name']:<28} {','.join(c.get('topics', []))[:60]}")
        return

    print("Using agent-reach route: YouTube via yt-dlp (subtitles only, no video download).")
    rep = learn(a.channel or None, tuple(a.tier) or ("core",), a.max_videos, a.dry_run)
    print(rep.summary())
    for n in rep.notes:
        print(f"    {n}")
    for f in rep.failures[:8]:
        print(f"    FAIL {f}")


if __name__ == "__main__":
    _cli()
