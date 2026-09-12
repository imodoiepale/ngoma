"""Brand kit loader + prompt builder.

Single source of truth for reading `brands/<brand>/{brand.yaml,styles/*.yaml,calendar/seed.yaml}`
and turning a calendar item + a style grammar into a provider-agnostic generation request.

Hard invariants enforced here (not left to the model):
  * the model is never asked to render text or any mark
  * the negative prompt always carries the style's full negative list
  * claim_class `sensitive` / `pitch` items are flagged for human approval
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
BRANDS = REPO / "brands"

RATIO_PX = {
    "1:1": (3840, 3840),
    "4:5": (3072, 3840),
    "3:4": (2880, 3840),
    "9:16": (2160, 3840),
    "16:9": (3840, 2160),
}


class BrandError(ValueError):
    pass


def _load_yaml(p: Path) -> dict[str, Any]:
    if not p.exists():
        raise BrandError(f"missing required file: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BrandError(f"{p} did not parse to a mapping")
    return data


@dataclass(frozen=True)
class Brand:
    key: str
    root: Path
    spec: dict[str, Any]
    styles: dict[str, dict[str, Any]]
    calendar: dict[str, Any]

    @property
    def palette(self) -> dict[str, str]:
        return self.spec["palette"]["measured"]

    @property
    def logo_master(self) -> Path:
        return self.root / self.spec["logo"]["master"]

    def style(self, key: str) -> dict[str, Any]:
        if key not in self.styles:
            raise BrandError(f"unknown style {key!r}; have {sorted(self.styles)}")
        return self.styles[key]

    def item(self, idea_id: int) -> dict[str, Any]:
        for it in self.calendar["items"]:
            if it["id"] == idea_id:
                return it
        raise BrandError(f"no calendar item with id {idea_id}")


def load_brand(key: str) -> Brand:
    root = BRANDS / key
    spec = _load_yaml(root / "brand.yaml")
    styles = {
        p.stem: _load_yaml(p)
        for p in sorted((root / "styles").glob("*.yaml"))
        if p.stem != "index"
    }
    if not styles:
        raise BrandError(f"no style grammars under {root/'styles'}")
    calendar_path = root / "calendar" / "seed.yaml"
    calendar = _load_yaml(calendar_path) if calendar_path.exists() else {"items": []}

    logo = root / spec["logo"]["master"]
    if not logo.exists():
        raise BrandError(f"logo master declared but absent: {logo}")

    # Fail loudly if the calendar points at a style grammar that does not exist.
    unknown = sorted({
        it["style_family"] for it in calendar.get("items", [])
        if it.get("style_family") and it["style_family"] not in styles
    })
    if unknown:
        raise BrandError(
            f"{calendar_path} references unknown style_family {unknown}; "
            f"available: {sorted(styles)}"
        )
    return Brand(key=key, root=root, spec=spec, styles=styles, calendar=calendar)


@dataclass
class GenRequest:
    """Provider-agnostic request. The router maps this onto a concrete endpoint."""
    brand: str
    idea_id: int | None
    style_key: str
    ratio: str
    width: int
    height: int
    prompt: str
    negative_prompt: str
    copy_block: dict[str, str]
    claim_class: str
    requires_human_approval: bool
    semantic_key: str = field(default="", repr=False)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _semantic_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def build_prompt(style: dict[str, Any], subject_override: str | None = None) -> str:
    """Compose the positive prompt from a style grammar.

    Ordered the way image models weight it: format, background, subject, composition,
    light, palette, finish, then the explicit no-text instruction.
    """
    subject = subject_override or style["subject"]
    palette = ", ".join(style["palette"])
    segments = [
        f"{style['ratios'][0]} composition, full-bleed, fully opaque.",
        f"BACKGROUND: {style['background']}.",
        f"SUBJECT: {subject}.",
        f"COMPOSITION: {style['composition']}.",
        f"LIGHT: {style['light']}.",
        f"PALETTE: strictly {palette}. {style['accent_use']}.",
        f"FINISH: {style['finish']}.",
        f"CULTURAL DIRECTION: {style['cultural']}.",
        "Render the image only. Do not draw any text, letters, numbers, logos or marks "
        "anywhere in the frame; typography and branding are applied afterwards.",
    ]
    return " ".join(segments)


def build_request(
    brand: Brand,
    idea_id: int | None = None,
    style_key: str | None = None,
    ratio: str | None = None,
    subject_override: str | None = None,
    copy_block: dict[str, str] | None = None,
) -> GenRequest:
    item: dict[str, Any] = {}
    if idea_id is not None:
        item = brand.item(idea_id)
    key = style_key or item.get("style_family")
    if not key:
        raise BrandError("need either idea_id (with style_family) or an explicit style_key")
    style = brand.style(key)

    chosen = ratio or style["ratios"][0]
    if chosen not in RATIO_PX:
        raise BrandError(f"unsupported ratio {chosen!r}; have {sorted(RATIO_PX)}")
    if chosen not in style["ratios"]:
        raise BrandError(
            f"style {key!r} declares ratios {style['ratios']}; {chosen!r} is not one of them"
        )
    w, h = RATIO_PX[chosen]

    claim_class = item.get("claim_class", "standard")
    copy = copy_block or {
        "headline": (item.get("hook") or "").upper(),
        "subhead": item.get("idea", ""),
        "cta": item.get("cta", ""),
        "attribution": brand.spec["positioning"]["attribution_line"],
        "disclosure": brand.spec["claim_safety"]["disclosure"],
    }

    prompt = build_prompt(style, subject_override)
    return GenRequest(
        brand=brand.key,
        idea_id=idea_id,
        style_key=key,
        ratio=chosen,
        width=w,
        height=h,
        prompt=prompt,
        negative_prompt=style["negative_prompt"],
        copy_block=copy,
        claim_class=claim_class,
        requires_human_approval=claim_class in ("sensitive", "pitch"),
        semantic_key=_semantic_key(brand.key, key, chosen, prompt),
        meta={
            "mode": style["mode"],
            "angle": item.get("angle"),
            "format": item.get("format"),
            "language_mix": item.get("language_mix", [brand.spec["languages"]["primary"]]),
            "sheng_intensity": item.get("sheng_intensity", "none"),
        },
    )


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Build a generation request from the brand kit.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--idea", type=int)
    ap.add_argument("--style")
    ap.add_argument("--ratio")
    ap.add_argument("--subject")
    ap.add_argument("--list-styles", action="store_true")
    ap.add_argument("--list-ideas", action="store_true")
    a = ap.parse_args()

    b = load_brand(a.brand)
    if a.list_styles:
        for k, s in sorted(b.styles.items()):
            print(f"{k:<28} {s['mode']:<24} {','.join(s['ratios'])}")
        return
    if a.list_ideas:
        for it in b.calendar["items"]:
            flag = "!" if it["claim_class"] != "standard" else " "
            print(f"{it['id']:>3}{flag} {it['idea']:<24} {it['style_family']:<28} {it['format']}")
        return
    if a.idea is None and not a.style:
        ap.error("pass --idea N or --style KEY (or --list-ideas / --list-styles)")
    req = build_request(b, a.idea, a.style, a.ratio, a.subject)
    print(json.dumps(req.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
