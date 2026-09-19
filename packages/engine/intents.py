"""Intent rules for what a person says to the studio.

Two layers share this file:

- `intent(text)`: one director utterance ("add a scene at a rooftop", "10 angles per scene",
  "wardrobe from my red-dress") becomes a named change to the brief. Moved here from
  `session.intent`; `session` re-exports it. Unknown text is a `note`.
- The describe layer: `refusal(text)` applies the FORBIDDEN rule (no person's name or
  likeness) before any node exists; `continuation(text)` recognises "now add ...", "also ...",
  "then ..." on an existing workflow and returns what to add; `route(text)` decides whether a
  sentence is a director piece (a profile or preset is named) or an author brief.

The brief rules themselves (swap, per-item, slides, sequencing, collections) live in
`workflow_author.parse_brief`, because the author route and the canvas use them without
the engine. Keyword rules only; nothing here calls a model.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import profiles  # noqa: E402
from presets import FORBIDDEN, load_presets  # noqa: E402

NUM = r"(\d+)"
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "twenty": 20}


@dataclass
class Intent:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


def _n(text: str) -> int | None:
    m = re.search(NUM, text)
    if m:
        return int(m.group(1))
    for w, v in WORDS.items():
        if re.search(rf"\b{w}\b", text):
            return v
    return None


# ---------------------------------------------------------------- director utterances

def intent(text: str) -> Intent:
    """Keyword rules, in the style of workflow_author.BRIEF_RULES. Unknown text is `note`."""
    t = text.strip()
    low = t.lower()
    presets = load_presets()["presets"]
    if re.search(r"\bundo\b", low):
        return Intent("undo")
    if m := re.search(r"\b(?:pick|keep|choose)\b.*?\b(?:at|on|for)\s+([a-z0-9.\-]+)\s*[:\s]\s*([\d,\s]+)$", low):
        return Intent("pick", {"node": m.group(1), "indices": [int(x) for x in re.findall(r"\d+", m.group(2))]})
    if re.search(r"\b(mode|switch to)\b.*\b(dry|approval|stage|auto)", low):
        word = re.search(r"\b(dry[- ]?run|dry|stage[- ]approval|approval|stage|auto(?:matic)?)\b", low).group(1)
        return Intent("mode", {"mode": word})
    if re.search(r"\brun\b", low) and re.search(r"\b(stage|next|all|everything|it)\b", low):
        m = re.search(r"\brun\s+(?:the\s+)?([a-z0-9\-]+)", low)
        target = m.group(1) if m else "next"
        return Intent("run", {"stage": "all" if target in ("all", "everything") else ("next" if target in ("next", "it", "stage", "the") else target)})
    if re.search(r"\b(add|another|new)\b.*\bscene\b", low) or re.search(r"\bscene\b.*\b(at|in|on|of)\b", low) and not re.search(r"\bangles?\b", low):
        hint = re.sub(r"^.*?\bscene\b\s*(?:\d+)?\s*(?:at|in|on|of|:)?\s*", "", t, flags=re.I).strip(" .")
        return Intent("add_scene", {"hint": hint})
    if m := re.search(r"\b(\d+|" + "|".join(WORDS) + r")\s+scenes\b", low):
        return Intent("set_scenes", {"n": _n(m.group(0))})
    if re.search(r"\bangles?\b|\bcameras?\b", low) and _n(low):
        return Intent("set_angles", {"k": _n(low)})
    if re.search(r"\b(takes?|seeds?|variants?)\b", low) and _n(low):
        return Intent("set_seeds", {"n": _n(low)})
    if re.search(r"\b(second|seconds|sec|s)\b", low) and re.search(r"\b(video|clip|clips|long)\b", low):
        return Intent("video", {"seconds": [int(x) for x in re.findall(r"(\d+)\s*(?:seconds|second|sec|s)\b", low)] or [_n(low)]})
    if m := re.search(r"\b(?:aesthetic|preset|style|look|like)\b\s*(?:of|:)?\s*([a-z][a-z \-]+)$", low):
        name = m.group(1).strip()
        key = name.replace(" ", "-")
        by_label = {p["label"].lower(): k for k, p in presets.items()}
        if key in presets or name in by_label:
            return Intent("preset", {"name": name})
    for key, p in presets.items():
        if key in low or p["label"].lower() in low:
            return Intent("preset", {"name": key})
    if prof := profiles.find(low):
        return Intent("profile", {"name": prof})
    if m := re.search(r"\b(wardrobe|clothes|outfit|location|room|set|jewell?ery|props?|motion clip|reference video)\b\s*(?:from|:|called|named)?\s*(?:my|the|our|own|owned|licensed)?\s*([a-z0-9][a-z0-9\-_ ]*)$", low):
        purpose = {"clothes": "wardrobe", "outfit": "wardrobe", "room": "location", "set": "location", "jewelry": "jewellery",
                   "prop": "jewellery", "props": "jewellery", "motion clip": "motion", "reference video": "motion"}.get(m.group(1), m.group(1))
        rights = "owned" if re.search(r"\b(my|mine|own|owned)\b", low) else ("licensed" if "licensed" in low else "unclear")
        use = "inspiration" if re.search(r"\b(inspiration|inspo|mood)\b", low) else "data"
        return Intent("attach_ref", {"purpose": purpose, "name": m.group(2).strip().replace(" ", "-"), "rights": rights, "use": use,
                                     "kind": "video" if purpose == "motion" else "image"})
    if m := re.search(r"\b(?:vfx|effect)\b\s*(?:called|:)?\s*([a-z][a-z\-]*)", low):
        return Intent("vfx", {"name": m.group(1)})
    if m := re.search(r"\b(?:add|new)\s+(?:a\s+)?role\s+([a-z][a-z0-9\-]*)(?:\s+from\s+([a-z0-9\-]+))?", low):
        return Intent("role", {"name": m.group(1), "ref_collection": m.group(2) or "", "consent": "consent" in low or "released" in low})
    return Intent("note", {"text": t})


# ---------------------------------------------------------------- the describe layer

CONTINUATION = re.compile(
    r"^\s*(?:ok(?:ay)?[,.]?\s*)?(?:(?:and|now|also|next|then|after that|afterwards|plus|additionally|finally)[,.]?\s+)*"
    r"(?:please\s+)?(?:add|append|include|attach|put in|follow (?:it |that )?with|continue with|chain|extend (?:it |this )?with|"
    r"(?:i|we)(?:'d| would)? (?:also )?(?:want|need|like)(?: to add)?)\b\s*(.*)$", re.I)
CONTINUATION_LEAD = re.compile(r"^\s*(?:ok(?:ay)?[,.]?\s*)?(?:now|also|next|then|after that|afterwards|plus|additionally|finally)\b[,.]?\s+(.*)$", re.I)


def refusal(text: str) -> str | None:
    """The FORBIDDEN rule at brief level: a person's name, a likeness or an attribution
    phrase is refused before any node exists, with the offending words named."""
    m = FORBIDDEN.search(text or "")
    if not m:
        return None
    return (f"The brief names a person or a likeness ({m.group(0)!r}). Describe the look instead: "
            "framing, lens, palette, pacing, blocking. Presets and profiles are grammar, never a name.")


def continuation(text: str) -> str | None:
    """"now add captions and export" -> "captions and export"; "also a carousel for each" ->
    "a carousel for each". None when the text does not read as an addition."""
    m = CONTINUATION.match(text or "")
    if m and m.group(1).strip():
        return m.group(1).strip(" .")
    m = CONTINUATION_LEAD.match(text or "")
    if m and m.group(1).strip():
        return m.group(1).strip(" .")
    return None


def matched_preset(text: str) -> str | None:
    low = (text or "").lower()
    for key, p in load_presets()["presets"].items():
        if key in low or p["label"].lower() in low:
            return key
    return None


def route(text: str) -> str:
    """`director` when the sentence names a profile (a lookbook, an explainer, a music
    video piece) or a preset (a look); `author` otherwise. The director grows scenes and
    angles from a brief; the author wires named steps."""
    if profiles.find(text or "") or matched_preset(text):
        return "director"
    return "author"
