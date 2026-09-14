"""Idea workflow diagrams: one Archify IR per business idea, generated and never hand-edited.

No node, no network: the IR is rebuilt in Python and compared byte for byte, so a changed
template, catalogue entry or price shows up here until someone regenerates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))

import business_os  # noqa: E402
import idea_diagrams as d  # noqa: E402

DOC = business_os.load()
ROWS = {r.idea["id"]: r for r in business_os.costed_all(DOC)}
IDS = sorted(ROWS)
CATALOG = d.load_catalog()


def ir_path(idea_id: str) -> Path:
    return d.OUT / f"{idea_id.lower()}.workflow.json"


def load_ir(idea_id: str) -> dict:
    return json.loads(ir_path(idea_id).read_text(encoding="utf-8"))


def test_one_ir_per_idea_and_nothing_else():
    assert len(IDS) == 50
    expected = {ir_path(i).name for i in IDS}
    found = {p.name for p in d.OUT.glob("*.workflow.json")}
    assert found == expected


@pytest.mark.parametrize("idea_id", IDS)
def test_ir_regenerates_byte_identically(idea_id):
    row = ROWS[idea_id]
    ir = d.build(row.idea, row, d.load_template(idea_id), CATALOG)
    assert ir_path(idea_id).read_bytes() == d.dumps(ir).encode("utf-8"), \
        f"{idea_id} drifted; run: uv run --quiet --with pyyaml python packages/strategy/idea_diagrams.py --deliver"


@pytest.mark.parametrize("idea_id", IDS)
def test_ir_shape_and_references(idea_id):
    ir = load_ir(idea_id)
    assert ir["schema_version"] == 2
    assert ir["diagram_type"] == "workflow"
    assert ir["meta"]["title"].startswith(idea_id + " ")
    assert ir["meta"]["quality_profile"] in ("showcase", "standard")
    if ir["meta"]["quality_profile"] == "standard":
        assert idea_id in d.STANDARD_FALLBACK
    lanes = {lane["id"] for lane in ir["lanes"]}
    ids = [n["id"] for n in ir["nodes"]]
    assert len(ids) == len(set(ids)) <= 12
    seats = set()
    for n in ir["nodes"]:
        assert 0 <= n["col"] <= 5
        assert n["lane"] in lanes
        assert len(n["label"]) <= d.MAX_LABEL
        assert (n["lane"], n["col"]) not in seats, f"{n['id']} collides in {n['lane']}"
        seats.add((n["lane"], n["col"]))
    cols = {n["id"]: n["col"] for n in ir["nodes"]}
    for e in ir["edges"]:
        assert e["from"] in cols and e["to"] in cols
        assert cols[e["to"]] >= cols[e["from"]], f"edge {e['from']}->{e['to']} points left"
    for a, b in zip(ir.get("mainPath", []), ir.get("mainPath", [])[1:]):
        assert any(e["from"] == a and e["to"] == b for e in ir["edges"])
    assert [c["title"] for c in ir["cards"]] == ["Numbers (base)", "Rules"]


@pytest.mark.parametrize("idea_id", IDS)
def test_every_template_step_is_drawn_with_its_gates(idea_id):
    template = d.load_template(idea_id)
    nodes = {n["id"]: n for n in load_ir(idea_id)["nodes"]}
    gap_ids = {g["node"] for g in template.get("gaps", [])}
    exception = {lane["id"] for lane in load_ir(idea_id)["lanes"] if lane.get("variant") == "exception"}
    for t in template["nodes"]:
        assert t["id"] in nodes, f"template node {t['id']} ({t['kind']}) missing"
        drawn = nodes[t["id"]]
        tags = (drawn.get("tag") or "").split(", ")
        entry = CATALOG.get(t["kind"], {})
        is_gap = (t["kind"] == "unmapped" or t["id"] in gap_ids
                  or entry.get("backend", {}).get("kind") == "gap")
        if is_gap:
            assert drawn["lane"] in exception and "gap" in tags
        else:
            assert drawn["lane"] not in exception
        if entry.get("consent"):
            assert "consent" in tags
        if entry.get("adult"):
            assert "18+" in tags
    template_pairs = {(e["source"], e["target"]) for e in template.get("edges", [])}
    drawn_pairs = [(e["from"], e["to"]) for e in load_ir(idea_id)["edges"]]
    assert set(drawn_pairs) == template_pairs and len(drawn_pairs) == len(template_pairs)


@pytest.mark.parametrize("idea_id", IDS)
def test_html_is_delivered_next_to_its_source(idea_id):
    html = ir_path(idea_id).with_suffix(".html")
    assert html.exists() and html.stat().st_size > 0


def test_readme_lists_every_idea():
    readme = (d.OUT / "README.md").read_text(encoding="utf-8")
    for idea_id in IDS:
        assert f"| {idea_id} |" in readme
