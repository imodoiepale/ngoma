"""Director profiles: the craft of a kind of piece (beats, narration, locks), as opposed to
presets, which are the look. Both are grammar; neither names a person."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from presets import FORBIDDEN, PresetError

REPO = Path(__file__).resolve().parents[2]
PROFILES = REPO / "brands" / "_presets" / "profiles.yaml"
KEYS = ("label", "for", "beats", "default_scenes", "default_preset", "seconds", "narration", "generator",
        "locks", "negatives", "aspect")


@lru_cache(maxsize=1)
def load_profiles(path: Path = PROFILES) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, p in doc["profiles"].items():
        missing = [k for k in KEYS if k not in p]
        if missing:
            raise PresetError(f"profile {key} lacks {missing}")
        if FORBIDDEN.search(" ".join(str(v) for v in p.values())):
            raise PresetError(f"profile {key} names a person or a likeness")
        if p["generator"] not in ("character", "text"):
            raise PresetError(f"profile {key}: generator must be character or text")
    return doc


def profile(name: str) -> dict[str, Any]:
    doc = load_profiles()
    if name not in doc["profiles"]:
        raise PresetError(f"no profile {name!r}; known: {', '.join(sorted(doc['profiles']))}")
    return doc["profiles"][name]


def beat(p: dict[str, Any], i: int) -> str:
    beats = p["beats"]
    return beats[i] if i < len(beats) else f"{beats[-1]} {i - len(beats) + 2}"


def lock_fragments(p: dict[str, Any], theme: str | None = None) -> list[str]:
    out = list(p["locks"])
    if theme and p.get("theme", {}).get(theme):
        out.insert(0, p["theme"][theme])
    return out


def aspect_note(p: dict[str, Any], ratio: str) -> str:
    return p["aspect"].get(ratio, "")


def find(text: str) -> str | None:
    low = text.lower()
    for key, p in load_profiles()["profiles"].items():
        if key in low or p["label"].lower() in low:
            return key
    return None
