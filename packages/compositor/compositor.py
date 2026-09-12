"""Deterministic brand compositor.

The image model produces the base visual ONLY. Every piece of text and the logo are
applied here, in code, from `brand.yaml` — so spelling, palette and the lockup are exact
and reproducible. This is the difference between a brand system and a slot machine.

Outputs a master PNG at the ratio's full resolution plus a sidecar JSON manifest
(sha256, campaign id, provenance) so publishing can verify what it is about to post.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]

# Font resolution: prefer a real Inter/Inter Tight if installed, else the platform's
# best condensed grotesque, else Pillow's bitmap default (which we warn about).
_FONT_CANDIDATES = {
    "headline": ["InterTight-ExtraBold.ttf", "Inter-ExtraBold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "subhead": ["Inter-SemiBold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "body": ["Inter-Regular.ttf", "arial.ttf", "DejaVuSans.ttf"],
    "micro": ["IBMPlexMono-Regular.ttf", "consola.ttf", "DejaVuSansMono.ttf"],
}
_FONT_DIRS = [
    Path(r"C:\Windows\Fonts"),
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
    REPO / "packages/compositor/fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
]


class CompositorError(RuntimeError):
    pass


def _find_font(role: str, size: int) -> tuple[ImageFont.FreeTypeFont, str]:
    for name in _FONT_CANDIDATES[role]:
        for d in _FONT_DIRS:
            p = d / name
            if p.exists():
                return ImageFont.truetype(str(p), size), name
    raise CompositorError(
        f"no usable font for role {role!r}. Tried {_FONT_CANDIDATES[role]} in {[str(d) for d in _FONT_DIRS]}. "
        f"Install Inter or drop TTFs into packages/compositor/fonts/."
    )


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def chan(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


@dataclass
class CompositeResult:
    path: Path
    manifest_path: Path
    sha256: str
    contrast: float
    warnings: list[str]


def composite(
    base: Path | Image.Image,
    brand_spec: dict[str, Any],
    brand_root: Path,
    copy_block: dict[str, str],
    ratio: str,
    size: tuple[int, int],
    out_dir: Path,
    campaign_id: str,
    slide: tuple[int, int] | None = None,
    provenance: dict[str, Any] | None = None,
    dark_ground: bool = True,
) -> CompositeResult:
    warnings: list[str] = []
    pal = brand_spec["palette"]["measured"]

    im = (Image.open(base) if isinstance(base, Path) else base).convert("RGB")
    if im.size != size:
        im = _cover_resize(im, size)
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")

    ground = _hex(pal["ground"] if dark_ground else pal["surface"])
    ink = _hex("#EDEDED") if dark_ground else _hex(pal["hairline"])
    accent = _hex(pal["accent"])

    margin = int(W * 0.07)
    max_w = W - 2 * margin

    # Scrim behind the copy zone so contrast is guaranteed regardless of the base image.
    scrim_h = int(H * 0.42)
    for y in range(scrim_h):
        a = int(215 * (1 - y / scrim_h) ** 1.35)
        d.line([(0, y), (W, y)], fill=(*ground, a))

    y = margin

    headline = (copy_block.get("headline") or "").strip()
    if headline:
        f, fname = _find_font("headline", int(H * 0.052))
        for line in _wrap(d, headline, f, max_w):
            d.text((margin, y), line, font=f, fill=ink)
            y += int(f.size * 1.08)
        y += int(H * 0.012)
        # accent rule
        d.rectangle([margin, y, margin + int(W * 0.10), y + max(3, int(H * 0.004))], fill=accent)
        y += int(H * 0.030)

    subhead = (copy_block.get("subhead") or "").strip()
    if subhead:
        f, _ = _find_font("subhead", int(H * 0.024))
        for line in _wrap(d, subhead, f, int(max_w * 0.82)):
            d.text((margin, y), line, font=f, fill=ink)
            y += int(f.size * 1.28)

    # Measured contrast of composited ink against the scrimmed ground.
    ratio_val = contrast_ratio(ink, ground)
    if ratio_val < 4.5:
        warnings.append(f"contrast {ratio_val:.2f}:1 below 4.5:1 minimum")

    # Bottom furniture. The logo owns the bottom-left band; copy stacks ABOVE it so the
    # two can never collide regardless of ratio.
    fb, _ = _find_font("body", int(H * 0.020))
    fm, _ = _find_font("micro", int(H * 0.012))

    # Bottom scrim so the furniture reads over any base image.
    foot_h = int(H * 0.26)
    for i in range(foot_h):
        y_ = H - 1 - i
        a = int(225 * (1 - i / foot_h) ** 1.3)
        d.line([(0, y_), (W, y_)], fill=(*ground, a))

    logo_box = _paste_logo(im, brand_spec, brand_root, margin=margin, dark_ground=dark_ground)
    by = logo_box[1] - int(H * 0.022)          # baseline ceiling: just above the logo plate

    disclosure = (copy_block.get("disclosure") or "").strip()
    if disclosure:
        d.text((margin, by - fm.size), disclosure, font=fm, fill=(*ink, 165))
        by -= int(fm.size * 2.4)

    attribution = (copy_block.get("attribution") or "").strip()
    if attribution:
        d.text((margin, by - fm.size), attribution, font=fm, fill=(*accent, 240))
        by -= int(fm.size * 2.6)

    cta = (copy_block.get("cta") or "").strip()
    if cta:
        for line in reversed(_wrap(d, cta, fb, int(max_w * 0.78))):
            d.text((margin, by - fb.size), line, font=fb, fill=ink)
            by -= int(fb.size * 1.32)

    if slide:
        n, total = slide
        txt = f"{n:02d}/{total:02d}"
        d.text((W - margin - d.textlength(txt, font=fm), logo_box[3] - fm.size),
               txt, font=fm, fill=(*ink, 205))

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{campaign_id}_{ratio.replace(':','x')}" + (f"_{slide[0]:02d}" if slide else "")
    path = out_dir / f"{stem}.png"
    im.save(path, "PNG", optimize=True)

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "campaign_id": campaign_id,
        "file": path.name,
        "sha256": digest,
        "ratio": ratio,
        "size": list(size),
        "copy_block": copy_block,
        "contrast_ratio": round(ratio_val, 2),
        "warnings": warnings,
        "logo_master_sha256": hashlib.sha256(
            (brand_root / brand_spec["logo"]["master"]).read_bytes()).hexdigest(),
        "composited_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "provenance": provenance or {},
    }
    mpath = out_dir / f"{stem}.json"
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return CompositeResult(path, mpath, digest, ratio_val, warnings)


def _cover_resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    sw, sh = im.size
    scale = max(tw / sw, th / sh)
    im = im.resize((max(tw, int(sw * scale)), max(th, int(sh * scale))), Image.LANCZOS)
    left, top = (im.width - tw) // 2, (im.height - th) // 2
    return im.crop((left, top, left + tw, top + th))


def _paste_logo(im: Image.Image, spec: dict[str, Any], brand_root: Path,
                margin: int, dark_ground: bool) -> tuple[int, int, int, int]:
    """Composite the approved lockup and return its bounding box (x0, y0, x1, y1).

    The master is never recoloured, redrawn or filtered. The Ongea Pesa lockup is navy
    and pale cyan, which is illegible directly on the #0A0A0A ground, so on dark grounds
    it is placed on a pearl plate with the brand's declared clear space. That is a
    placement decision, not a modification of the mark.
    """
    cfg = spec["logo"]
    logo = Image.open(brand_root / cfg["master"]).convert("RGBA")
    target_w = int(im.width * float(cfg.get("min_width_pct", 12)) / 100)
    scale = target_w / logo.width
    logo = logo.resize((target_w, max(1, int(logo.height * scale))), Image.LANCZOS)

    pad = int(logo.height * float(cfg.get("clear_space_ratio", 0.5)))
    x0, y1 = margin, im.height - margin
    if dark_ground:
        plate_w, plate_h = logo.width + 2 * pad, logo.height + 2 * pad
        px0, py0 = x0, y1 - plate_h
        plate = Image.new("RGBA", (plate_w, plate_h), (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            [0, 0, plate_w - 1, plate_h - 1], radius=int(pad * 0.9),
            fill=(*_hex(spec["palette"]["measured"]["surface"]), 255))
        plate.alpha_composite(logo, (pad, pad))
        im.paste(plate, (px0, py0), plate)
        return (px0, py0, px0 + plate_w, py0 + plate_h)

    ly0 = y1 - logo.height
    im.paste(logo, (x0, ly0), logo)
    return (x0, ly0, x0 + logo.width, y1)


def _cli() -> None:
    import argparse
    import sys
    sys.path.insert(0, str(REPO / "packages" / "brandkit"))
    from brandkit import load_brand, RATIO_PX  # noqa: E402

    ap = argparse.ArgumentParser(description="Composite brand copy + logo onto a base image.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--idea", type=int)
    ap.add_argument("--ratio", default="4:5")
    ap.add_argument("--campaign-id", default=None)
    ap.add_argument("--slide", help="N/TOTAL, e.g. 1/5")
    ap.add_argument("--out", type=Path, default=REPO / "out")
    ap.add_argument("--light", action="store_true", help="composite on the light surface instead of the dark ground")
    a = ap.parse_args()

    b = load_brand(a.brand)
    if a.idea:
        it = b.item(a.idea)
        copy_block = {
            "headline": (it["hook"] or "").upper(),
            "subhead": it["idea"],
            "cta": it["cta"],
            "attribution": b.spec["positioning"]["attribution_line"],
            "disclosure": b.spec["claim_safety"]["disclosure"],
        }
        cid = a.campaign_id or f"{a.brand}-idea{a.idea:02d}"
    else:
        copy_block = {
            "headline": b.spec["positioning"]["tagline"].upper(),
            "subhead": b.spec["positioning"]["promise"],
            "cta": b.spec["positioning"]["ctas"][0],
            "attribution": b.spec["positioning"]["attribution_line"],
            "disclosure": b.spec["claim_safety"]["disclosure"],
        }
        cid = a.campaign_id or f"{a.brand}-tagline"

    slide = None
    if a.slide:
        n, t = a.slide.split("/")
        slide = (int(n), int(t))

    r = composite(a.base, b.spec, b.root, copy_block, a.ratio, RATIO_PX[a.ratio],
                  a.out, cid, slide=slide, dark_ground=not a.light)
    print(f"{r.path}\n  sha256   {r.sha256}\n  contrast {r.contrast:.2f}:1")
    for w in r.warnings:
        print(f"  WARNING  {w}")


if __name__ == "__main__":
    _cli()
