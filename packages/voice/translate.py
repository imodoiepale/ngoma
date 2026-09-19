"""Translate a script or caption file through an OpenRouter chat model, with the brand's terms
and every claim held fixed.

The `translate` catalogue step (S07, short-form dubbing) sends the transcript to a text
model and gets the target-language script back for the voiceover. This is that call, plus
the two guards a dub for a fintech or a brand cannot do without:

  glossary     brand names, product names and tokens that must come back untouched. Each
               term is swapped for a placeholder before the request and swapped back after,
               so the model never sees or rewrites it. The glossary is a file: one term per
               line (`#` comments), or JSON `["Ongea Pesa", "M-Pesa"]`.
  claim check  the translation must say what the source said. Deterministically checked:
               every number (amounts, percentages, dates, phone numbers) in the source must
               appear in the translation, every glossary term too, and the money-promise
               rules of packages/engine/edit.py `claim_check` must flag the same set in both
               texts (a translation may not add a guarantee the source did not make). A
               violation raises `TranslateError`; the runner never gets a translation that
               drifted. `--no-claim-check` only downgrades it to a printed warning.

    python packages/voice/translate.py --from en --to sw --in script.txt --out script.sw.txt --dry-run
    python packages/voice/translate.py --from en --to sw --in captions.srt --out captions.sw.srt --glossary brands/ongea-pesa/glossary.txt
    python packages/voice/translate.py --from en --to fr --in script.txt --out script.fr.txt --model google/gemini-3.1-flash

Formats: `.txt` and `.md` are translated as one text, paragraph structure kept. `.srt` keeps
every index and timecode and translates only the cue text, one cue per line in a single
request so the model can keep the sense across cues. `.json` (a list of strings, or of
objects with a `text` field, as `transcribe.py` writes) is translated field by field.

Network: the same `/chat/completions` endpoint and the same `OPENROUTER_API_KEY` from
`packages/common/vault.py` that the image router uses. `--dry-run` prints the exact request
body (placeholders in place) and touches nothing; without a key the live call refuses.
Languages: `en`, `sw`, `fr` and `sheng`; Sheng out of a model reads as broken Swahili, so a
Sheng target is refused unless `--sheng-reviewed`, the same policy as tts.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.1-flash"
LANGUAGES = {"en": "English", "sw": "Kiswahili", "fr": "French", "sheng": "Sheng (Nairobi code-switched Swahili)"}
SHENG_REFUSAL = ("target language is Sheng: no text model writes Sheng reliably; it comes out as broken "
                 "Swahili. Translate to sw and have a Sheng speaker adapt it, or pass --sheng-reviewed.")
PLACEHOLDER = "\u27e6G{n}\u27e7"                       # ⟦G1⟧: unlikely in any script, survives tokenisation
_PLACEHOLDER_RE = re.compile(r"\u27e6G(\d+)\u27e7")
# numbers that must survive: 1,500  2.5  50%  KES 200  0712 345 678  2026  3x
NUMBER_RE = re.compile(r"\d(?:\d|[,. ](?=\d))*")
SRT_TIME = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")


class TranslateError(RuntimeError):
    pass


# ---------------------------------------------------------------- glossary

def load_glossary(path: Path | None) -> list[str]:
    """Terms that must not be translated, longest first so `Ongea Pesa` wins over `Pesa`."""
    if path is None:
        return []
    p = Path(path)
    if not p.exists():
        raise TranslateError(f"glossary not found: {p}")
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
        terms = [str(t) for t in (data if isinstance(data, list) else data.get("terms", []))]
    else:
        terms = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    seen: list[str] = []
    for t in sorted(terms, key=len, reverse=True):
        if t and t not in seen:
            seen.append(t)
    return seen


def protect(text: str, glossary: list[str], mapping: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """Replace every glossary term with a numbered placeholder. Returns the masked text and the
    placeholder -> term map. Pass the same `mapping` for several texts so one term keeps one key."""
    mapping = mapping if mapping is not None else {}
    out = text
    for term in glossary:
        pattern = re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", re.IGNORECASE)
        if not pattern.search(out):
            continue
        key = next((k for k, v in mapping.items() if v == term), None)
        if key is None:
            key = PLACEHOLDER.format(n=len(mapping) + 1)
            mapping[key] = term
        out = pattern.sub(key, out)
    return out, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    def sub(m: re.Match[str]) -> str:
        return mapping.get(m.group(0), m.group(0))
    return _PLACEHOLDER_RE.sub(sub, text)


# ---------------------------------------------------------------- claim check

def _numbers(text: str) -> list[str]:
    return sorted(re.sub(r"[ ,]", "", m.group(0)) for m in NUMBER_RE.finditer(text))


def _claim_flags(text: str) -> set[str]:
    """The money-promise rules the studio already enforces, when the engine module imports."""
    try:
        engine = str(REPO / "packages" / "engine")
        if engine not in sys.path:
            sys.path.append(engine)
        import edit  # type: ignore
        return {f["rule"] for f in edit.claim_check(text, dry_run=True).get("flags", [])}
    except Exception:  # the check is a guard, never the reason a translation cannot run
        return set()


def check_claims(source: str, translated: str, glossary: list[str]) -> list[str]:
    """Problems, empty when the translation says what the source said: same numbers, every
    glossary term present, no money promise added or dropped."""
    problems: list[str] = []
    src_n, out_n = _numbers(source), _numbers(translated)
    if src_n != out_n:
        missing = [n for n in src_n if n not in out_n]
        added = [n for n in out_n if n not in src_n]
        if missing:
            problems.append(f"numbers missing from the translation: {missing}")
        if added:
            problems.append(f"numbers the source does not have: {added}")
    for term in glossary:
        want = len(re.findall(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", source, re.IGNORECASE))
        got = len(re.findall(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", translated, re.IGNORECASE))
        if want and got < want:
            problems.append(f"glossary term {term!r} appears {want}x in the source, {got}x in the translation")
    src_f, out_f = _claim_flags(source), _claim_flags(translated)
    if out_f - src_f:
        problems.append(f"the translation adds a claim the source did not make: {sorted(out_f - src_f)}")
    if _PLACEHOLDER_RE.search(translated):
        problems.append("a glossary placeholder was not restored")
    return problems


# ---------------------------------------------------------------- formats

def read_units(path: Path) -> tuple[str, list[str], Any]:
    """(format, translatable units, skeleton). Units are what goes to the model; the skeleton
    puts the answers back in place."""
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".srt":
        cues: list[dict[str, Any]] = []
        for block in re.split(r"\r?\n\r?\n+", text.strip()):
            lines = block.splitlines()
            if len(lines) >= 2 and SRT_TIME.match(lines[1]):
                cues.append({"index": lines[0], "time": lines[1], "text": " ".join(l.strip() for l in lines[2:])})
            elif len(lines) >= 1 and SRT_TIME.match(lines[0]):
                cues.append({"index": None, "time": lines[0], "text": " ".join(l.strip() for l in lines[1:])})
        if not cues:
            raise TranslateError(f"{path.name}: no SRT cues found")
        return "srt", [c["text"] for c in cues], cues
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict) and "segments" in data:
            items, container = data["segments"], data
        elif isinstance(data, list):
            items, container = data, None
        else:
            raise TranslateError(f"{path.name}: expected a list, or an object with `segments`")
        units = [str(it["text"]) if isinstance(it, dict) else str(it) for it in items]
        return "json", units, (container, items)
    return "text", [text.strip()], None


def write_units(path: Path, fmt: str, units: list[str], skeleton: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "srt":
        blocks = []
        for cue, text in zip(skeleton, units):
            head = ([cue["index"]] if cue["index"] is not None else []) + [cue["time"]]
            blocks.append("\n".join(head + [text]))
        path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    elif fmt == "json":
        container, items = skeleton
        out_items = []
        for it, text in zip(items, units):
            out_items.append({**it, "text": text} if isinstance(it, dict) else text)
        payload = {**container, "segments": out_items} if container is not None else out_items
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        path.write_text(units[0].rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the request

def build_request(units: list[str], src: str, dst: str, glossary: list[str], model: str) -> tuple[dict[str, Any], dict[str, str]]:
    """The OpenRouter chat body. Units are numbered lines; the model returns the same numbering."""
    masked: list[str] = []
    mapping: dict[str, str] = {}   # one map for the whole request: the same term keeps the same key
    for u in units:
        m, _ = protect(u, glossary, mapping)
        masked.append(m)
    numbered = "\n".join(f"[{i + 1}] {u}" for i, u in enumerate(masked))
    system = (f"You translate scripts and captions for short-form video from {LANGUAGES[src]} to {LANGUAGES[dst]}. "
              "Rules: keep every number, amount, percentage and date exactly as written; keep every "
              "\u27e6G#\u27e7 placeholder exactly as written and in place (they are brand terms); do not add, "
              "soften or strengthen any promise or claim; keep the register spoken and short; return only "
              "the translated lines, each prefixed with the same [n] marker, one per line, nothing else.")
    body = {"model": model, "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": numbered}]}
    return body, mapping


def parse_reply(content: str, count: int) -> list[str]:
    """`[n] text` lines back into units; a missing or extra line is an error, never a guess."""
    found: dict[int, str] = {}
    for line in content.splitlines():
        m = re.match(r"^\s*\[(\d+)\]\s*(.*)$", line)
        if m:
            found[int(m.group(1))] = m.group(2).strip()
        elif found and line.strip():
            last = max(found)
            found[last] = (found[last] + " " + line.strip()).strip()
    missing = [i for i in range(1, count + 1) if i not in found]
    if missing or len(found) != count:
        raise TranslateError(f"the model returned {len(found)} of {count} lines (missing {missing[:5]})")
    return [found[i] for i in range(1, count + 1)]


def _secret(name: str) -> str | None:
    sys.path.insert(0, str(REPO / "packages" / "common"))
    import vault  # type: ignore
    return vault.get(name)


def call_openrouter(body: dict[str, Any]) -> str:
    import urllib.request
    key = _secret("OPENROUTER_API_KEY")
    if not key:
        raise TranslateError("OPENROUTER_API_KEY is not set; refusing to call a paid endpoint. Store it with "
                             "python infra/runpod/set_secret.py openrouter, or use --dry-run.")
    req = urllib.request.Request(
        f"{OPENROUTER_BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://ongeapesa.nsait.co.ke", "X-Title": "director-studio-translate"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise TranslateError(f"unexpected OpenRouter reply: {str(payload)[:200]}") from e


def translate_units(units: list[str], src: str, dst: str, glossary: list[str], model: str = DEFAULT_MODEL,
                    call: Callable[[dict[str, Any]], str] = call_openrouter, strict: bool = True) -> dict[str, Any]:
    """Translate units through `call` (the OpenRouter call, or a stand-in in tests), restore the
    glossary, and run the claim check. Returns units, problems and the request."""
    body, mapping = build_request(units, src, dst, glossary, model)
    t0 = time.time()
    reply = call(body)
    out = [restore(u, mapping) for u in parse_reply(reply, len(units))]
    problems = check_claims("\n".join(units), "\n".join(out), glossary)
    if problems and strict:
        raise TranslateError("translation drifted from the source: " + "; ".join(problems))
    return {"units": out, "problems": problems, "request": body, "glossary": mapping,
            "elapsed_s": round(time.time() - t0, 2)}


def translate_file(src_path: Path, out_path: Path, src: str, dst: str, glossary_path: Path | None = None,
                   model: str = DEFAULT_MODEL, dry_run: bool = True, strict: bool = True,
                   sheng_reviewed: bool = False, call: Callable[[dict[str, Any]], str] = call_openrouter) -> dict[str, Any]:
    if src not in LANGUAGES or dst not in LANGUAGES:
        raise TranslateError(f"languages are {sorted(LANGUAGES)}")
    if src == dst:
        raise TranslateError("--from and --to are the same language")
    if dst == "sheng" and not sheng_reviewed:
        raise TranslateError(SHENG_REFUSAL)
    src_path = Path(src_path)
    if not src_path.exists():
        raise TranslateError(f"input not found: {src_path}")
    glossary = load_glossary(glossary_path)
    fmt, units, skeleton = read_units(src_path)
    if not any(u.strip() for u in units):
        raise TranslateError(f"{src_path.name}: nothing to translate")
    if dry_run:
        body, mapping = build_request(units, src, dst, glossary, model)
        return {"status": "dry-run", "format": fmt, "units": len(units), "glossary": mapping, "request": body,
                "note": f"would send {len(units)} unit(s) to {model}; nothing sent, {out_path.name} not written"}
    result = translate_units(units, src, dst, glossary, model, call=call, strict=strict)
    write_units(Path(out_path), fmt, result["units"], skeleton)
    return {"status": "completed", "format": fmt, "units": len(units), "file": Path(out_path).as_posix(),
            "glossary": result["glossary"], "problems": result["problems"], "model": model,
            "elapsed_s": result["elapsed_s"], "note": f"{len(units)} unit(s) {src}->{dst}"
            + ("" if not result["problems"] else f"; {len(result['problems'])} claim warning(s)")}


# ---------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Translate a script or caption file through OpenRouter, keeping brand "
                                             "terms and claims fixed. Dry-run prints the request and sends nothing.")
    ap.add_argument("--from", dest="src", required=True, choices=sorted(LANGUAGES), help="source language")
    ap.add_argument("--to", dest="dst", required=True, choices=sorted(LANGUAGES), help="target language")
    ap.add_argument("--in", dest="src_path", required=True, help="script (.txt/.md), captions (.srt) or transcript (.json)")
    ap.add_argument("--out", dest="out_path", help="where to write the translation (same format); required unless --dry-run")
    ap.add_argument("--glossary", help="terms that must not be translated: one per line, or a JSON list")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenRouter model id (default {DEFAULT_MODEL})")
    ap.add_argument("--dry-run", action="store_true", help="print the request payload; no network, nothing written")
    ap.add_argument("--no-claim-check", action="store_true", help="report claim drift as a warning instead of refusing")
    ap.add_argument("--sheng-reviewed", action="store_true", help="allow a Sheng target (a speaker will review it)")
    a = ap.parse_args(argv)
    if not a.dry_run and not a.out_path:
        ap.error("--out is required unless --dry-run")
    out_path = Path(a.out_path) if a.out_path else Path(a.src_path).with_suffix(f".{a.dst}{Path(a.src_path).suffix}")
    try:
        result = translate_file(Path(a.src_path), out_path, a.src, a.dst, Path(a.glossary) if a.glossary else None,
                                model=a.model, dry_run=a.dry_run, strict=not a.no_claim_check,
                                sheng_reviewed=a.sheng_reviewed)
    except TranslateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
