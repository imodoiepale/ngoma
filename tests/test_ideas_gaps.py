"""The 50 idea templates: every one validates, every remaining gap is a named capability gap.

The table below is the list of true capability gaps as of 2026-09-20 (spec Part 2B, groups
G1-G9, after W6 built G1 motion-graphics, G3 lora-train and G6 translate). A template that
grows a gap not in this table, or loses one that is, fails here so the change is a decision
and never drift. Every gap must say exactly what would close it (a workflow, a module, a
model or an API), and every bound-but-gated step must point at its docs/BLOCKERS.md item.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
sys.path.insert(0, str(REPO / "packages" / "engine"))
import ports  # noqa: E402
import workflow_author as wa  # noqa: E402

CAT = wa.load_catalog()
IDEAS = yaml.safe_load((REPO / "brands" / "_business" / "ideas.yaml").read_text(encoding="utf-8"))["ideas"]
TEMPLATES = REPO / "brands" / "_templates" / "workflows"
BLOCKERS = (REPO / "docs" / "BLOCKERS.md").read_text(encoding="utf-8")

# idea -> gap steps still open, and why (the exact missing thing lives on the catalogue node)
EXPECTED_GAPS: dict[str, list[str]] = {
    "M01": ["relight"],           # G2: no video relight ComfyUI workflow in the library (the WanAnimate
                                  #     relight LoRA only matches a swapped character to the driving clip)
}
TRUE_GAP_KINDS = {"relight"}
TRUE_GAP_TOTAL = sum(len(v) for v in EXPECTED_GAPS.values())  # 1

# the gaps W6 closed: kind -> the python module that now runs it, and the ideas it unblocked
W6_MODULES = {
    "motion-graphics": ("packages/video/motion_graphics.py", {"M02", "M07", "S05", "S06", "U05", "V07"}),
    "lora-train": ("packages/engine/lora_train.py", {"S01", "X01"}),
    "translate": ("packages/voice/translate.py", {"S07"}),
}

# a gap is concrete when it names a file, a workflow, a model or an API, not a wish
CONCRETE = re.compile(r"(\.py\b|workflows/manifest\.json|\.ports\.json|ComfyUI workflow|OpenRouter|ai-toolkit|"
                      r"Remotion|HyperFrames|\.safetensors|Daraja)")

# the four port maps W4 owns (spec Part 4): kind -> workflow it drives
W4_PORT_MAPS = {
    "dataset": "icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-no_base-_subs_-_Icekiub_v2.json",
    "caption-dataset": "icekiub/AIO_-_Uncensored_captioning_workflow_-_subs_-_icekiub_v1.5.json",
    "text-to-video": "icekiub/LTX2-T2V_-_ICY.json",
    "long-video": "3-Image-To-Long-Video/3-Image-To-Long-Video.json",
}


def template(idea_id: str) -> dict:
    matches = sorted(TEMPLATES.glob(f"{idea_id.lower()}-*.studio.json"))
    assert len(matches) == 1, f"{idea_id}: expected one template, found {[m.name for m in matches]}"
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _shape(wf: dict) -> tuple:
    return (tuple((n["kind"], (n.get("data") or {}).get("step")) for n in wf["nodes"]),
            tuple((e["source"], e["sourceHandle"], e["target"], e["targetHandle"]) for e in wf["edges"]),
            tuple((g["node"], g["step"], g["reason"]) for g in wf["gaps"]))


@pytest.mark.parametrize("idea", IDEAS, ids=[i["id"] for i in IDEAS])
def test_template_validates_and_is_current(idea):
    wf = template(idea["id"])
    assert wa.validate(wf) == []
    fresh = wa.from_idea(idea["id"], wa.TEMPLATES)
    assert _shape(wf) == _shape(fresh), \
        f"{idea['id']} template is stale; re-run: python packages/strategy/workflow_author.py --all-ideas"


@pytest.mark.parametrize("idea", IDEAS, ids=[i["id"] for i in IDEAS])
def test_gaps_per_idea_match_the_table(idea):
    got = sorted(g["step"] for g in template(idea["id"])["gaps"])
    assert got == sorted(EXPECTED_GAPS.get(idea["id"], [])), \
        f"{idea['id']}: gaps {got}; update EXPECTED_GAPS only as a recorded decision"


def test_total_gaps_within_the_documented_true_gaps():
    total = 0
    for idea in IDEAS:
        wf = template(idea["id"])
        assert not [n for n in wf["nodes"] if n["kind"] == "unmapped"], f"{idea['id']}: unmapped step"
        for g in wf["gaps"]:
            assert g["step"] in TRUE_GAP_KINDS, (idea["id"], g)
            total += 1
    assert total == TRUE_GAP_TOTAL == 1


def test_w6_gaps_are_bound_to_real_modules():
    """motion-graphics, lora-train and translate are python steps on modules that exist, carry
    no `missing`, and appear in every idea they used to block."""
    for kind, (module, ideas) in W6_MODULES.items():
        be = CAT["by_kind"][kind]["backend"]
        assert be["kind"] == "python" and be["module"] == module, kind
        assert (REPO / module).exists(), module
        assert "missing" not in be and "reason" not in be, kind
        for idea in ideas:
            wf = template(idea)
            assert kind in [n["kind"] for n in wf["nodes"]], (idea, kind)
            assert not [g for g in wf["gaps"] if g["step"] == kind], (idea, kind)
    # the LoRA job depends on the pod (ai-toolkit clone, licence-gated base model) and says so
    assert CAT["by_kind"]["lora-train"]["needs_setup"]["blocker"] == 3
    assert "ai-toolkit" in CAT["by_kind"]["lora-train"]["needs_setup"]["what"]
    # the captions the caption-dataset step writes feed the LoRA job
    for idea in ("S01", "X01"):
        wf = template(idea)
        kinds = {n["id"]: n["kind"] for n in wf["nodes"]}
        assert any(kinds[e["source"]] == "caption-dataset" and kinds[e["target"]] == "lora-train"
                   and e["targetHandle"] == "captions" for e in wf["edges"]), idea
    # the avatar clip sits under the title cards in S05
    kinds = {n["id"]: n["kind"] for n in template("S05")["nodes"]}
    assert any(kinds[e["source"]] == "lipsync" and kinds[e["target"]] == "motion-graphics"
               and e["targetHandle"] == "background" for e in template("S05")["edges"])


def test_every_catalogue_gap_names_the_concrete_missing_thing():
    gaps = [n for n in CAT["nodes"] if n["backend"]["kind"] == "gap"]
    assert {n["kind"] for n in gaps} == TRUE_GAP_KINDS, "a new gap kind needs a row in TRUE_GAP_KINDS"
    for n in gaps:
        be = n["backend"]
        assert be.get("reason", "").strip(), n["kind"]
        assert CONCRETE.search(be.get("missing", "")), f"{n['kind']}: `missing` must name a file, workflow, model or API"


def test_every_template_gap_reason_is_the_catalogue_reason():
    for idea in IDEAS:
        for g in template(idea["id"])["gaps"]:
            assert g["reason"] == CAT["by_kind"][g["step"]]["backend"]["reason"], (idea["id"], g)


def test_every_idea_with_an_open_gap_records_its_decision():
    for idea in IDEAS:
        if idea["id"] in EXPECTED_GAPS:
            assert idea.get("decisions"), f"{idea['id']}: add a dated `decisions` entry in ideas.yaml"
            assert any(re.match(r"\d{4}-\d{2}-\d{2}:", d) for d in idea["decisions"]), idea["id"]


def test_needs_setup_points_at_a_blockers_item():
    gated = [n for n in CAT["nodes"] if n.get("needs_setup")]
    assert {n["kind"] for n in gated} >= {"carousel", "h3-reference-image"}
    for n in gated:
        ns = n["needs_setup"]
        assert isinstance(ns["blocker"], int) and ns["what"].strip(), n["kind"]
        assert re.search(rf"^## {ns['blocker']}\. ", BLOCKERS, re.M), f"{n['kind']}: no item {ns['blocker']} in docs/BLOCKERS.md"
        assert n["backend"]["kind"] != "gap", "needs_setup is for bound steps; a gap uses backend.missing"


def test_business_steps_are_bound_to_real_modules():
    kinds = {i: [n["kind"] for n in template(i)["nodes"]] for i in ("A02", "A03", "E03", "E05")}
    assert "image-hosted" in kinds["A02"] and "compositor" in kinds["A02"]
    assert "comfy-api" in kinds["A03"]
    assert "register-workflow" in kinds["E03"]
    assert "studio-handoff" in kinds["E05"] and "course" in kinds["E05"]
    for kind in ("comfy-api", "register-workflow", "studio-handoff"):
        be = CAT["by_kind"][kind]["backend"]
        assert be["kind"] == "python" and (REPO / be["module"]).exists(), kind


def test_interim_steps_run_on_existing_workflows():
    manifest = {w["canonical"].removeprefix("workflows/")
                for w in json.loads(wa.MANIFEST.read_text(encoding="utf-8"))["workflows"]}
    restore = CAT["by_kind"]["restore"]["backend"]
    assert restore["kind"] == "comfy" and restore["workflow"] in manifest
    assert CAT["by_step"]["product-relight"]["kind"] == "image-edit"
    assert "restore" in [n["kind"] for n in template("S04")["nodes"]]
    assert "image-edit" in [n["kind"] for n in template("S02")["nodes"]]


def test_w4_port_maps_exist_and_validate(monkeypatch):
    for kind, workflow in W4_PORT_MAPS.items():
        assert CAT["by_kind"][kind]["backend"]["workflow"] == workflow, kind
        assert ports.port_map_path(workflow).exists(), f"{kind}: no .ports.json beside {workflow}"
    monkeypatch.setattr(ports, "ENGINE_KINDS", list(W4_PORT_MAPS))
    assert ports.validate_port_maps(CAT) == []
