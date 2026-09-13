"""Step outlines and channel filtering: evidence pointers, never transcript copies."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "ingest"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))

import steps  # noqa: E402
import yt_learn  # noqa: E402


def _rec():
    return {"video_id": "abcdefghijk", "title": "Build a RefMod", "channel": "dainamo",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "facts": {"node_pack": [{"value": "kj nodes", "t": "00:01:10", "video": "abcdefghijk", "quote": ""}],
                      "model": [{"value": "minimax-h3", "t": "00:03:30", "video": "abcdefghijk", "quote": ""}]}}


def test_steps_point_to_moments_without_reproducing_sentences():
    cues = [("00:01:05", "now we install the KJ nodes pack from the manager and restart everything"),
            ("00:03:25", "then load the MiniMax H3 reference model and run the graph once"),
            ("00:05:00", "thanks for watching and see you next time")]
    out = steps.outline(_rec(), cues)
    assert [s["action"] for s in out] == ["install", "load"]
    md = steps.render(_rec(), out)
    for _, sentence in cues:
        assert sentence not in md, "the outline must not copy transcript sentences"
    assert "&t=65" in md and "&t=205" in md


def test_a_cue_without_a_named_tool_is_not_a_step():
    cues = [("00:09:00", "click the button and run it")]
    assert steps.outline(_rec(), cues) == []


def test_title_filter_keeps_only_matching_videos(monkeypatch, tmp_path):
    monkeypatch.setattr(yt_learn, "REPO", tmp_path)
    monkeypatch.setattr(yt_learn, "CORPUS", tmp_path)
    monkeypatch.setattr(yt_learn, "load_channels", lambda: {
        "subtitle_langs": ["en"], "default_max_videos": 5,
        "channels": [{"key": "aq", "tier": "proposed", "url": "u", "title_filter": "comfyui|minimax"}]})
    monkeypatch.setattr(yt_learn, "list_videos", lambda url, limit: [
        {"id": "a" * 11, "title": "MiniMax H3 Tutorial"},
        {"id": "b" * 11, "title": "Best AI logo tool review"},
        {"id": "c" * 11, "title": "ComfyUI upscale build"}])
    fetched = []

    def fake_subs(vid, dest, langs):
        fetched.append(vid)
        return []
    monkeypatch.setattr(yt_learn, "fetch_subs", fake_subs)
    rep = yt_learn.learn(["aq"])
    assert fetched == ["a" * 11, "c" * 11]
    assert any("title_filter kept 2/3" in n for n in rep.notes)
