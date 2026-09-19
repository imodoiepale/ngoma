"""packages/voice/translate.py: glossary terms survive, numbers and claims are checked, nothing is sent in dry-run."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "voice"))
import translate as tr  # noqa: E402

SCRIPT = "Send KES 1,500 with Ongea Pesa in 3 taps. M-Pesa fees stay at 2.5%. Call 0712 345 678."
GLOSSARY = ["Ongea Pesa", "M-Pesa"]


def echo_with(replacements: dict[str, str]):
    """A stand-in for the OpenRouter call: the numbered lines back with some words swapped."""
    def call(body):
        user = body["messages"][1]["content"]
        for a, b in replacements.items():
            user = user.replace(a, b)
        return user
    return call


@pytest.fixture
def files(tmp_path):
    g = tmp_path / "glossary.txt"
    g.write_text("# brand terms\nOngea Pesa\nM-Pesa\n", encoding="utf-8")
    s = tmp_path / "script.txt"
    s.write_text(SCRIPT + "\n", encoding="utf-8")
    srt = tmp_path / "caps.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nSend KES 1,500\nwith Ongea Pesa\n\n"
                   "2\n00:00:02,000 --> 00:00:04,000\nIn 3 taps\n", encoding="utf-8")
    return {"glossary": g, "script": s, "srt": srt, "dir": tmp_path}


def test_glossary_terms_are_masked_then_restored():
    masked, mapping = tr.protect(SCRIPT, GLOSSARY)
    assert "Ongea Pesa" not in masked and "M-Pesa" not in masked
    assert set(mapping.values()) == set(GLOSSARY)
    assert tr.restore(masked, mapping) == SCRIPT


def test_one_placeholder_per_term_across_units():
    body, mapping = tr.build_request(["Ongea Pesa is fast", "Use Ongea Pesa daily", "M-Pesa too"], "en", "sw", GLOSSARY, "m")
    assert len(mapping) == 2
    user = body["messages"][1]["content"]
    assert user.count(next(k for k, v in mapping.items() if v == "Ongea Pesa")) == 2
    assert user.startswith("[1] ") and "[3] " in user


def test_dry_run_prints_the_request_and_sends_nothing(files, monkeypatch):
    monkeypatch.setattr(tr, "call_openrouter", lambda body: pytest.fail("dry-run must not call the network"))
    out = files["dir"] / "script.sw.txt"
    r = tr.translate_file(files["script"], out, "en", "sw", files["glossary"], dry_run=True)
    assert r["status"] == "dry-run" and not out.exists()
    assert r["request"]["model"] == tr.DEFAULT_MODEL
    user = r["request"]["messages"][1]["content"]
    assert "Ongea Pesa" not in user and "1,500" in user and "\u27e6G1\u27e7" in user


def test_translation_keeps_glossary_numbers_and_srt_timing(files):
    out = files["dir"] / "caps.sw.srt"
    r = tr.translate_file(files["srt"], out, "en", "sw", files["glossary"], dry_run=False,
                          call=echo_with({"Send": "Tuma", "with": "na", "In": "Kwa"}))
    assert r["status"] == "completed" and r["problems"] == []
    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in text and "00:00:02,000 --> 00:00:04,000" in text
    assert "Tuma KES 1,500 na Ongea Pesa" in text and "Kwa 3 taps" in text


def test_json_transcript_is_translated_field_by_field(files):
    src = files["dir"] / "t.json"
    src.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": "Send 200 now"}, {"start": 1, "end": 2, "text": "M-Pesa"}]}),
                   encoding="utf-8")
    out = files["dir"] / "t.sw.json"
    r = tr.translate_file(src, out, "en", "sw", files["glossary"], dry_run=False, call=echo_with({"Send": "Tuma"}))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert r["status"] == "completed"
    assert data["segments"][0] == {"start": 0, "end": 1, "text": "Tuma 200 now"} and data["segments"][1]["text"] == "M-Pesa"


def test_a_changed_number_is_refused(files):
    with pytest.raises(tr.TranslateError, match="1500"):
        tr.translate_file(files["script"], files["dir"] / "o.txt", "en", "sw", files["glossary"], dry_run=False,
                          call=echo_with({"1,500": "1,600"}))
    assert not (files["dir"] / "o.txt").exists()


def test_a_dropped_or_rewritten_brand_term_is_refused(files):
    with pytest.raises(tr.TranslateError, match="Ongea Pesa"):
        tr.translate_file(files["script"], files["dir"] / "o.txt", "en", "sw", files["glossary"], dry_run=False,
                          call=echo_with({"\u27e6G1\u27e7": "Ongea"}))


def test_an_added_money_promise_is_refused(files):
    with pytest.raises(tr.TranslateError, match="adds a claim"):
        tr.translate_file(files["script"], files["dir"] / "o.txt", "en", "sw", files["glossary"], dry_run=False,
                          call=echo_with({"taps.": "taps. Guaranteed returns!"}))


def test_strict_off_downgrades_drift_to_a_warning(files):
    r = tr.translate_file(files["script"], files["dir"] / "o.txt", "en", "sw", files["glossary"], dry_run=False,
                          strict=False, call=echo_with({"1,500": "1,600"}))
    assert r["status"] == "completed" and r["problems"]


def test_missing_lines_from_the_model_are_an_error():
    with pytest.raises(tr.TranslateError, match="returned 1 of 2"):
        tr.parse_reply("[1] only one", 2)
    assert tr.parse_reply("[1] a\ncontinued\n[2] b", 2) == ["a continued", "b"]


def test_sheng_target_needs_review_and_same_language_is_refused(files):
    with pytest.raises(tr.TranslateError, match="Sheng"):
        tr.translate_file(files["script"], files["dir"] / "o.txt", "en", "sheng", None, dry_run=True)
    r = tr.translate_file(files["script"], files["dir"] / "o.txt", "en", "sheng", None, dry_run=True, sheng_reviewed=True)
    assert r["status"] == "dry-run"
    with pytest.raises(tr.TranslateError, match="same language"):
        tr.translate_file(files["script"], files["dir"] / "o.txt", "sw", "sw", None, dry_run=True)


def test_live_call_without_a_key_refuses(monkeypatch):
    monkeypatch.setattr(tr, "_secret", lambda name: None)
    with pytest.raises(tr.TranslateError, match="OPENROUTER_API_KEY"):
        tr.call_openrouter({"model": "x", "messages": []})


def test_cli_dry_run_and_help(files, capsys):
    rc = tr.main(["--from", "en", "--to", "sw", "--in", str(files["script"]), "--glossary", str(files["glossary"]), "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "dry-run" and out["glossary"]
    r = subprocess.run([sys.executable, str(REPO / "packages" / "voice" / "translate.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    for flag in ("--from", "--to", "--in", "--out", "--dry-run", "--glossary"):
        assert flag in r.stdout, flag
