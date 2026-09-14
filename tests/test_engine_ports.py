"""Port maps: every engine workflow has one, it matches the workflow bytes, and bind() lands values."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import ports  # noqa: E402
import workflow_author as wa  # noqa: E402

CAT = wa.load_catalog()
MANIFEST = {w["canonical"]: w for w in json.loads((REPO / "workflows" / "manifest.json").read_text(encoding="utf-8"))["workflows"]}
KIND_TO_REL = {k: CAT["by_kind"][k]["backend"]["workflow"] for k in ports.ENGINE_KINDS}
WARDROBE = KIND_TO_REL["wardrobe"]


def _graph(rel: str) -> dict:
    return json.loads((REPO / "workflows" / rel).read_text(encoding="utf-8"))


def test_every_engine_kind_validates():
    assert ports.validate_port_maps(CAT) == []


def test_engine_kinds_are_comfy_backed():
    for kind in ports.ENGINE_KINDS:
        assert CAT["by_kind"][kind]["backend"]["kind"] == "comfy"


@pytest.mark.parametrize("kind", ports.ENGINE_KINDS)
def test_map_matches_workflow(kind):
    rel = KIND_TO_REL[kind]
    pm = ports.load_port_map(rel)
    assert pm["workflow"] == rel
    assert pm["sha256"] == MANIFEST["workflows/" + rel]["sha256"]
    ids = ports.workflow_node_ids(_graph(rel))
    for name, ref in ports._refs(pm):
        assert ref["node"] in ids, f"{kind}: {name} -> node {ref['node']} missing"
    assert pm["outputs"], f"{kind}: no outputs"
    # ascii + LF on disk
    raw = ports.port_map_path(rel).read_bytes()
    assert b"\r\n" not in raw
    raw.decode("ascii")


def test_port_map_path():
    p = ports.port_map_path("icekiub/H3_Icy_image.json")
    assert p.name == "H3_Icy_image.ports.json" and p.parent.name == "icekiub"
    assert ports.port_map_path("workflows/icekiub/H3_Icy_image.json") == p
    with pytest.raises(ports.PortMapError):
        ports.port_map_path("icekiub/H3_Icy_image.txt")


def test_missing_map_raises():
    with pytest.raises(ports.PortMapError):
        ports.load_port_map("does-not-exist/nothing.json")


def test_bind_wardrobe_sets_images_seed_and_reports_unknown():
    graph = _graph(WARDROBE)
    pm = ports.load_port_map(WARDROBE)
    before = json.dumps(graph, sort_keys=True)
    bound, log = ports.bind(graph, pm, {
        "image": "model.png", "clothes": "jacket.png", "seed": 42, "prompt": "put the jacket on the model",
        "banana": "x",
    })
    assert json.dumps(graph, sort_keys=True) == before, "bind must not mutate its input"
    by_id = {str(n["id"]): n for n in bound["nodes"]}
    assert by_id[pm["inputs"]["image"]["node"]]["widgets_values"][0] == "model.png"
    assert by_id[pm["inputs"]["clothes"]["node"]]["widgets_values"][0] == "jacket.png"
    assert by_id[pm["seed"]["node"]]["widgets_values"][pm["seed"]["widget_index"]] == 42
    assert by_id[pm["prompt"]["node"]]["widgets_values"][0] == "put the jacket on the model"
    assert any(line.startswith("skipped banana") for line in log)
    assert sum(line.startswith("set ") for line in log) == 4


def test_bind_api_format():
    rel = KIND_TO_REL["klein-t2i"]
    bound, log = ports.bind(_graph(rel), ports.load_port_map(rel), {"prompt": "hello", "seed": 7, "count": 2})
    assert bound["4"]["inputs"]["text"] == "hello"
    assert bound["8"]["inputs"]["seed"] == 7
    assert bound["7"]["inputs"]["batch_size"] == 2
    assert len(log) == 3


def test_bind_unknown_port_is_reported_as_unknown():
    rel = KIND_TO_REL["lipsync"]
    _, log = ports.bind(_graph(rel), ports.load_port_map(rel), {"audio": "voice.wav"})
    assert log == ["skipped audio: listed as unknown in the port map"]


def test_wrong_sha_is_reported(tmp_path, monkeypatch):
    # copy the workflow tree entry for wardrobe into a temp WORKFLOWS root with a tampered sha
    root = tmp_path / "workflows"
    src = REPO / "workflows" / WARDROBE
    (root / Path(WARDROBE).parent).mkdir(parents=True)
    (root / WARDROBE).write_bytes(src.read_bytes())
    pm = ports.load_port_map(WARDROBE)
    pm["sha256"] = "0" * 64
    (root / (WARDROBE[:-5] + ".ports.json")).write_text(json.dumps(pm), encoding="utf-8")
    (root / "manifest.json").write_bytes((REPO / "workflows" / "manifest.json").read_bytes())
    monkeypatch.setattr(ports, "WORKFLOWS", root)
    monkeypatch.setattr(ports, "MANIFEST", root / "manifest.json")
    mini = {"nodes": [CAT["by_kind"]["wardrobe"]]}
    monkeypatch.setattr(ports, "ENGINE_KINDS", ["wardrobe"])
    problems = ports.validate_port_maps(mini)
    assert any("sha256" in p and "does not match" in p for p in problems), problems


def test_missing_node_is_reported(monkeypatch):
    pm = ports.load_port_map(WARDROBE)
    pm["inputs"]["image"]["node"] = "999999"
    monkeypatch.setattr(ports, "load_port_map", lambda rel: pm)
    monkeypatch.setattr(ports, "ENGINE_KINDS", ["wardrobe"])
    problems = ports.validate_port_maps(CAT)
    assert any("999999" in p and "does not exist" in p for p in problems), problems
