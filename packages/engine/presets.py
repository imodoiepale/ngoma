"""Director presets: an aesthetic as grammar, turned into prompt fragments and node settings."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
PRESETS = REPO / "brands" / "_presets" / "directors.yaml"
GRAMMAR_KEYS = ("label", "inspired_by", "framing", "lens", "palette", "pacing", "blocking", "grade", "motion", "negatives")
# Words that would turn a grammar into a likeness. A preset may never contain them.
FORBIDDEN = re.compile(r"\b(anderson|refn|kubrick|tarantino|nolan|villeneuve|beyonc|rihanna|drake|kardashian|"
                       r"look[- ]?alike|face of|voice of|celebrity)\b", re.I)


class PresetError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_presets(path: Path = PRESETS) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, p in doc["presets"].items():
        missing = [k for k in GRAMMAR_KEYS if k not in p]
        if missing:
            raise PresetError(f"preset {key} lacks {missing}")
        text = " ".join(str(v) for v in p.values())
        if FORBIDDEN.search(text):
            raise PresetError(f"preset {key} names a person or a likeness; presets are grammar only")
    return doc


def preset(name: str) -> dict[str, Any]:
    doc = load_presets()
    if name not in doc["presets"]:
        raise PresetError(f"no preset {name!r}; known: {', '.join(sorted(doc['presets']))}")
    return doc["presets"][name]


def cameras(k: int) -> list[dict[str, str]]:
    table = load_presets()["cameras"]
    if k > len(table):
        raise PresetError(f"only {len(table)} camera angles are defined; asked for {k}")
    return table[:k]


def _cycle(items: list[str], i: int) -> str:
    return items[i % len(items)] if items else ""


def scene_fragments(p: dict[str, Any], scene_index: int) -> list[str]:
    """The preset's contribution to one scene: a framing and a blocking, plus the constants."""
    return [_cycle(p["framing"], scene_index), _cycle(p["blocking"], scene_index),
            f"shot on {p['lens']}", "palette: " + ", ".join(p["palette"]), p["grade"], p["motion"]]


def negatives(p: dict[str, Any]) -> str:
    return ", ".join(f"no {n}" for n in p.get("negatives", []))


def node_params(p: dict[str, Any], kind: str, seconds: int | None = None) -> dict[str, Any]:
    """Settings a preset implies for a step. Only keys the catalogue node actually has are kept
    by the caller."""
    out: dict[str, Any] = {}
    if kind in ("image-to-video", "long-video", "character-video", "text-to-video") and seconds:
        out["seconds"] = seconds
    if kind == "cut":
        out["seconds"] = 3 if "beat" in p["pacing"] else 8
    return out


def compose_prompt(scene_text: str, camera_prompt: str, fragments: list[str], extra: list[str] = ()) -> str:
    parts = [scene_text.strip(), camera_prompt] + list(fragments) + list(extra)
    return ". ".join(x.strip().rstrip(".") for x in parts if x and x.strip())
