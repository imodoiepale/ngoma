"""Generated docs exist for every idea and every workflow, and agree with the numbers they come from."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import proposals  # noqa: E402
import workflow_catalog as wc  # noqa: E402


def test_every_manifest_workflow_has_a_description():
    missing = [r["canonical"] for r in wc.load()["rows"] if not r["does"]]
    assert not missing, f"add them to workflow_catalog.DESCRIPTIONS: {missing}"


def test_catalogue_names_no_workflow_that_is_not_in_the_manifest():
    manifest = {w["canonical"] for w in json.loads(wc.MANIFEST.read_text(encoding="utf-8"))["workflows"]}
    assert set(wc.DESCRIPTIONS) <= manifest, set(wc.DESCRIPTIONS) - manifest


def test_workflow_library_doc_is_current():
    assert wc.OUT.read_text(encoding="utf-8") == wc.render(wc.load()), \
        "re-run: uv run python packages/strategy/workflow_catalog.py"


def test_there_is_a_proposal_per_idea_and_it_matches_the_costing():
    props, families = proposals.build_all()
    assert len(props) == 50
    for p in props:
        i = p["idea"]
        f = proposals.OUT / f"{i['id'].lower()}-{proposals.slug(i['name'])}.md"
        assert f.exists(), f
        assert f.read_text(encoding="utf-8") == proposals.render(p, families), \
            f"re-run: uv run --with pyyaml python packages/strategy/proposals.py ({f.name})"
    index = (proposals.OUT / "README.md").read_text(encoding="utf-8")
    assert index == proposals.render_index(props, families)


def test_a_gap_is_never_counted_as_ready():
    props, _ = proposals.build_all()
    for p in props:
        for s in p["steps"]:
            if s["gap"]:
                assert s["runs"] == "not runnable yet", (p["idea"]["id"], s)
