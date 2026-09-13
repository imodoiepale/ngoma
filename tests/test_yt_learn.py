"""The YouTube learner: single-video intake and a corpus that runs cannot shrink."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "ingest"))
import yt_learn  # noqa: E402


def _rec(vid: str, channel: str, value: str) -> dict:
    return {"video_id": vid, "channel": channel, "title": vid, "cue_count": 1, "fact_count": 1,
            "facts": {"node_pack": [{"value": value, "t": "00:00:01", "video": vid, "quote": ""}]}}


def test_a_one_channel_run_does_not_delete_other_channels(tmp_path):
    yt_learn.merge_facts([_rec("aaaaaaaaaaa", "kiubai", "kjnodes"),
                          _rec("bbbbbbbbbbb", "dgikaos", "rgthree")], tmp_path)
    # a later run that only touched one channel
    idx, rollup = yt_learn.merge_facts([_rec("ccccccccccc", "axiomgraph", "kjnodes")], tmp_path)
    ids = [json.loads(line)["video_id"] for line in idx.read_text(encoding="utf-8").splitlines()]
    assert sorted(ids) == ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"]
    assert rollup["node_pack"] == {"kjnodes": 2, "rgthree": 1}


def test_re_mining_a_video_replaces_it_rather_than_duplicating(tmp_path):
    yt_learn.merge_facts([_rec("aaaaaaaaaaa", "kiubai", "kjnodes")], tmp_path)
    idx, _ = yt_learn.merge_facts([_rec("aaaaaaaaaaa", "kiubai", "sageattention")], tmp_path)
    lines = idx.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and "sageattention" in lines[0]


@pytest.mark.parametrize("given", [
    "https://www.youtube.com/watch?v=9APXcBMpbgU&t=25s",
    "https://youtu.be/9APXcBMpbgU?t=25",
    "9APXcBMpbgU",
])
def test_video_id_of_accepts_the_links_people_actually_paste(given):
    assert yt_learn.video_id_of(given) == "9APXcBMpbgU"


def test_video_id_of_refuses_non_video_links():
    with pytest.raises(yt_learn.YTError):
        yt_learn.video_id_of("https://www.youtube.com/@AxiomGraph")


def test_install_guides_yield_versions_and_packs():
    cues = [("00:02:50", "my portable version uses torch 2.9.0 with CUDA 13.0"),
            ("00:01:30", "look for Python 3.13.6 and download it"),
            ("00:05:50", "install KJ nodes and add the patch sage attention node, Triton too")]
    facts = yt_learn.mine(cues, "9APXcBMpbgU", "Install Sage Attention 2.2")["facts"]
    versions = {f["value"] for f in facts["version"]}
    assert {"torch 2.9.0", "cuda 13.0", "python 3.13.6"} <= versions
    assert {"kj nodes", "sage attention", "triton"} <= {f["value"] for f in facts["node_pack"]}


def test_spoken_pack_names_join_the_workflow_pack_node():
    """'KJ nodes' said aloud must land on the same node workflows require, or the
    graph shows two packs and half the evidence."""
    sys.path.insert(0, str(REPO / "packages" / "library"))
    from graph_build import _norm_pack
    assert _norm_pack("kj-nodes") == _norm_pack("kjnodes") == "comfyui-kjnodes"


def test_evidence_lookup_ignores_spaces_and_hyphens():
    sys.path.insert(0, str(REPO / "packages" / "library"))
    from graph_query import _find
    nodes = {"node_pack:sage-attention": {"kind": "node_pack", "label": "sage-attention"}}
    assert _find(nodes, "sage attention") == ["node_pack:sage-attention"]
    assert _find(nodes, "SageAttention") == ["node_pack:sage-attention"]


def test_a_video_is_never_filed_without_its_title(monkeypatch, tmp_path):
    """yt-dlp wrote subtitles but no info.json for 2K6-OtV_Vbc, and the video landed in
    `unsorted/` with title null. Metadata must be fetched another way, not left empty."""
    import subprocess
    vid = "2K6-OtV_Vbc"
    monkeypatch.setattr(yt_learn, "REPO", tmp_path)
    monkeypatch.setattr(yt_learn, "CORPUS", tmp_path / "youtube")
    monkeypatch.setattr(yt_learn, "load_channels", lambda: {"channels": [], "subtitle_langs": ["en"]})

    def fake_subs(video_id, dest, langs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{video_id}.en.vtt").write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nsearch for create H3 ref from folder\n",
            encoding="utf-8")
        return [dest / f"{video_id}.en.vtt"]          # note: no info.json written

    meta = {"id": vid, "title": "How to Create a RefMod for MiniMax H3",
            "channel": "Dainamo", "channel_id": "UCb_A1zvd9iXCigO8ekgJW2A", "uploader_id": "@DainamoLabs"}
    monkeypatch.setattr(yt_learn, "fetch_subs", fake_subs)
    monkeypatch.setattr(yt_learn, "_ytdlp", lambda args, timeout=900: subprocess.CompletedProcess(
        args, 0, stdout=json.dumps(meta), stderr=""))

    rep = yt_learn.learn_video(f"https://www.youtube.com/watch?v={vid}")
    assert rep.status == "ok", rep.notes
    rec = json.loads((tmp_path / "youtube" / "facts.jsonl").read_text(encoding="utf-8"))
    assert rec["title"] == meta["title"] and rec["channel"] == "dainamolabs"
    assert (tmp_path / "youtube" / "dainamolabs" / "subs" / f"{vid}.info.json").exists()


def test_manifest_has_one_entry_per_workflow():
    """Duplicate entries (same path twice, or the same bytes under two paths) split one
    workflow into several graph nodes and double its apparent dependency counts."""
    man = json.loads((REPO / "workflows" / "manifest.json").read_text(encoding="utf-8"))
    paths = [w["canonical"] for w in man["workflows"]]
    shas = [w["sha256"] for w in man["workflows"]]
    assert len(paths) == len(set(paths)), "duplicate canonical paths"
    assert len(shas) == len(set(shas)), "identical workflow stored under two paths"


def test_every_manifest_workflow_exists_and_matches_its_hash():
    import hashlib
    man = json.loads((REPO / "workflows" / "manifest.json").read_text(encoding="utf-8"))
    assert man["count"] == len(man["workflows"])
    for w in man["workflows"]:
        p = REPO / w["canonical"]
        assert p.exists(), w["canonical"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == w["sha256"], w["canonical"]


def test_refmod_workflows_name_the_node_repos_they_need():
    man = json.loads((REPO / "workflows" / "manifest.json").read_text(encoding="utf-8"))
    by = {Path(w["canonical"]).name: w for w in man["workflows"]}
    gen = by["dainamo-refmod-generate.json"]
    assert {"Luisacaotica/ComfyUI-MiniMaxH3Mod", "xmarre/ComfyUI-Spectrum-MiniMax-H3",
            "comfyui-kjnodes"} <= set(gen["node_packs"])
    assert "minimax_h3_ref2va_pruned_fp8_scaled.safetensors" in gen["models"]
    create = by["franckyb-refmod-create-from-folder.json"]
    assert "FranckyB/ComfyUI-H3RefModPicker" in create["node_packs"]
