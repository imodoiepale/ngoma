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
