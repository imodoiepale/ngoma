"""Speech out — voiceover for reels and UGC, plus the bake-off that picks a provider.

The plan said to evaluate TTS providers against Kiswahili and Sheng quality before
committing, rather than defaulting to whatever is popular. That is not caution for its own
sake: English TTS is close to solved, Kiswahili is serviceable at best, and **Sheng is not
supported by anything** — it is code-switched Nairobi slang with no training data and no
standard orthography.

So this module does two things:

  1. `bake-off` renders the same script through every configured provider and produces a
     scoring sheet you listen to. It deliberately does not pick a winner — perceived
     naturalness in a language is not something a script can score, and a made-up metric
     would be worse than an honest blank column.
  2. `say` renders a line once a provider is chosen.

Sheng policy, enforced rather than advised: a Sheng script is refused unless
`--sheng-reviewed` is passed, because synthesised Sheng reliably comes out as
mispronounced Swahili and that reads as a brand that does not know its own audience.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out" / "voice"

# What each provider can genuinely do, recorded honestly. `sheng` is `none` everywhere
# because no TTS system supports it — listing it as "partial" would be wishful.
PROVIDERS: dict[str, dict[str, Any]] = {
    "piper": {
        "kind": "local",
        "cost": "free",
        "needs": "piper binary + a voice model (.onnx)",
        "languages": {"en": "good", "sw": "limited", "fr": "good", "sheng": "none"},
        "note": "fully offline and free. Swahili voices exist but are thin; audition before use.",
    },
    "elevenlabs": {
        "kind": "api",
        "cost": "per character",
        "needs": "ELEVENLABS_API_KEY",
        "languages": {"en": "excellent", "sw": "fair", "fr": "excellent", "sheng": "none"},
        "note": "strongest English/French. Multilingual model handles Swahili with an accent.",
    },
    "openai": {
        "kind": "api",
        "cost": "per character",
        "needs": "OPENAI_API_KEY",
        "languages": {"en": "excellent", "sw": "fair", "fr": "good", "sheng": "none"},
        "note": "reliable, fast, limited voice range.",
    },
    "edge-tts": {
        "kind": "local-proxy",
        "cost": "free",
        "needs": "uv tool install edge-tts",
        "languages": {"en": "good", "sw": "fair", "fr": "good", "sheng": "none"},
        "note": "free Microsoft voices incl. sw-KE (Rafiki/Zuri). Best free Swahili option "
                "to audition first. Unofficial endpoint — do not build a product on it.",
    },
}

SHENG_REFUSAL = (
    "This script is marked Sheng. No TTS system supports Sheng — it is code-switched "
    "Nairobi slang with no training data and no standard orthography, so every provider "
    "will render it as mispronounced Swahili. That reads as a brand that does not know its "
    "own audience.\n"
    "  Options: record a human voice, or rewrite in Kiswahili/Kenyan English.\n"
    "  To override anyway (you have listened and accepted it): --sheng-reviewed"
)


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


class TTSError(RuntimeError):
    pass


@dataclass
class Take:
    provider: str
    language: str
    text: str
    path: str | None = None
    duration_s: float | None = None
    status: str = "pending"
    error: str | None = None
    # Left blank on purpose — a human fills these in after listening.
    score_naturalness: str = ""
    score_pronunciation: str = ""
    notes: str = ""


def available(provider: str) -> tuple[bool, str]:
    if provider not in PROVIDERS:
        raise TTSError(f"unknown provider {provider!r}; have {sorted(PROVIDERS)}")
    if provider == "piper":
        return (shutil.which("piper") is not None, "piper binary on PATH")
    if provider == "edge-tts":
        return (shutil.which("edge-tts") is not None, "edge-tts on PATH")
    env = {"elevenlabs": "ELEVENLABS_API_KEY", "openai": "OPENAI_API_KEY"}[provider]
    return (bool(_secret(env)), env)


def _duration(p: Path) -> float | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(p)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return round(float(r.stdout.strip()), 2)
    except Exception:  # noqa: BLE001
        return None


def _edge_tts(text: str, lang: str, dest: Path) -> None:
    voice = {"sw": "sw-KE-RafikiNeural", "en": "en-KE-ChilembaNeural",
             "en-KE": "en-KE-ChilembaNeural", "fr": "fr-FR-HenriNeural"}.get(lang, "en-US-GuyNeural")
    r = subprocess.run(["edge-tts", "--voice", voice, "--text", text,
                        "--write-media", str(dest)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    if r.returncode != 0 or not dest.exists():
        raise TTSError(f"edge-tts failed: {(r.stderr or r.stdout)[:250]}")


def _openai(text: str, lang: str, dest: Path, voice: str = "onyx") -> None:
    key = _secret("OPENAI_API_KEY")
    if not key:
        raise TTSError("OPENAI_API_KEY not set")
    body = json.dumps({"model": "gpt-4o-mini-tts", "voice": voice, "input": text}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=body,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            dest.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        raise TTSError(f"openai tts failed ({e.code}): "
                       f"{e.read().decode('utf-8','replace')[:200]}") from e


def _elevenlabs(text: str, lang: str, dest: Path,
                voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> None:
    key = _secret("ELEVENLABS_API_KEY")
    if not key:
        raise TTSError("ELEVENLABS_API_KEY not set")
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            dest.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        raise TTSError(f"elevenlabs failed ({e.code}): "
                       f"{e.read().decode('utf-8','replace')[:200]}") from e


def _piper(text: str, lang: str, dest: Path) -> None:
    model = os.environ.get("PIPER_MODEL")
    if not model:
        raise TTSError("PIPER_MODEL is not set (path to a .onnx voice)")
    r = subprocess.run(["piper", "--model", model, "--output_file", str(dest)],
                       input=text, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    if r.returncode != 0 or not dest.exists():
        raise TTSError(f"piper failed: {(r.stderr or '')[:250]}")


RENDERERS = {"edge-tts": _edge_tts, "openai": _openai,
             "elevenlabs": _elevenlabs, "piper": _piper}


def render_take(provider: str, text: str, lang: str, dest: Path, dry_run: bool = True) -> Take:
    t = Take(provider=provider, language=lang, text=text)
    ok, need = available(provider)
    if not ok:
        t.status, t.error = "unavailable", f"requires {need}"
        return t
    if dry_run:
        t.status = "dry_run"
        return t
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        RENDERERS[provider](text, lang, dest)
        t.path, t.duration_s, t.status = str(dest), _duration(dest), "ok"
    except TTSError as e:
        t.status, t.error = "failed", str(e)
    return t


def bake_off(text: str, lang: str, dry_run: bool = True) -> list[Take]:
    takes = []
    for prov in PROVIDERS:
        dest = OUT / "bakeoff" / f"{lang}-{prov}.mp3"
        takes.append(render_take(prov, text, lang, dest, dry_run))
    return takes


def sheet(takes: list[Take], lang: str) -> str:
    L = [f"# TTS bake-off — {lang}", "",
         "Listen to each take and fill in the two score columns yourself. This file leaves",
         "them blank on purpose: perceived naturalness in a language is not something a",
         "script can measure, and an invented number would be worse than an honest blank.",
         "",
         "| provider | status | duration | naturalness /5 | pronunciation /5 | file |",
         "|---|---|---|---|---|---|"]
    for t in takes:
        L.append(f"| {t.provider} | {t.status}{' — ' + t.error if t.error else ''} "
                 f"| {t.duration_s or '—'} |  |  | "
                 f"{Path(t.path).name if t.path else '—'} |")
    L += ["", "## Declared language support", "",
          "| provider | en | sw | fr | sheng | cost | note |", "|---|---|---|---|---|---|---|"]
    for k, v in PROVIDERS.items():
        lv = v["languages"]
        L.append(f"| {k} | {lv['en']} | {lv['sw']} | {lv['fr']} | **{lv['sheng']}** "
                 f"| {v['cost']} | {v['note']} |")
    L += ["", "Sheng is `none` everywhere because no TTS system supports it. Record a human,",
          "or write the line in Kiswahili or Kenyan English."]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Voiceover rendering and provider bake-off.")
    ap.add_argument("command", choices=["providers", "bake-off", "say"])
    ap.add_argument("--text", default="Ongea Pesa. Sema, tuma, imekwisha.")
    ap.add_argument("--lang", default="sw")
    ap.add_argument("--provider")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--live", action="store_true", help="actually render audio")
    ap.add_argument("--sheng-reviewed", action="store_true",
                    help="override the Sheng refusal, having listened and accepted it")
    a = ap.parse_args()

    if a.lang == "sheng" and not a.sheng_reviewed:
        raise SystemExit(SHENG_REFUSAL)

    if a.command == "providers":
        for k, v in PROVIDERS.items():
            ok, need = available(k)
            print(f"{k:<12} {'READY' if ok else 'not configured':<16} {v['cost']:<12} "
                  f"sw={v['languages']['sw']:<9} needs: {need}")
        return

    if a.command == "bake-off":
        takes = bake_off(a.text, a.lang, dry_run=not a.live)
        md = sheet(takes, a.lang)
        print(md)
        out = a.out or OUT / f"bakeoff-{a.lang}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        (out.with_suffix(".json")).write_text(
            json.dumps([asdict(t) for t in takes], indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n-> {out}")
        if not a.live:
            print("(dry run — pass --live to render audio from the configured providers)")
        return

    if not a.provider:
        raise SystemExit("--provider is required for `say`; run `providers` to see what is ready")
    dest = a.out or OUT / f"{a.lang}-{a.provider}.mp3"
    t = render_take(a.provider, a.text, a.lang, dest, dry_run=not a.live)
    print(json.dumps(asdict(t), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except TTSError as e:
        raise SystemExit(f"error: {e}")
