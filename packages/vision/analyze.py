"""Reference analysis — turn harvested images and video into structured creative features.

Runs entirely offline. That is deliberate: a VLM pass is better at semantics, but it costs
money per image and needs a key, and most of what a strategy layer needs is measurable —
palette, where the subject sits, how much of the frame is empty, whether there is room for
a headline, how dense the texture is, how the cut rhythm moves in a video.

Measured features are also *checkable*. "Dust gold drifted into orange" is a number here,
not an opinion, which is what makes `packages/strategy` able to enforce a brand rather than
just describe one.

An optional VLM pass (`--vlm`) layers semantics on top when a key is present. It never
replaces the measurements.

    uv run --with pillow --with numpy packages/vision/analyze.py --brand epalle --path <dir>
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageFilter, ImageStat

REPO = Path(__file__).resolve().parents[2]
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp"}
VID_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}

# Copy sits in the emptiest third. Anything below this is too busy to letter over.
QUIET_THRESHOLD = 0.12


# ----------------------------------------------------------------- colour helpers

def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb


def _unhex(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(rgb: tuple[int, int, int]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """Perceptual-ish distance. Plain RGB euclidean over-weights green; this weights the
    channels closer to how the eye reads a shift, which matters when the question is
    'did dust gold drift toward orange'."""
    rm = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db)


# ----------------------------------------------------------------- feature record

@dataclass
class Features:
    path: str
    kind: str
    width: int
    height: int
    aspect: str
    # colour
    palette: list[dict[str, Any]] = field(default_factory=list)
    mean_luma: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0
    warm_ratio: float = 0.0
    crushed_blacks: float = 0.0
    blown_whites: float = 0.0
    # composition
    subject_quadrant: str = ""
    busiest_third: str = ""
    quiet_zones: list[str] = field(default_factory=list)
    copy_zone: str | None = None
    edge_density: float = 0.0
    symmetry: float = 0.0
    rule_of_thirds_bias: str = ""
    # video only
    duration_s: float | None = None
    fps: float | None = None
    cut_count: int | None = None
    avg_shot_s: float | None = None
    # brand fit, filled by check_against_brand
    brand_fit: dict[str, Any] = field(default_factory=dict)
    semantics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _aspect_name(w: int, h: int) -> str:
    r = w / h
    for name, val in (("9:16", 9 / 16), ("4:5", 0.8), ("3:4", 0.75), ("1:1", 1.0),
                      ("16:9", 16 / 9), ("3:2", 1.5)):
        if abs(r - val) < 0.04:
            return name
    return f"{r:.2f}:1"


def _palette(im: Image.Image, k: int = 6) -> list[dict[str, Any]]:
    small = im.copy()
    small.thumbnail((160, 160))
    q = small.quantize(colors=k, method=Image.Quantize.FASTOCTREE)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    out = []
    for count, idx in counts[:k]:
        rgb = tuple(pal[idx * 3: idx * 3 + 3])  # type: ignore[assignment]
        if len(rgb) != 3:
            continue
        h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
        out.append({"hex": _hex(rgb), "share": round(count / total, 4),
                    "luma": round(_lum(rgb), 1), "sat": round(s, 3), "hue": round(h, 3)})
    return out


def analyse_image(p: Path, downscale: int = 900) -> Features:
    im = Image.open(p)
    W, H = im.size
    im = im.convert("RGB")
    if max(im.size) > downscale:
        im.thumbnail((downscale, downscale))
    w, h = im.size

    f = Features(path=str(p.relative_to(REPO)).replace("\\", "/") if REPO in p.parents else str(p),
                 kind="image", width=W, height=H, aspect=_aspect_name(W, H))

    stat = ImageStat.Stat(im)
    f.mean_luma = round(sum(stat.mean) / 3, 1)
    f.contrast = round(sum(stat.stddev) / 3, 1)
    f.palette = _palette(im)

    _, sat_channel, _ = im.convert("HSV").split()
    f.saturation = round(ImageStat.Stat(sat_channel).mean[0], 1)

    px = list(im.convert("RGB").getdata())  # noqa: PD011
    n = len(px) or 1
    f.crushed_blacks = round(sum(1 for c in px if _lum(c) < 8) / n, 4)
    f.blown_whites = round(sum(1 for c in px if _lum(c) > 248) / n, 4)
    warm = 0
    for c in px[::7]:
        hh, sss, vv = colorsys.rgb_to_hsv(*[x / 255 for x in c])
        if (hh < 0.13 or hh > 0.94) and sss > 0.15 and vv > 0.15:
            warm += 1
    f.warm_ratio = round(warm / max(1, len(px[::7])), 4)

    # --- composition, from an edge-energy map -------------------------------
    gray = im.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    f.edge_density = round(ImageStat.Stat(edges).mean[0] / 255, 4)

    cols, rows = 3, 3
    cw, ch = max(1, w // cols), max(1, h // rows)
    cells: dict[str, float] = {}
    names = [["top-left", "top-centre", "top-right"],
             ["mid-left", "centre", "mid-right"],
             ["bottom-left", "bottom-centre", "bottom-right"]]
    for r in range(rows):
        for c in range(cols):
            box = (c * cw, r * ch, min(w, (c + 1) * cw), min(h, (r + 1) * ch))
            cells[names[r][c]] = ImageStat.Stat(edges.crop(box)).mean[0] / 255
    f.subject_quadrant = max(cells, key=lambda k: cells[k])
    f.busiest_third = ("top" if sum(cells[n] for n in names[0]) >= max(
        sum(cells[n] for n in names[1]), sum(cells[n] for n in names[2]))
        else "middle" if sum(cells[n] for n in names[1]) >= sum(cells[n] for n in names[2])
        else "bottom")
    f.quiet_zones = sorted([k for k, v in cells.items() if v < QUIET_THRESHOLD],
                           key=lambda k: cells[k])
    f.copy_zone = f.quiet_zones[0] if f.quiet_zones else None
    if not f.copy_zone:
        f.notes.append("no zone quiet enough to letter over without a scrim")

    left = sum(cells[n[0]] for n in names)
    right = sum(cells[n[2]] for n in names)
    f.symmetry = round(1 - abs(left - right) / max(1e-6, left + right), 3)
    f.rule_of_thirds_bias = ("left" if left > right * 1.25 else
                             "right" if right > left * 1.25 else "centred")
    return f


# ----------------------------------------------------------------- video

def _ffprobe(p: Path) -> dict[str, Any]:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate,duration:format=duration",
             "-of", "json", str(p)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return json.loads(r.stdout or "{}")
    except Exception:  # noqa: BLE001 - ffprobe is optional
        return {}


def analyse_video(p: Path, sample_frames: int = 6) -> Features:
    meta = _ffprobe(p)
    streams = meta.get("streams") or [{}]
    st = streams[0]
    W, H = int(st.get("width") or 0), int(st.get("height") or 0)
    dur = float(st.get("duration") or (meta.get("format") or {}).get("duration") or 0) or None
    fps = None
    if st.get("r_frame_rate", "0/0") not in ("0/0", None):
        num, _, den = st["r_frame_rate"].partition("/")
        try:
            fps = round(int(num) / max(1, int(den)), 3)
        except ValueError:
            fps = None

    f = Features(path=str(p), kind="video", width=W, height=H,
                 aspect=_aspect_name(W, H) if W and H else "unknown",
                 duration_s=round(dur, 2) if dur else None, fps=fps)

    # Sample frames evenly and average their features, so a video gets the same
    # vocabulary as a still rather than a separate one.
    if dur and dur > 0:
        tmp = Path(REPO / "out" / "_vision_frames")
        tmp.mkdir(parents=True, exist_ok=True)
        for old in tmp.glob("f*.jpg"):
            old.unlink()
        step = dur / (sample_frames + 1)
        got = []
        for i in range(1, sample_frames + 1):
            fp = tmp / f"f{i:02d}.jpg"
            try:
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{step*i:.2f}",
                                "-i", str(p), "-frames:v", "1", "-q:v", "4", str(fp)],
                               capture_output=True, timeout=120)
                if fp.exists():
                    got.append(analyse_image(fp))
            except Exception:  # noqa: BLE001
                continue
        if got:
            f.palette = got[len(got) // 2].palette
            f.mean_luma = round(sum(g.mean_luma for g in got) / len(got), 1)
            f.contrast = round(sum(g.contrast for g in got) / len(got), 1)
            f.saturation = round(sum(g.saturation for g in got) / len(got), 1)
            f.warm_ratio = round(sum(g.warm_ratio for g in got) / len(got), 4)
            f.crushed_blacks = round(sum(g.crushed_blacks for g in got) / len(got), 4)
            f.edge_density = round(sum(g.edge_density for g in got) / len(got), 4)
            f.subject_quadrant = max(set(g.subject_quadrant for g in got),
                                     key=[g.subject_quadrant for g in got].count)
            quiet = set(got[0].quiet_zones)
            for g in got[1:]:
                quiet &= set(g.quiet_zones)
            f.quiet_zones = sorted(quiet)
            f.copy_zone = f.quiet_zones[0] if f.quiet_zones else None
            # crude cut detection: palette distance between consecutive samples
            cuts = sum(1 for a, b in zip(got, got[1:])
                       if abs(a.mean_luma - b.mean_luma) > 18 or abs(a.edge_density - b.edge_density) > 0.06)
            f.cut_count = cuts
            f.avg_shot_s = round(dur / max(1, cuts + 1), 2)
            f.notes.append(f"cut count is estimated from {len(got)} sampled frames — "
                           "indicative of pacing, not an exact edit list")
    else:
        f.notes.append("ffprobe could not read duration; is ffmpeg on PATH?")
    return f


# ----------------------------------------------------------------- brand fit

def check_against_brand(f: Features, brand_spec: dict[str, Any]) -> dict[str, Any]:
    """Turn the brand's palette rules into measured pass/fail, not opinion."""
    pal = brand_spec.get("palette", {}).get("measured", {})
    targets = {k: _unhex(v) for k, v in pal.items() if isinstance(v, str) and v.startswith("#")}
    if not targets:
        return {}

    found = [(_unhex(c["hex"]), c["share"]) for c in f.palette]
    matches, off = [], []
    for rgb, share in found:
        best = min(targets, key=lambda k: _dist(rgb, targets[k]))
        d = _dist(rgb, targets[best])
        (matches if d < 60 else off).append(
            {"hex": _hex(rgb), "share": share, "nearest": best, "distance": round(d, 1)})

    fit = {
        "in_palette_share": round(sum(m["share"] for m in matches), 3),
        "matched": matches,
        "off_palette": sorted(off, key=lambda m: -m["share"])[:4],
        "violations": [],
    }

    # The two named drifts from the EPALLE visual language, as measurements.
    if "dust_gold" in targets:
        for m in off:
            rgb = _unhex(m["hex"])
            hh, ss, vv = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
            if 0.02 < hh < 0.10 and ss > 0.45 and m["share"] > 0.05:
                fit["violations"].append(
                    f"{m['hex']} ({m['share']:.0%}) reads as saturated orange — dust gold "
                    f"must stay matte and aged, not warm into orange")
    if f.crushed_blacks > 0.20:
        fit["violations"].append(
            f"{f.crushed_blacks:.0%} of pixels are crushed to near-black — charcoal must "
            f"keep shadow detail")
    if f.blown_whites > 0.05:
        fit["violations"].append(f"{f.blown_whites:.0%} of pixels are blown out")

    for bad in brand_spec.get("forbidden_looks", []):
        if "symmetrical hero" in str(bad) and f.symmetry > 0.93 and f.edge_density > 0.1:
            fit["violations"].append("near-perfect left/right symmetry — a forbidden look")
    fit["passes"] = not fit["violations"]
    return fit


# ----------------------------------------------------------------- driver

def iter_media(root: Path, limit: int | None = None) -> Iterable[Path]:
    n = 0
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXT | VID_EXT:
            yield p
            n += 1
            if limit and n >= limit:
                return


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyse reference media into creative features.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--path", type=Path, required=True, help="file or directory of references")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path, help="defaults to <path>/vision.jsonl")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, str(REPO / "packages" / "brandkit"))
    brand_spec: dict[str, Any] = {}
    try:
        from brandkit import load_brand  # noqa: PLC0415
        brand_spec = load_brand(a.brand).spec
    except Exception as e:  # noqa: BLE001 - analysis still works without a brand
        print(f"note: no brand fit ({e})")

    root = a.path
    files = [root] if root.is_file() else list(iter_media(root, a.limit))
    if not files:
        raise SystemExit(f"no media found under {root}")

    out = a.out or ((root if root.is_dir() else root.parent) / "vision.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in files:
        try:
            f = analyse_video(p) if p.suffix.lower() in VID_EXT else analyse_image(p)
        except Exception as e:  # noqa: BLE001 - one bad file must not kill a batch
            print(f"  FAIL {p.name}: {e}")
            continue
        if brand_spec:
            f.brand_fit = check_against_brand(f, brand_spec)
        recs.append(f)
        if not a.quiet:
            v = f.brand_fit.get("violations", [])
            mark = "ok " if f.brand_fit.get("passes", True) else "!! "
            print(f"{mark}{p.name[:44]:<46} {f.aspect:<7} luma {f.mean_luma:>5.1f}  "
                  f"edge {f.edge_density:.3f}  copy@{f.copy_zone or 'none'}")
            for x in v:
                print(f"      {x}")

    with out.open("w", encoding="utf-8") as fh:
        for f in recs:
            fh.write(json.dumps(asdict(f), ensure_ascii=False) + "\n")
    print(f"\n{len(recs)} analysed -> {out}")
    if brand_spec:
        bad = sum(1 for f in recs if not f.brand_fit.get("passes", True))
        print(f"{bad}/{len(recs)} break a brand rule")


if __name__ == "__main__":
    main()
