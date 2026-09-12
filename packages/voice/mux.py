"""Assemble — put voiceover and subtitles onto a video.

The last mile of a reel. Takes generated or shot footage, a voiceover track and a script,
and produces a delivery file with burned-in captions.

Three decisions worth stating:

  * **Subtitles are burned in, not attached.** Instagram and TikTok do not reliably render
    a sidecar subtitle track, and most people watch muted. A soft subtitle track is a
    caption nobody sees.
  * **Audio duration drives the cut, not the other way round.** If the voiceover is longer
    than the picture, the picture is extended by holding the last frame rather than
    speeding up speech. Rushed speech is the most common tell of an automated reel.
  * **Loudness is normalised to -14 LUFS**, the integrated target these platforms
    normalise to anyway. Doing it here means you hear what the viewer hears.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out" / "voice"

TARGET_LUFS = -14.0
SAFE_BOTTOM_PCT = 0.14      # keep captions above platform UI furniture


class MuxError(RuntimeError):
    pass


@dataclass
class MuxResult:
    output: str
    duration_s: float | None
    video_duration_s: float | None
    audio_duration_s: float | None
    strategy: str
    warnings: list[str] = field(default_factory=list)


def _need_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise MuxError("ffmpeg/ffprobe are not on PATH")


def dimensions(p: Path) -> tuple[int, int] | None:
    """Needed because libass sizes text against the subtitle file's PlayRes, which
    defaults to 384x288. Without setting PlayRes to the real frame size, a font size that
    looks sane renders roughly five times too big on a 1080x1920 reel."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                            str(p)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        w, h = r.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except Exception:  # noqa: BLE001
        return None


def duration(p: Path) -> float | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(p)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return round(float(r.stdout.strip()), 2)
    except Exception:  # noqa: BLE001
        return None


def _ass_time(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):d}:{int(m):02d}:{sec:05.2f}"


def _wrap(script: str, max_chars: int) -> list[str]:
    words, lines, cur = script.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars or not cur:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def script_to_ass(script: str, total_s: float, vw: int, vh: int,
                  max_chars: int = 24) -> str:
    """Build an ASS subtitle file with PlayRes pinned to the real frame size.

    SRT plus ffmpeg's `force_style` does not work here: libass sizes text against the
    subtitle file's own PlayRes, which defaults to 384x288, and `original_size` only
    corrects the aspect ratio. The result is captions roughly five times too large on a
    1080x1920 reel. Writing ASS directly is the only way to state the resolution the font
    size is relative to.

    Timing is proportional to characters — predictable, but a starting point to nudge
    rather than forced alignment.
    """
    lines = _wrap(script, max_chars)
    if not lines:
        return ""
    font = max(18, round(vh * 0.042))
    margin_v = int(vh * SAFE_BOTTOM_PCT)
    margin_h = int(vw * 0.07)
    head = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {vw}\n"
        f"PlayResY: {vh}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,Arial,{font},&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(2, font // 14)},0,2,"
        f"{margin_h},{margin_h},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    total_chars = sum(len(l) for l in lines) or 1
    body, t = [], 0.0
    for line in lines:
        span = max(0.8, total_s * (len(line) / total_chars))
        body.append(f"Dialogue: 0,{_ass_time(t)},{_ass_time(t + span)},Caption,,0,0,0,,"
                    f"{line}")
        t += span
    return head + "\n".join(body) + "\n"


def mux(video: Path, audio: Path | None, script: str | None, dest: Path,
        font_size: int | None = None, keep_original_audio: bool = False,
        dry_run: bool = True) -> MuxResult:
    _need_ffmpeg()
    if not video.exists():
        raise MuxError(f"video not found: {video}")
    vd, ad = duration(video), (duration(audio) if audio and audio.exists() else None)
    dims = dimensions(video)
    warnings: list[str] = []
    if dims is None:
        dims = (1080, 1920)
        warnings.append("could not read frame size; assuming 1080x1920 for caption sizing")
    vw, vh = dims
    # ~4.5% of frame height is a readable caption on a phone without dominating the frame.
    if font_size is None:
        font_size = max(18, round(vh * 0.045))

    if ad and vd and ad > vd + 0.15:
        strategy = "hold_last_frame"
        warnings.append(
            f"voiceover ({ad:.1f}s) is longer than the picture ({vd:.1f}s); the last frame is "
            f"held rather than speeding up speech")
    elif ad and vd and vd > ad + 0.15:
        strategy = "trim_to_audio"
        warnings.append(f"picture ({vd:.1f}s) is longer than the voiceover ({ad:.1f}s); "
                        f"trimming picture to the narration")
    else:
        strategy = "as_is"

    target = ad or vd or 0.0
    srt_path = None
    if script:
        # Wrap width follows the frame: a 42-char line that fits 16:9 overflows 9:16.
        max_chars = 24 if vw < vh else 46
        srt = script_to_ass(script, target, vw, vh, max_chars)
        srt_path = dest.with_suffix(".ass")
        if not dry_run:
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(srt, encoding="utf-8")
        warnings.append("subtitle timing is proportional to characters, not force-aligned — "
                        "check it against the audio and nudge before delivery")

    if dry_run:
        return MuxResult(str(dest), target, vd, ad, strategy,
                         warnings + ["dry run — nothing rendered"])

    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if strategy == "hold_last_frame":
        cmd += ["-loop", "1", "-t", f"{target:.2f}", "-i", str(video)] if video.suffix.lower() in {".png", ".jpg"} \
            else ["-i", str(video)]
    else:
        cmd += ["-i", str(video)]
    if audio and audio.exists():
        cmd += ["-i", str(audio)]

    filters = []
    if strategy == "hold_last_frame":
        filters.append(f"tpad=stop_mode=clone:stop_duration={max(0, target - (vd or 0)):.2f}")
    if srt_path:
        esc = str(srt_path).replace("\\", "/").replace(":", "\\:")
        # No force_style: the ASS file declares its own PlayRes and style, which is the
        # whole point of generating ASS rather than SRT.
        filters.append(f"subtitles='{esc}'")
    if filters:
        cmd += ["-vf", ",".join(filters)]

    if audio and audio.exists():
        cmd += ["-filter:a", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11"]
        cmd += ["-map", "0:v:0", "-map", "1:a:0"] if not keep_original_audio else []
    cmd += ["-t", f"{target:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dest)]

    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    if r.returncode != 0 or not dest.exists():
        raise MuxError(f"ffmpeg failed: {(r.stderr or '')[:400]}")
    return MuxResult(str(dest), duration(dest), vd, ad, strategy, warnings)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mux voiceover and burned-in subtitles.")
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--script", help="caption text; omit for no subtitles")
    ap.add_argument("--script-file", type=Path)
    ap.add_argument("--out", type=Path, default=OUT / "reel.mp4")
    ap.add_argument("--font-size", type=int, default=None,
                    help="omit to size captions from the frame height (~4.5%%)")
    ap.add_argument("--keep-original-audio", action="store_true")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    script = a.script
    if a.script_file and a.script_file.exists():
        script = a.script_file.read_text(encoding="utf-8")

    res = mux(a.video, a.audio, script, a.out, a.font_size,
              a.keep_original_audio, dry_run=not a.live)
    print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    if not a.live:
        print("\n(dry run — pass --live to render)")


if __name__ == "__main__":
    try:
        main()
    except MuxError as e:
        raise SystemExit(f"error: {e}")
