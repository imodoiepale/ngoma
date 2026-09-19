"""The steps the engine runs on this machine: voiceover, cut, captions, export, the brand
compositor, the claim check, hook variants, transcription, and the file conversions a
ComfyUI workflow needs before it can take an input.

No GPU. Voiceover can spend (ElevenLabs bills per character); cut and captions are ffmpeg;
the compositor is Pillow; claim-check and hooks are pure rules; transcribe reads a sidecar
transcript when there is one and faster-whisper otherwise. Every function takes `dry_run`
and returns a dict that says what happened or would happen. Everything is deterministic:
the same inputs give the same bytes (fonts aside) and the same text.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "voice"))
sys.path.insert(0, str(REPO / "packages" / "compositor"))

RATIO_PX = {"1:1": (3840, 3840), "4:5": (3072, 3840), "3:4": (2880, 3840), "9:16": (2160, 3840), "16:9": (3840, 2160)}


class EditError(RuntimeError):
    pass


def _ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise EditError("ffmpeg and ffprobe must be on PATH")


def _run(cmd: list[str], timeout: int = 1800) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise EditError(f"{Path(cmd[0]).name} failed: {(r.stderr or r.stdout)[-400:]}")


def _size(p: Path) -> tuple[int, int]:
    import mux
    return mux.dimensions(p) or (1080, 1920)


def voiceover(text: str, lang: str, dest: Path, provider: str | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Render narration. Sheng is refused (no TTS speaks it); the provider falls back from the one
    asked for to ElevenLabs, then the free edge-tts voices."""
    import tts
    if not text.strip():
        return {"status": "blocked", "note": "no script to read"}
    if lang == "sheng":
        return {"status": "blocked", "note": tts.SHENG_REFUSAL.splitlines()[0]}
    order = [p for p in (provider, "elevenlabs", "edge-tts") if p]
    chosen = next((p for p in order if tts.available(p)[0]), None)
    if not chosen:
        return {"status": "blocked", "note": f"no voice provider available (tried {', '.join(order)})"}
    take = tts.render_take(chosen, text, lang, dest, dry_run=dry_run)
    status = {"ok": "completed", "dry_run": "dry-run"}.get(take.status, "error")
    return {"status": status, "provider": chosen, "characters": len(text), "files": [str(dest)] if take.path else [],
            "duration_s": take.duration_s, "note": take.error or ""}


def concat(files: list[Path], dest: Path, seconds_each: float | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Join clips in order at the first clip's frame size, each trimmed to `seconds_each` if given."""
    if not files:
        return {"status": "blocked", "note": "no clips to cut"}
    if dry_run:
        return {"status": "dry-run", "files": [], "note": f"would join {len(files)} clip(s)"}
    _ffmpeg()
    w, h = _size(files[0])
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f in files:
        cmd += ["-i", str(f)]
    chains = []
    for i in range(len(files)):
        trim = f"trim=duration={seconds_each}," if seconds_each else ""
        chains.append(f"[{i}:v]{trim}setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,"
                      f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=0[out]"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(cmd + ["-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(dest)])
    return {"status": "completed", "files": [str(dest)]}


def captions(video: Path, audio: Path | None, script: str | None, dest: Path, dry_run: bool = True) -> dict[str, Any]:
    import mux
    try:
        r = mux.mux(video, audio, script, dest, dry_run=dry_run)
    except mux.MuxError as e:
        return {"status": "error", "note": str(e)}
    return {"status": "dry-run" if dry_run else "completed", "files": [] if dry_run else [r.output],
            "note": "; ".join(r.warnings)}


def _post_layout(groups: list[str | None]) -> dict[str, list[int]]:
    """group id -> indices of the files in it, in order. Empty when nothing carries a group."""
    if not any(g is not None for g in groups):
        return {}
    out: dict[str, list[int]] = {}
    for i, g in enumerate(groups):
        out.setdefault(str(g if g is not None else "ungrouped"), []).append(i)
    return out


def export(files: list[Path], dest_dir: Path, dry_run: bool = True,
           groups: list[str | None] | None = None) -> dict[str, Any]:
    """Copy the masters to `dest_dir`. When the files carry a group (they came through a
    fan-out), they land as `posts/<group>/slide-<n>.<ext>` so one folder is one post ready to
    publish; otherwise flat, as before. A `posts.json` index is written in both layouts."""
    if not files:
        return {"status": "blocked", "note": "nothing to export"}
    groups = list(groups) if groups is not None else [None] * len(files)
    posts = _post_layout(groups)
    if dry_run:
        if posts:
            names = ", ".join(sorted(posts, key=lambda g: (len(g), g)))
            return {"status": "dry-run", "files": [], "layout": "posts/<group>/slide-<n>",
                    "expected": {"files": len(files), "groups": sorted(posts, key=lambda g: (len(g), g))},
                    "note": f"would export {len(files)} file(s) as {len(posts)} post folder(s) posts/<group>/slide-<n> for groups {names}"}
        return {"status": "dry-run", "files": [], "layout": "flat", "note": f"would export {len(files)} file(s)"}
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    index: dict[str, list[str]] = {}
    if posts:
        for g, idxs in posts.items():
            folder = dest_dir / "posts" / g
            folder.mkdir(parents=True, exist_ok=True)
            for n, i in enumerate(idxs, 1):
                target = folder / f"slide-{n:02d}{files[i].suffix.lower()}"
                shutil.copy2(files[i], target)
                out.append(str(target))
                index.setdefault(g, []).append(target.name)
    else:
        for f in files:
            target = dest_dir / f.name
            shutil.copy2(f, target)
            out.append(str(target))
        index["files"] = [Path(f).name for f in out]
    (dest_dir / "posts.json").write_text(json.dumps({"layout": "posts/<group>/slide-<n>" if posts else "flat",
                                                     "posts": index}, indent=2) + "\n", encoding="utf-8")
    return {"status": "completed", "files": out, "layout": "posts/<group>/slide-<n>" if posts else "flat",
            "posts": index}


# ---------------------------------------------------------------- brand compositor

def _luminance(hex_colour: str) -> float:
    c = hex_colour.lstrip("#")
    try:
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 0.5
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def brand_kit(brand_root: Path) -> tuple[dict[str, Any] | None, str]:
    """(brand.yaml as a dict ready for the compositor, problem). The compositor needs a measured
    palette with the roles ground, surface, accent and hairline, and a logo master to place.

    A kit that names its colours differently (EPALLE: charcoal, ivory, dust_gold) gets the roles
    filled deterministically by luminance: darkest is ground, lightest is surface, the remaining
    mid-tone is accent, ground doubles as hairline. Nothing is invented; the note says so."""
    import yaml
    p = brand_root / "brand.yaml"
    if not p.exists():
        return None, f"no brand.yaml at {p}"
    spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    pal = dict(((spec.get("palette") or {}).get("measured") or {}))
    hexes = {k: v for k, v in pal.items() if isinstance(v, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", v)}
    roles = ("ground", "surface", "accent", "hairline")
    if not all(k in hexes for k in roles):
        if len(hexes) < 2:
            return spec, "brand.yaml palette.measured needs at least two colours (or ground, surface, accent, hairline)"
        by_light = sorted(hexes, key=lambda k: _luminance(hexes[k]))
        derived = {"ground": hexes[by_light[0]], "surface": hexes[by_light[-1]],
                   "accent": hexes[by_light[len(by_light) // 2]] if len(by_light) > 2 else hexes[by_light[-1]],
                   "hairline": hexes[by_light[0]]}
        pal = {**derived, **{k: v for k, v in pal.items() if k in roles}}
        spec = {**spec, "palette": {**(spec.get("palette") or {}), "measured": {**hexes, **pal}},
                "_palette_roles_derived": {k: by_light[0] if k in ("ground", "hairline") else (by_light[-1] if k == "surface" else by_light[len(by_light) // 2])
                                           for k in roles if k not in hexes}}
    logo = spec.get("logo") or {}
    master = logo.get("master")
    if not master:
        return spec, "brand.yaml has no logo.master; the compositor places the logo, it never generates one"
    if not (brand_root / master).exists():
        return spec, f"logo master {master} is not on disk under {brand_root.name}/"
    if float(logo.get("min_width_pct", 12) or 0) <= 0:
        return spec, ("brand.yaml logo.min_width_pct is 0: this brand declares no mark to place on every asset, "
                      "so the compositor has nothing to composite; give it a lockup or drop the compositor step")
    return spec, ""


def copy_block(text: str, spec: dict[str, Any] | None) -> dict[str, str]:
    """Exact copy from the brief text: line 1 headline, line 2 subhead, line 3 call to action.
    Attribution and disclosure come from brand.yaml, never from a model."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    spec = spec or {}
    pos = spec.get("positioning") or {}
    return {"headline": lines[0] if lines else "", "subhead": lines[1] if len(lines) > 1 else "",
            "cta": lines[2] if len(lines) > 2 else "",
            "attribution": str(pos.get("attribution_line") or ""),
            "disclosure": str((spec.get("claim_safety") or {}).get("disclosure") or "")}


def composite_batch(files: list[Path], groups: list[str | None], brand_root: Path, text: str, ratio: str,
                    dest_dir: Path, campaign: str, dry_run: bool = True) -> dict[str, Any]:
    """Place the brand's logo and exact copy on every image, numbering slides within a group.

    Output i belongs to the same group as input i, so a carousel keeps its post. Files are
    `<campaign>-g<group>_<ratio>_<nn>.png` plus the compositor's sidecar JSON per image."""
    if not files:
        return {"status": "blocked", "note": "nothing to composite"}
    if ratio not in RATIO_PX:
        return {"status": "blocked", "note": f"ratio {ratio!r} is not one of {sorted(RATIO_PX)}"}
    spec, problem = brand_kit(brand_root)
    groups = list(groups) if groups else [None] * len(files)
    posts = _post_layout(groups) or {"0": list(range(len(files)))}
    distinct = sorted({str(g) for g in groups if g is not None}, key=lambda g: (len(g), g))
    if dry_run:
        note = f"would composite {len(files)} image(s) at {ratio} with the {brand_root.name} kit (logo + exact copy)"
        if distinct:
            note += f" across {len(distinct)} post(s), slides numbered within each"
        if problem:
            note += f"; blocked until fixed: {problem}"
        return {"status": "dry-run", "files": [], "groups": [], "expected": {"files": len(files), "groups": distinct},
                "note": note}
    if problem:
        return {"status": "blocked", "files": [], "note": problem}
    import compositor
    block = copy_block(text, spec)
    out_files, out_groups, warnings = [], [], []
    if spec.get("_palette_roles_derived"):
        warnings.append("palette roles derived by luminance from " + ", ".join(f"{k}={v}" for k, v in spec["_palette_roles_derived"].items()))
    for g, idxs in posts.items():
        for n, i in enumerate(idxs, 1):
            try:
                r = compositor.composite(files[i], spec, brand_root, block, ratio, RATIO_PX[ratio], dest_dir,
                                         f"{campaign}-g{g}", slide=(n, len(idxs)) if len(idxs) > 1 else None,
                                         provenance={"source": str(files[i]), "group": g})
            except (compositor.CompositorError, OSError) as e:
                raise EditError(str(e)) from e
            out_files.append(str(r.path))
            out_groups.append(groups[i])
            warnings += [f"{r.path.name}: {w}" for w in r.warnings]
    return {"status": "completed", "files": out_files, "groups": out_groups, "note": "; ".join(warnings)}


# ---------------------------------------------------------------- claim check

# Money promises and risk claims no brand here may make. Deterministic; a person clears
# anything this flags, a generating agent never does.
CLAIM_RULES: list[tuple[str, str]] = [
    (r"\bguarantee[ds]?\b", "guarantee"),
    (r"\b(risk[- ]free|no risk|zero risk|100 ?% safe|completely safe)\b", "risk-free claim"),
    (r"\b(double|triple|10x|multiply) your (money|savings|cash|income)\b", "money multiplication"),
    (r"\b(get rich|become rich|make you rich|instant wealth)\b", "wealth promise"),
    (r"\b\d+(\.\d+)? ?% ?(returns?|interest|profit|yield|apr|per (day|week|month))\b", "rate promise"),
    (r"\b(instant|immediate|same[- ]day|guaranteed) (loan|approval|credit|payout)s?\b", "instant credit promise"),
    (r"\b(no (credit )?checks?|everyone (is )?approved|approved for everyone)\b", "approval promise"),
    (r"\b(cure|heal|clinically proven)\b", "health claim"),
    (r"\b(#1|number one|best in (kenya|africa|the world)|world'?s best)\b", "superlative"),
    (r"\b(free money|cash back guaranteed|earn while you sleep|passive income)\b", "free money"),
]


def claim_check(text: str, brand_root: Path | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Pass the text through when it makes no money promise; block with every flag otherwise.
    brand.yaml `claim_safety.banned_phrases` (plain strings) add to the built-in rules."""
    if not (text or "").strip():
        return {"status": "blocked", "note": "no text to check"}
    flags: list[dict[str, str]] = []
    low = text.lower()
    for pattern, label in CLAIM_RULES:
        for m in re.finditer(pattern, low):
            flags.append({"rule": label, "match": text[m.start():m.end()]})
    if brand_root is not None and (brand_root / "brand.yaml").exists():
        import yaml
        spec = yaml.safe_load((brand_root / "brand.yaml").read_text(encoding="utf-8")) or {}
        for phrase in (spec.get("claim_safety") or {}).get("banned_phrases") or []:
            if str(phrase).lower() in low:
                flags.append({"rule": "brand banned phrase", "match": str(phrase)})
    verdict = "blocked" if flags else "pass"
    if dry_run:
        return {"status": "dry-run", "files": [], "verdict": verdict, "flags": flags,
                "note": f"would check {len(text.split())} word(s): {verdict}" + (f" ({len(flags)} flag(s))" if flags else "")}
    if flags:
        return {"status": "blocked", "files": [], "verdict": verdict, "flags": flags, "text": text,
                "note": "claim check blocked: " + "; ".join(f"{f['rule']}: '{f['match']}'" for f in flags) + ". A person rewrites it; no agent may clear its own."}
    return {"status": "completed", "files": [], "verdict": verdict, "flags": [], "text": text, "note": "no risky claim found"}


# ---------------------------------------------------------------- hook variants

HOOK_PATTERNS = [
    "What nobody tells you about {x}",
    "{X} in 15 seconds",
    "Stop doing this with {x}",
    "I tried {x} for 7 days. Here is what happened",
    "The {x} mistake everyone makes",
    "{X}: the honest version",
    "Before you {x}, watch this",
    "Three things about {x} I wish I knew earlier",
    "{X}, explained by someone who actually does it",
    "Why {x} is not what you think",
    "POV: your first time with {x}",
    "The fastest way to {x}",
    "{X} for people who hate {x}",
    "Nobody asked, but here is the truth about {x}",
    "{X}. No filter",
    "Read this before you {x}",
]


def hooks(text: str, count: int = 10, seed: int = 7, dry_run: bool = True) -> dict[str, Any]:
    """`count` opening lines built from the brief's subject with fixed patterns. Same seed, same
    lines. No model, no claim: the claim check still runs on the result when the pipeline has one."""
    if not (text or "").strip():
        return {"status": "blocked", "note": "no text to write hooks from"}
    count = max(1, min(int(count or 10), 50))
    first = re.split(r"[.!?\n]", text.strip(), maxsplit=1)[0].strip().rstrip(",;:")
    subject = re.sub(r"^(a|an|the|we|our|make|create|build)\s+", "", first, flags=re.I)[:80] or first[:80]
    if dry_run:
        return {"status": "dry-run", "files": [], "note": f"would write {count} hook variant(s) on '{subject}'"}
    order = sorted(range(len(HOOK_PATTERNS)), key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    lines = []
    for k in range(count):
        pat = HOOK_PATTERNS[order[k % len(order)]]
        line = pat.replace("{X}", subject[:1].upper() + subject[1:]).replace("{x}", subject)
        if k >= len(order):
            line += f" ({k // len(order) + 1})"
        lines.append(line)
    return {"status": "completed", "files": [], "subject": subject, "hooks": lines, "text": "\n".join(lines),
            "note": f"{len(lines)} hook(s) from fixed patterns; no claim was checked here"}


# ---------------------------------------------------------------- transcribe

def transcribe(media: Path, dest: Path, language: str | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Timed text from a clip. A sidecar `<clip>.txt` or `.srt` next to the media wins (free and
    exact); otherwise faster-whisper, when installed. Never a hosted API."""
    if not media.exists():
        return {"status": "blocked", "files": [], "note": f"{media} is not on disk"}
    sidecar = next((media.with_suffix(ext) for ext in (".txt", ".srt") if media.with_suffix(ext).exists()), None)
    if dry_run:
        how = f"read the sidecar {sidecar.name}" if sidecar else "run faster-whisper locally"
        return {"status": "dry-run", "files": [], "note": f"would transcribe {media.name}: {how}"}
    if sidecar:
        text = sidecar.read_text(encoding="utf-8", errors="replace")
        if sidecar.suffix == ".srt":
            text = "\n".join(ln.strip() for ln in text.splitlines()
                             if ln.strip() and not ln.strip().isdigit() and "-->" not in ln)
        source, lang = f"sidecar {sidecar.name}", language
    else:
        import transcribe as voice
        if not voice.whisper_available():
            return {"status": "blocked", "files": [],
                    "note": f"no sidecar transcript next to {media.name} and faster-whisper is not installed "
                            "(uv tool install faster-whisper), so nothing was transcribed"}
        try:
            text, lang, _dur = voice.transcribe(media, language=language)
        except voice.VoiceError as e:
            return {"status": "error", "files": [], "note": str(e)}
        source = "faster-whisper"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text.strip() + "\n", encoding="utf-8")
    return {"status": "completed", "files": [str(dest)], "text": text.strip(), "language": lang, "source": source}


def audio_to_video(audio: Path, dest: Path) -> Path:
    """Wrap an audio file in a black 640x360 video, for workflows that read a voice from a video
    file's soundtrack (MiniMax H3 image + audio to video)."""
    _ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30", "-i", str(audio),
          "-shortest", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dest)])
    return dest
