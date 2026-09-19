"""Motion graphics without a GPU: typed text, kinetic type, lower thirds and phone mock-ups to MP4.

The `motion-graphics` catalogue step (M02, M07, S05, S06, U05, V07) needed a renderer that
takes a script and writes a clip. This is the lightest one that is real: every frame is
drawn with Pillow from a JSON spec, then piped as raw RGB(A) into ffmpeg, which the edit
stage (`packages/voice/mux.py`) already requires. No Node, no browser, no download.

    python packages/video/motion_graphics.py --spec spec.json --out clip.mp4 --dry-run   # frame plan only
    python packages/video/motion_graphics.py --spec spec.json --out clip.mp4             # render
    python packages/video/motion_graphics.py --example > spec.json                        # a starting spec

The spec
--------
    {
      "aspect": "9:16",             # 9:16 | 16:9 | 1:1 | 4:5 | 3:4, or give "width" and "height"
      "width": 1080,                # optional; the default short side is 1080
      "fps": 24,
      "duration": 6.0,              # seconds; defaults to the last line's `out`
      "client": "epalle",           # optional: colours named below resolve against
                                    # brands/<client>/brand.yaml palette.measured
      "font": "InterTight-ExtraBold.ttf",   # optional: file name or path; see "Fonts"
      "background": {"color": "#1A1512"}    # or {"image": "path"} or {"video": "path"}
                                            # or {"color": ..., "phone": true} for a phone mock-up frame,
                                            # with an optional "screen": "path" image inside the phone
      "lines": [
        {"text": "Pay in 3 taps", "in": 0.0, "out": 2.5,
         "style": "headline",      # headline | subhead | body | lower-third | caption
         "animation": "typed",     # typed | fade | slide-up | none
         "color": "ivory",         # a palette key of the client kit, or a hex colour
         "position": "center",     # center | top | bottom | lower-third, or [x_frac, y_frac]
         "size": 96}               # optional px; the style has a default per frame height
      ]
    }

`--dry-run` writes `<out>.plan.json`: the resolved size, fps, frame count, fonts, the ffmpeg
command, and per frame which lines are visible with their typed prefix, opacity and offset.
The same plan drives the render, so the plan is the test surface: it is deterministic and
needs neither ffmpeg nor a display. The MP4 is H.264 yuv420p (`libx264`) so every player and
every publisher takes it.

Fonts
-----
A font is looked for, in order, in `brands/<client>/fonts/`, `packages/video/fonts/`,
`packages/compositor/fonts/`, then the Windows and Linux system font folders, by the name
given in the spec, else the same candidates the compositor uses (Inter Tight, Inter, Arial,
DejaVu). If none exists Pillow's bundled default face is used and the plan records
`font.fallback = true`. Nothing is downloaded.

Alternatives, documented, not depended on
-----------------------------------------
Browser-quality type animation (springs, per-glyph 3D, After-Effects-style easing) is a
Node job: HyperFrames (`npm i -g hyperframes`, HTML compositions rendered to video) or a
Remotion project (`npx create-video`, `@remotion/cli render`). Either can replace `render`
behind the same spec by writing the composition from `plan()`; neither is installed and the
studio does not require them. This module covers title cards, kinetic captions, lower thirds
and app-demo phone frames, which is what the six ideas ship.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BRANDS = REPO / "brands"

ASPECTS: dict[str, tuple[int, int]] = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1), "4:5": (4, 5), "3:4": (3, 4)}
STYLES: dict[str, dict[str, Any]] = {
    # size is a fraction of the frame height; role picks the font candidates
    "headline": {"size": 0.075, "role": "headline", "position": "center", "animation": "typed", "align": "center"},
    "subhead": {"size": 0.045, "role": "subhead", "position": "center", "animation": "fade", "align": "center"},
    "body": {"size": 0.035, "role": "body", "position": "center", "animation": "fade", "align": "center"},
    "lower-third": {"size": 0.04, "role": "subhead", "position": "lower-third", "animation": "slide-up", "align": "left",
                    "plate": True},
    "caption": {"size": 0.038, "role": "body", "position": "bottom", "animation": "fade", "align": "center", "plate": True},
}
ANIMATIONS = ("typed", "fade", "slide-up", "none")
FADE_S = 0.35            # fade and slide take this long in and out
TYPE_CPS = 18.0          # typed characters per second
FONT_CANDIDATES = {
    "headline": ["InterTight-ExtraBold.ttf", "Inter-ExtraBold.ttf", "Inter-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "subhead": ["Inter-SemiBold.ttf", "Inter-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "body": ["Inter-Regular.ttf", "Inter-Medium.ttf", "arial.ttf", "DejaVuSans.ttf"],
}
SYSTEM_FONT_DIRS = [Path(r"C:\Windows\Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
                    Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/truetype")]
DEFAULT_PALETTE = {"ink": "#111111", "paper": "#F4F1EA", "accent": "#E9876A"}
EXAMPLE_SPEC: dict[str, Any] = {
    "aspect": "9:16", "fps": 24, "duration": 5.0, "client": None,
    "background": {"color": "#111111"},
    "lines": [
        {"text": "Pay in 3 taps", "in": 0.2, "out": 2.4, "style": "headline", "animation": "typed", "color": "#F4F1EA"},
        {"text": "No queue. No paperwork.", "in": 2.2, "out": 4.6, "style": "subhead", "animation": "fade", "color": "#F4F1EA"},
        {"text": "Amina, Nairobi", "in": 0.8, "out": 4.6, "style": "lower-third", "color": "#111111"},
    ],
}


class MotionGraphicsError(RuntimeError):
    pass


# ---------------------------------------------------------------- helpers

def _hex(c: str) -> tuple[int, int, int]:
    c = c.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise MotionGraphicsError(f"not a hex colour: {c!r}")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def kit_palette(client: str | None) -> dict[str, str]:
    """`palette.measured` of brands/<client>/brand.yaml, hex values only; the defaults when
    there is no client or no palette."""
    if not client:
        return dict(DEFAULT_PALETTE)
    p = BRANDS / client / "brand.yaml"
    if not p.exists():
        raise MotionGraphicsError(f"no brand kit at {p.relative_to(REPO).as_posix()}")
    import yaml
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    measured = ((doc.get("palette") or {}).get("measured") or {})
    out = {k: str(v) for k, v in measured.items() if isinstance(v, str) and str(v).startswith("#")}
    return out or dict(DEFAULT_PALETTE)


def resolve_colour(value: str | None, palette: dict[str, str], default: str) -> str:
    if not value:
        return default
    if value in palette:
        return palette[value]
    if value.startswith("#"):
        _hex(value)
        return value.upper()
    raise MotionGraphicsError(f"colour {value!r} is neither a palette key {sorted(palette)} nor a hex value")


def find_font(name: str | None, role: str, client: str | None) -> tuple[Path | None, bool]:
    """(path, fallback). A repo or system TrueType file, else (None, True) for Pillow's default."""
    dirs = [BRANDS / client / "fonts" if client else None, REPO / "packages" / "video" / "fonts",
            REPO / "packages" / "compositor" / "fonts", *SYSTEM_FONT_DIRS]
    dirs = [d for d in dirs if d is not None]
    names = ([name] if name else []) + FONT_CANDIDATES[role]
    for n in names:
        p = Path(n)
        if p.is_absolute() or "/" in n or "\\" in n:
            if p.exists():
                return p, False
            continue
        for d in dirs:
            if (d / n).exists():
                return d / n, False
    return None, True


def _load_font(path: Path | None, size: int):
    from PIL import ImageFont
    if path is not None:
        return ImageFont.truetype(str(path), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def frame_size(spec: dict[str, Any]) -> tuple[int, int]:
    if spec.get("width") and spec.get("height"):
        w, h = int(spec["width"]), int(spec["height"])
    else:
        aspect = spec.get("aspect", "9:16")
        if aspect not in ASPECTS:
            raise MotionGraphicsError(f"aspect must be one of {sorted(ASPECTS)} or give width and height")
        aw, ah = ASPECTS[aspect]
        short = int(spec.get("width") or 1080)
        w, h = (short, round(short * ah / aw)) if aw <= ah else (round(short * aw / ah), short)
    # yuv420p needs even dimensions
    return w + (w % 2), h + (h % 2)


def _ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(min(max(t, 0.0), 1.0) * math.pi)


# ---------------------------------------------------------------- the plan

def plan(spec: dict[str, Any], out: Path | None = None) -> dict[str, Any]:
    """Resolve a spec into per-frame line states. Deterministic; touches no file, needs no ffmpeg."""
    if not isinstance(spec.get("lines"), list) or not spec["lines"]:
        raise MotionGraphicsError("spec.lines must be a non-empty list")
    w, h = frame_size(spec)
    fps = int(spec.get("fps") or 24)
    if fps < 1 or fps > 60:
        raise MotionGraphicsError("fps must be between 1 and 60")
    client = spec.get("client")
    palette = kit_palette(client)
    bg = dict(spec.get("background") or {"color": palette.get("ground") or palette.get("charcoal") or "#111111"})
    bg_colour = resolve_colour(bg.get("color"), palette, "#111111")
    for key in ("image", "video", "screen"):
        if bg.get(key) and not Path(bg[key]).exists():
            raise MotionGraphicsError(f"background {key} not found: {bg[key]}")
    if bg.get("image") and bg.get("video"):
        raise MotionGraphicsError("background takes an image or a video, not both")

    lines: list[dict[str, Any]] = []
    fonts: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(spec["lines"]):
        if not str(raw.get("text", "")).strip():
            raise MotionGraphicsError(f"lines[{i}] has no text")
        style = STYLES.get(raw.get("style", "headline"))
        if style is None:
            raise MotionGraphicsError(f"lines[{i}].style must be one of {sorted(STYLES)}")
        t_in, t_out = float(raw.get("in", 0.0)), float(raw.get("out", 0.0))
        if t_out <= t_in or t_in < 0:
            raise MotionGraphicsError(f"lines[{i}]: out must be after in")
        anim = raw.get("animation", style["animation"])
        if anim not in ANIMATIONS:
            raise MotionGraphicsError(f"lines[{i}].animation must be one of {ANIMATIONS}")
        role = style["role"]
        path, fallback = find_font(raw.get("font") or spec.get("font"), role, client)
        fonts.setdefault(role, {"path": path.as_posix() if path else None, "fallback": fallback})
        default_ink = palette.get("ivory") or palette.get("paper") or palette.get("ink") or "#F4F1EA"
        lines.append({
            "index": i, "text": str(raw["text"]), "style": raw.get("style", "headline"), "animation": anim,
            "in": t_in, "out": t_out, "frame_in": int(round(t_in * fps)), "frame_out": int(round(t_out * fps)),
            "size": int(raw.get("size") or round(style["size"] * h)), "role": role,
            "color": resolve_colour(raw.get("color"), palette, default_ink),
            "plate": resolve_colour(raw.get("plate"), palette, palette.get("accent") or palette.get("dust_gold") or "#E9876A")
            if style.get("plate") or raw.get("plate") else None,
            "position": raw.get("position", style["position"]), "align": raw.get("align", style["align"]),
        })

    duration = float(spec.get("duration") or max(l["out"] for l in lines))
    n_frames = max(1, int(round(duration * fps)))
    frames: list[dict[str, Any]] = []
    for f in range(n_frames):
        t = f / fps
        visible = []
        for l in lines:
            if not (l["in"] <= t < l["out"]):
                continue
            age, left = t - l["in"], l["out"] - t
            state: dict[str, Any] = {"line": l["index"], "text": l["text"], "opacity": 1.0, "dy": 0}
            if l["animation"] == "typed":
                shown = min(len(l["text"]), int(age * TYPE_CPS) + 1)
                state["text"] = l["text"][:shown]
                state["cursor"] = shown < len(l["text"]) and (f // max(1, fps // 4)) % 2 == 0
                if left < FADE_S:
                    state["opacity"] = round(_ease(left / FADE_S), 3)
            elif l["animation"] in ("fade", "slide-up"):
                o = min(_ease(age / FADE_S), _ease(left / FADE_S))
                state["opacity"] = round(o, 3)
                if l["animation"] == "slide-up":
                    state["dy"] = int(round((1 - _ease(age / FADE_S)) * l["size"] * 0.6))
            visible.append(state)
        frames.append({"frame": f, "t": round(t, 4), "lines": visible})

    return {
        "version": 1, "width": w, "height": h, "fps": fps, "duration": duration, "frame_count": n_frames,
        "client": client, "palette": palette, "background": {**bg, "color": bg_colour},
        "fonts": fonts, "lines": lines, "frames": frames,
        "ffmpeg": ffmpeg_command(w, h, fps, duration, bg, out or Path("out.mp4")),
    }


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def ffmpeg_command(w: int, h: int, fps: int, duration: float, bg: dict[str, Any], out: Path) -> list[str]:
    """Raw frames on stdin become H.264. A background video is the first input and the drawn
    frames (RGBA) are overlaid on it, scaled to cover the frame."""
    exe = ffmpeg_path() or "ffmpeg"
    if bg.get("video"):
        return [exe, "-y", "-v", "error", "-stream_loop", "-1", "-i", str(bg["video"]),
                "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                "-filter_complex",
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}[bg];"
                f"[bg][1:v]overlay=shortest=1,format=yuv420p[v]",
                "-map", "[v]", "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-movflags", "+faststart", str(out)]
    return [exe, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
            "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]


# ---------------------------------------------------------------- drawing

def _cover(img, w: int, h: int):
    from PIL import Image
    scale = max(w / img.width, h / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    x, y = (resized.width - w) // 2, (resized.height - h) // 2
    return resized.crop((x, y, x + w, y + h))


def _phone_frame(canvas, w: int, h: int, screen_path: str | None, palette: dict[str, str]) -> None:
    """A rounded phone body centred in the frame with a screen area; the screen shows an image
    when given, else a slightly lighter panel. Drawn once and reused for every frame."""
    from PIL import Image, ImageDraw
    body_h = int(h * 0.78)
    body_w = int(body_h * 9 / 19.5)
    x0, y0 = (w - body_w) // 2, (h - body_h) // 2
    draw = ImageDraw.Draw(canvas)
    r = int(body_w * 0.12)
    draw.rounded_rectangle((x0, y0, x0 + body_w, y0 + body_h), radius=r, fill=(20, 20, 22, 255), outline=(70, 70, 74, 255), width=max(2, w // 300))
    inset = max(4, body_w // 30)
    sx0, sy0, sx1, sy1 = x0 + inset, y0 + inset, x0 + body_w - inset, y0 + body_h - inset
    if screen_path:
        screen = _cover(Image.open(screen_path).convert("RGBA"), sx1 - sx0, sy1 - sy0)
        mask = Image.new("L", screen.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, screen.width - 1, screen.height - 1), radius=r - inset, fill=255)
        canvas.paste(screen, (sx0, sy0), mask)
    else:
        draw.rounded_rectangle((sx0, sy0, sx1, sy1), radius=r - inset, fill=_hex(palette.get("paper") or palette.get("ivory") or "#F4F1EA") + (255,))
    notch_w = body_w // 3
    draw.rounded_rectangle((x0 + (body_w - notch_w) // 2, sy0 + inset, x0 + (body_w + notch_w) // 2, sy0 + inset * 3),
                           radius=inset, fill=(20, 20, 22, 255))


def _anchor(position: Any, w: int, h: int, text_w: int, text_h: int, align: str) -> tuple[int, int]:
    margin = int(h * 0.06)
    if isinstance(position, (list, tuple)) and len(position) == 2:
        cx, cy = float(position[0]) * w, float(position[1]) * h
        return int(cx - text_w / 2), int(cy - text_h / 2)
    if position == "top":
        y = margin
    elif position == "bottom":
        y = h - margin - text_h
    elif position == "lower-third":
        y = int(h * 0.72)
    else:
        y = (h - text_h) // 2
    x = margin if align == "left" else (w - margin - text_w if align == "right" else (w - text_w) // 2)
    return x, y


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def render_frame(p: dict[str, Any], frame: dict[str, Any], base, fonts: dict[int, Any]):
    """One frame: the background (or transparent when a video sits under it) plus the visible lines."""
    from PIL import Image, ImageDraw
    w, h = p["width"], p["height"]
    canvas = base.copy()
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    by_index = {l["index"]: l for l in p["lines"]}
    for state in frame["lines"]:
        l = by_index[state["line"]]
        font = fonts[l["index"]]
        alpha = int(round(255 * state["opacity"]))
        text = state["text"] + ("|" if state.get("cursor") else "")
        max_w = int(w * 0.84)
        rows = _wrap(draw, text, font, max_w)
        line_h = int(l["size"] * 1.2)
        text_w = max(int(draw.textlength(r, font=font)) for r in rows)
        text_h = line_h * len(rows)
        x, y = _anchor(l["position"], w, h, text_w, text_h, l["align"])
        y += state.get("dy", 0)
        if l.get("plate"):
            pad = int(l["size"] * 0.45)
            draw.rounded_rectangle((x - pad, y - pad // 2, x + text_w + pad, y + text_h + pad // 2), radius=pad // 2,
                                   fill=_hex(l["plate"]) + (alpha,))
        for k, row in enumerate(rows):
            rx = x if l["align"] == "left" else (x + text_w - int(draw.textlength(row, font=font)) if l["align"] == "right"
                                                 else x + (text_w - int(draw.textlength(row, font=font))) // 2)
            draw.text((rx, y + k * line_h), row, font=font, fill=_hex(l["color"]) + (alpha,))
    return Image.alpha_composite(canvas, layer)


def _base_canvas(p: dict[str, Any]):
    """What sits under the type on every frame: colour or image, transparent over a video, and
    the phone body when the spec asks for a mock-up."""
    from PIL import Image
    w, h = p["width"], p["height"]
    bg = p["background"]
    if bg.get("video"):
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    elif bg.get("image"):
        base = _cover(Image.open(bg["image"]).convert("RGBA"), w, h)
    else:
        base = Image.new("RGBA", (w, h), _hex(bg["color"]) + (255,))
    if bg.get("phone"):
        _phone_frame(base, w, h, bg.get("screen"), p["palette"])
    return base


def render(spec: dict[str, Any], out: Path, dry_run: bool = False) -> dict[str, Any]:
    """Plan, and unless `dry_run`, draw every frame and encode. Returns the plan with `status`,
    `plan_path` and, after a render, `file`."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    p = plan(spec, out)
    plan_path = out.with_suffix(out.suffix + ".plan.json")
    plan_path.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    p["plan_path"] = plan_path.as_posix()
    if dry_run:
        p["status"] = "dry-run"
        p["note"] = f"would render {p['frame_count']} frames at {p['width']}x{p['height']}@{p['fps']} to {out.name}"
        return p
    if not ffmpeg_path():
        raise MotionGraphicsError("ffmpeg is not on PATH; the render needs it (the edit stage does too)")
    base = _base_canvas(p)
    fonts = {l["index"]: _load_font(Path(p["fonts"][l["role"]]["path"]) if p["fonts"][l["role"]]["path"] else None, l["size"])
             for l in p["lines"]}
    fmt = "RGBA" if p["background"].get("video") else "RGB"
    proc = subprocess.Popen(p["ffmpeg"], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in p["frames"]:
            img = render_frame(p, frame, base, fonts)
            proc.stdin.write(img.convert(fmt).tobytes())  # type: ignore[union-attr]
    finally:
        proc.stdin.close()  # type: ignore[union-attr]
    _, err = proc.communicate(timeout=600)
    if proc.returncode != 0 or not out.exists():
        raise MotionGraphicsError(f"ffmpeg failed: {(err or b'').decode('utf-8', 'ignore')[:400]}")
    p["status"] = "completed"
    p["file"] = out.as_posix()
    p["note"] = f"{p['frame_count']} frames, {p['duration']:.2f}s, {out.stat().st_size} bytes"
    return p


# ---------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render typed text, kinetic type, lower thirds and phone mock-ups to MP4 "
                                             "with Pillow and ffmpeg. See the module docstring for the spec.")
    ap.add_argument("--spec", help="JSON spec file (see --example)")
    ap.add_argument("--out", help="output .mp4; the frame plan goes to <out>.plan.json")
    ap.add_argument("--dry-run", action="store_true", help="write the frame plan JSON only, no ffmpeg")
    ap.add_argument("--example", action="store_true", help="print an example spec and exit")
    a = ap.parse_args(argv)
    if a.example:
        print(json.dumps(EXAMPLE_SPEC, indent=2))
        return 0
    if not a.spec or not a.out:
        ap.error("--spec and --out are required (or --example)")
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    try:
        result = render(spec, Path(a.out), dry_run=a.dry_run)
    except MotionGraphicsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    summary = {k: result[k] for k in ("status", "width", "height", "fps", "frame_count", "plan_path", "note") if k in result}
    if "file" in result:
        summary["file"] = result["file"]
    summary["fonts"] = result["fonts"]
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
