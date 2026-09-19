"""The fan-out contract: `<step>@each` marks a node to run once per upstream item.

Shared by the author (this file's subject), the runner loop, the canvas badge and the
describe-to-workflow parser. See docs/superpowers/specs/2026-09-20-general-creative-studio-design.md.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import workflow_author as wa  # noqa: E402

CAT = wa.load_catalog()


def test_split_each_strips_the_suffix_only_when_present():
    assert wa.split_each("carousel@each") == ("carousel", True)
    assert wa.split_each("carousel") == ("carousel", False)
    assert wa.split_each("wardrobe@each") == ("wardrobe", True)


def test_a_step_with_each_authors_a_fan_out_node_that_validates():
    wf = wa.author(["reference-images", "wardrobe@each", "carousel@each", "compositor"], "batch", "epalle", {"test": True})
    by_kind = {n["kind"]: n for n in wf["nodes"]}
    assert wa.is_each(by_kind["wardrobe"]) and wa.is_each(by_kind["carousel"])
    assert not wa.is_each(by_kind["compositor"]) and not wa.is_each(by_kind["reference-images"])
    assert wa.iterated_port(by_kind["wardrobe"], CAT) == "image"
    assert wa.iterated_port(by_kind["carousel"], CAT) == "image"
    assert wa.validate(wf) == []


def test_the_plain_step_stays_a_single_run():
    wf = wa.author(["carousel"], "one", "epalle", {"test": True})
    assert not any(wa.is_each(n) for n in wf["nodes"])
    assert "each" not in next(n for n in wf["nodes"] if n["kind"] == "carousel")["data"]


def test_each_port_overrides_the_default_and_must_exist():
    wf = wa.author(["wardrobe@each"], "w", "epalle", {"test": True})
    node = next(n for n in wf["nodes"] if n["kind"] == "wardrobe")
    node["data"]["each_port"] = "clothes"
    assert wa.iterated_port(node, CAT) == "clothes"
    assert wa.validate(wf) == []
    node["data"]["each_port"] = "no-such-port"
    assert any("each_port" in p for p in wa.validate(wf))


def test_each_is_refused_where_nothing_can_loop():
    for step in ("reference-images", "brand-kit", "pick", "postiz"):
        wf = wa.author([step], "x", "epalle", {"test": True})
        node = next(n for n in wf["nodes"] if n["kind"] == CAT["by_step"][step]["kind"])
        node["data"]["each"] = True
        assert any("cannot fan out" in p or "no image or video input" in p for p in wa.validate(wf)), step


def test_each_must_be_a_boolean():
    wf = wa.author(["carousel"], "c", "epalle", {"test": True})
    next(n for n in wf["nodes"] if n["kind"] == "carousel")["data"]["each"] = "yes"
    assert any("each must be true or false" in p for p in wa.validate(wf))


def test_a_fan_out_node_needs_something_on_its_iterated_port():
    wf = wa.author(["carousel@each"], "c", "epalle", {"test": True})
    car = next(n for n in wf["nodes"] if n["kind"] == "carousel")
    wf["edges"] = [e for e in wf["edges"] if e["target"] != car["id"]]
    assert any("nothing feeds its image port" in p for p in wa.validate(wf))


def test_a_pick_after_a_fan_out_may_keep_more_than_one_per_item():
    wf = wa.author(["carousel@each"], "c", "epalle", {"test": True})
    car = next(n for n in wf["nodes"] if n["kind"] == "carousel")
    pick = {"id": "p", "kind": "pick", "position": {"x": 0, "y": 0}, "data": {"params": {"k": 10}}}
    wf["nodes"].append(pick)
    wf["edges"].append({"id": "ep", "source": car["id"], "sourceHandle": "images", "target": "p", "targetHandle": "candidates", "type": "image"})
    assert wa.validate(wf) == []
    plain = copy.deepcopy(wf)
    next(n for n in plain["nodes"] if n["kind"] == "carousel")["data"].pop("each")
    assert any("asks to keep 10" in p for p in wa.validate(plain))


def test_combining_keeps_the_each_flag():
    a = wa.author(["wardrobe@each"], "swap", "epalle", {"t": 1})
    b = wa.author(["carousel@each"], "carousels", "epalle", {"t": 2})
    wf = wa.combine([a, b], "swap then carousels", "epalle")
    assert sum(1 for n in wf["nodes"] if wa.is_each(n)) == 2
    assert wa.validate(wf) == []


@pytest.mark.parametrize("brief", ["carousel@each", "carousel", "wardrobe@each"])
def test_each_survives_a_save_and_reload_cycle(tmp_path, brief, monkeypatch):
    wf = wa.author([brief], "t", "epalle", {"t": 1})
    monkeypatch.setattr(wa, "BRANDS", tmp_path)
    (tmp_path / "epalle").mkdir()
    (tmp_path / "epalle" / "brand.yaml").write_text("brand: epalle\n", encoding="utf-8")
    p = wa.save(wf)
    import json
    back = json.loads(p.read_text(encoding="utf-8"))
    assert [wa.is_each(n) for n in back["nodes"]] == [wa.is_each(n) for n in wf["nodes"]]
