"""Speech in — turn a spoken brief into a structured one.

Control-in half of the voice layer. You talk; this transcribes, extracts what a brief
actually needs (brand, format, idea, language, constraints), and prints it **for you to
confirm in text**.

The confirmation is not a formality. Voice is lossy in exactly the places that cost money:
"Ongea" and "Ongeya", "four by five" and "forty-five", a brand name heard as a common noun.
So this module's contract is narrow and absolute:

    It produces a brief. It never generates, spends or publishes.

Backend: faster-whisper, local, no key, and good at Kiswahili and French. Install on demand:

    uv tool install faster-whisper        # or: uv run --with faster-whisper ...

Sheng is the known weak spot — it is code-switched Swahili/English slang that no ASR model
is trained on. Expect it to be transcribed as malformed Swahili. That is why the extracted
brief is shown as text before anything acts on it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

FORMATS = {"carousel": ["carousel", "slides", "swipe"],
           "reel": ["reel", "video", "short", "tiktok"],
           "single": ["single", "post", "image", "picture", "still"],
           "story": ["story", "status"]}
RATIOS = {"9:16": ["nine by sixteen", "9 by 16", "vertical", "portrait video"],
          "4:5": ["four by five", "4 by 5", "portrait"],
          "1:1": ["one by one", "square"],
          "16:9": ["sixteen by nine", "landscape", "wide"]}
LANGS = {"sw": ["swahili", "kiswahili"], "sheng": ["sheng"], "fr": ["french", "francais"],
         "en-KE": ["kenyan english"], "en": ["english"]}


class VoiceError(RuntimeError):
    pass


@dataclass
class SpokenBrief:
    transcript: str
    language_detected: str | None = None
    duration_s: float | None = None
    brand: str | None = None
    format: str | None = None
    ratio: str | None = None
    languages: list[str] = field(default_factory=list)
    idea: str = ""
    constraints: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    confidence: str = "unconfirmed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401,PLC0415
        return True
    except ImportError:
        return False


def transcribe(audio: Path, model_size: str = "base", language: str | None = None
               ) -> tuple[str, str | None, float | None]:
    if not audio.exists():
        raise VoiceError(f"audio not found: {audio}")
    if not whisper_available():
        raise VoiceError(
            "faster-whisper is not installed. Install it with:\n"
            "  uv tool install faster-whisper\n"
            "or run this module as:\n"
            "  uv run --with faster-whisper packages/voice/transcribe.py ...")
    from faster_whisper import WhisperModel  # noqa: PLC0415

    model = WhisperModel(model_size, device="auto", compute_type="int8")
    segments, info = model.transcribe(str(audio), language=language, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    return text, getattr(info, "language", None), getattr(info, "duration", None)


def known_brands() -> list[str]:
    return sorted(p.name for p in (REPO / "brands").iterdir() if (p / "brand.yaml").exists())


def extract(transcript: str, detected_lang: str | None = None) -> SpokenBrief:
    """Pull structure out of speech, and be explicit about what stayed ambiguous."""
    b = SpokenBrief(transcript=transcript, language_detected=detected_lang)
    # Punctuation must not hide a keyword: "and sheng," only matches once the comma is gone.
    low = " " + re.sub(r"[^a-z0-9']+", " ", transcript.lower()).strip() + " "

    # brand — match on the real directory names, and on a loose spoken form
    for brand in known_brands():
        spoken = brand.replace("-", " ")
        if f" {spoken} " in low or f" {brand} " in low:
            b.brand = brand
            break
    if not b.brand:
        # "ongea pesa" is routinely heard as "ongeya pesa" / "angea pesa"
        if re.search(r"\bo?n[gj]e[a-z]{0,2}\s+pesa\b", low):
            b.brand = "ongea-pesa"
            b.ambiguities.append("brand heard approximately as 'ongea pesa' — confirm")
        elif re.search(r"\bep+a+l+e?\b", low):
            b.brand = "epalle"
            b.ambiguities.append("brand heard approximately as 'epalle' — confirm")
        else:
            b.ambiguities.append(f"no brand named; known brands are {', '.join(known_brands())}")

    for fmt, words in FORMATS.items():
        if any(f" {w} " in low for w in words):
            b.format = fmt
            break
    if not b.format:
        b.ambiguities.append("no format named (carousel / reel / single / story)")

    for ratio, words in RATIOS.items():
        if any(w in low for w in words):
            b.ratio = ratio
            break

    for code, words in LANGS.items():
        if any(f" {w} " in low for w in words):
            b.languages.append(code)
    if "sheng" in low:
        b.ambiguities.append(
            "Sheng was requested. No ASR model handles Sheng reliably, so any Sheng in this "
            "recording is likely mistranscribed. Write Sheng copy by hand.")

    # Constraints - the "no X" / "don't X" clauses people actually say. Stop at a
    # conjunction, or "no orange teal grade and don't show till numbers" collapses into one
    # constraint ending in "and don".
    stop = r"(?:\band\b|\bbut\b|\balso\b|\bthen\b|\bor\b|[.,;])"
    for m in re.finditer(r"\b(?:no|don'?t|avoid|without)\s+(.+?)(?=\s*" + stop + r"|$)",
                         " " + transcript.lower() + " "):
        c = re.sub(r"\s+", " ", m.group(1)).strip(" .,'")
        if 2 < len(c) < 60:
            b.constraints.append(c)

    # The idea is what remains once the machinery is stripped: the instruction verb, the
    # brand, the format, the ratio, the language list, and every constraint clause.
    idea = transcript
    strip_pats = [
        r"\b(?:make|create|generate|build|do)\s+(?:me\s+)?(?:an?\s+)?",
        r"\bfor\s+(?:onge[a-z]*\s*pesa|epalle)\b",
        # Bare, because the verb pattern above already ate the article: "generate a reel"
        # becomes "reel" before this runs.
        r"\b(?:as\s+)?(?:an?\s+)?(?:carousel|reel|single|story|post)\b",
        r"\bin\s+(?:swahili|kiswahili|sheng|french|english|kenyan\s+english)"
        r"(?:\s*(?:,|and)\s*(?:swahili|kiswahili|sheng|french|english))*\b",
        r"\b(?:four\s+by\s+five|nine\s+by\s+sixteen|one\s+by\s+one|"
        r"sixteen\s+by\s+nine|\d+\s*by\s*\d+|vertical|square|landscape|portrait)\b",
        r"\b(?:no|don'?t|avoid|without)\s+.+?(?=\s*(?:\band\b|[.,;])|$)",
    ]
    for pat in strip_pats:
        idea = re.sub(pat, " ", idea, flags=re.I)
    # Stripping clauses out of the middle of a sentence leaves orphaned punctuation
    # and dangling connectives. Tidy those rather than shipping "reel , , about a flower".
    idea = re.sub(r"\s*,\s*(?=,)", "", idea)          # collapse ", ,"
    idea = re.sub(r"\s*,\s*", ", ", idea)
    idea = re.sub(r"^[\s,;.]+", "", idea)
    idea = re.sub(r"^\s*(?:about|for|of|to)\s+", "", idea.strip(" ,."), flags=re.I)
    idea = re.sub(r"\s+", " ", idea).strip(" .,;")
    b.idea = re.sub(r"\s+(?:and|in|for)\s*$", "", idea, flags=re.I).strip(" .,;")

    if detected_lang and detected_lang not in ("en",) and not b.languages:
        b.languages.append(detected_lang)
        b.ambiguities.append(f"language auto-detected as '{detected_lang}' but not stated aloud")
    return b


def render(b: SpokenBrief) -> str:
    L = ["", "=" * 64, "SPOKEN BRIEF — confirm before anything runs", "=" * 64,
         f"heard: \"{b.transcript}\"", ""]
    if b.duration_s:
        L.append(f"({b.duration_s:.1f}s, detected language: {b.language_detected or 'unknown'})")
    L += ["", f"  brand      {b.brand or '— NOT IDENTIFIED'}",
          f"  format     {b.format or '— NOT IDENTIFIED'}",
          f"  ratio      {b.ratio or '(default for format)'}",
          f"  languages  {', '.join(b.languages) or '(brand default)'}",
          f"  idea       {b.idea or '—'}"]
    if b.constraints:
        L.append(f"  avoid      {', '.join(b.constraints)}")
    if b.ambiguities:
        L += ["", "  NEEDS YOUR CONFIRMATION:"]
        L += [f"    - {a}" for a in b.ambiguities]
    L += ["", "Nothing has been generated, spent or published. Voice produces a brief only.",
          "Next, by hand:",
          f"  uv run --with pyyaml packages/image-router/router.py "
          f"--brand {b.brand or '<brand>'} --style <style>", "=" * 64]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a spoken brief into a structured one.")
    ap.add_argument("audio", nargs="?", type=Path)
    ap.add_argument("--text", help="skip ASR and parse this text instead (for testing)")
    ap.add_argument("--model", default="base",
                    help="tiny|base|small|medium|large-v3 — base is a good default")
    ap.add_argument("--language", help="force a language instead of auto-detecting")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--check", action="store_true", help="report whether ASR is usable")
    ap.add_argument("--json", action="store_true", help="print only the brief as JSON (for the studio's director)")
    a = ap.parse_args()

    if a.check:
        ok = whisper_available()
        print(f"faster-whisper: {'installed' if ok else 'NOT installed'}")
        print(f"ffmpeg:         {shutil.which('ffmpeg') or 'NOT on PATH'}")
        print(f"known brands:   {', '.join(known_brands())}")
        raise SystemExit(0 if ok else 1)

    if a.text:
        b = extract(a.text)
    elif a.audio:
        text, lang, dur = transcribe(a.audio, a.model, a.language)
        b = extract(text, lang)
        b.duration_s = dur
    else:
        ap.error("pass an audio file, or --text for a dry parse, or --check")

    if a.json:
        print(json.dumps(b.to_dict(), ensure_ascii=False))
        return
    print(render(b))
    out = a.out or REPO / "out" / "spoken-brief.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(b.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    try:
        main()
    except VoiceError as e:
        raise SystemExit(f"error: {e}")
