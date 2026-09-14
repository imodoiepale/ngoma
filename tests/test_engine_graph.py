"""The graph core the director engine needs: many nodes of one kind, picks, lanes, no loops."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import workflow_author as wa  # noqa: E402

CAT = wa.load_catalog()


def _node(nid: str, kind: str, **data):
    return {"id": nid, "kind": kind, "position": {"x": 0, "y": 0}, "data": {"params": {}, **data}}


def _edge(eid: str, s: str, sh: str, t: str, th: str, typ: str):
    return {"id": eid, "source": s, "sourceHandle": sh, "target": t, "targetHandle": th, "type": typ}


def test_a_brief_still_gets_one_node_per_kind():
    wf = wa.from_brief("Sheng WhatsApp status ad for a mama mboga", "ongea-pesa")
    kinds = [n["kind"] for n in wf["nodes"]]
    assert len(kinds) == len(set(kinds))


def test_two_generators_of_one_kind_survive_when_they_serve_different_scenes():
    wf = {"version": 2, "nodes": [
        _node("s1.brief", "brief"), _node("s2.a", "klein-t2i", scene=1, shot=1), _node("s3.b", "klein-t2i", scene=2, shot=1)],
        "edges": [_edge("e1", "s1.brief", "text", "s2.a", "prompt", "text"), _edge("e2", "s1.brief", "text", "s3.b", "prompt", "text")],
        "gaps": []}
    assert wa.validate(wf) == []
    assert wa._node_key(wf["nodes"][1]) != wa._node_key(wf["nodes"][2])


def test_pick_cannot_keep_more_than_it_is_offered():
    wf = {"version": 2, "nodes": [
        _node("g", "klein-t2i", variant_count=4), _node("p", "pick", params={"k": 5}), _node("b", "brief")],
        "edges": [_edge("e0", "b", "text", "g", "prompt", "text"), _edge("e1", "g", "image", "p", "candidates", "image")], "gaps": []}
    assert any("only 4 candidate" in p for p in wa.validate(wf))
    wf["nodes"][1]["data"]["params"]["k"] = 4
    assert wa.validate(wf) == []


def test_human_backend_belongs_to_decide_steps_only():
    spec = CAT["by_kind"]["pick"]
    assert spec["backend"]["kind"] == "human" and spec["category"] == "decide"
    for n in CAT["nodes"]:
        assert (n["backend"]["kind"] == "human") == (n["category"] == "decide"), n["kind"]


def test_loops_are_refused():
    wf = {"version": 2, "nodes": [_node("a", "image-edit"), _node("b", "image-edit", scene=2), _node("t", "brief")],
          "edges": [_edge("e1", "a", "image", "b", "image", "image"), _edge("e2", "b", "image", "a", "image", "image"),
                    _edge("e3", "t", "text", "a", "prompt", "text"), _edge("e4", "t", "text", "b", "prompt", "text")], "gaps": []}
    assert any("feed back" in p for p in wa.validate(wf))


@pytest.mark.parametrize("mode", wa.RUN_MODES)
def test_run_modes_are_accepted(mode):
    wf = wa.from_idea("V08", "epalle")
    wf["run_mode"] = mode
    assert wa.validate(wf) == []
    wf["run_mode"] = "yolo"
    assert any("run_mode" in p for p in wa.validate(wf))


def test_layout_lanes_puts_each_stage_in_its_own_band():
    stages = [{"id": "s1", "label": "Refs", "order": 1}, {"id": "s2", "label": "Scene 1", "order": 2}]
    nodes = [_node("a", "reference-images", stage="s1"), _node("b", "image-edit", stage="s2"), _node("c", "brief", stage="s2")]
    edges = [_edge("e1", "a", "images", "b", "image", "image"), _edge("e2", "c", "text", "b", "prompt", "text")]
    wa.layout_lanes(nodes, edges, stages)
    ys = {n["id"]: n["position"]["y"] for n in nodes}
    assert ys["b"] >= ys["a"] + 260 and ys["c"] == ys["b"], "stage 2 sits in a band below stage 1"
    assert nodes[1]["position"]["x"] > nodes[2]["position"]["x"], "inside a lane, depth runs left to right"
