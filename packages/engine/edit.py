"""The steps the engine runs on this machine: voiceover, cut, captions, export, and the file
conversions a ComfyUI workflow needs before it can take an input.

No GPU. Voiceover can spend (ElevenLabs bills per character); everything else is ffmpeg.
Every function takes `dry_run` and returns a dict that says what happened or would happen.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "voice"))


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


def export(files: list[Path], dest_dir: Path, dry_run: bool = True) -> dict[str, Any]:
    if not files:
        return {"status": "blocked", "note": "nothing to export"}
    if dry_run:
        return {"status": "dry-run", "files": [], "note": f"would export {len(files)} file(s)"}
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for f in files:
        target = dest_dir / f.name
        shutil.copy2(f, target)
        out.append(str(target))
    return {"status": "completed", "files": out}


def audio_to_video(audio: Path, dest: Path) -> Path:
    """Wrap an audio file in a black 640x360 video, for workflows that read a voice from a video
    file's soundtrack (MiniMax H3 image + audio to video)."""
    _ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30", "-i", str(audio),
          "-shortest", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dest)])
    return dest
