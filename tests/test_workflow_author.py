"""Workflow author: every idea becomes a valid canvas workflow, gaps are visible, types line up."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import workflow_author as wa  # noqa: E402

CAT = wa.load_catalog()
IDEAS = yaml.safe_load((REPO / "brands" / "_business" / "ideas.yaml").read_text(encoding="utf-8"))["ideas"]


def test_catalogue_comfy_backends_exist_in_the_manifest():
    manifest = {w["canonical"].removeprefix("workflows/")
                for w in json.loads((REPO / "workflows" / "manifest.json").read_text(encoding="utf-8"))["workflows"]}
    missing = [n["kind"] for n in CAT["nodes"] if n["backend"]["kind"] == "comfy" and n["backend"]["workflow"] not in manifest]
    assert not missing, missing


def test_catalogue_python_backends_exist_in_the_repo():
    missing = [n["kind"] for n in CAT["nodes"] if n["backend"].get("module") and not (REPO / n["backend"]["module"]).exists()]
    assert not missing, missing


@pytest.mark.parametrize("idea", IDEAS, ids=[i["id"] for i in IDEAS])
def test_every_idea_authors_a_structurally_valid_workflow(idea):
    wf = wa.from_idea(idea["id"], "ongea-pesa")
    assert wa.validate(wf) == []
    assert wf["nodes"], "a workflow with no nodes is not a workflow"
    kinds = {n["kind"] for n in wf["nodes"]}
    assert kinds & {"export", "postiz", "whatsapp-status", "course"} or not any(
        o["type"] in ("image", "video") for n in wf["nodes"] if n["kind"] in CAT["by_kind"]
        for o in CAT["by_kind"][n["kind"]]["outputs"]), "media must end somewhere"


def test_steps_nothing_can_run_become_declared_gaps_not_silent_drops():
    wf = wa.author(["lora", "print-something-new"], "t", "epalle", {"test": True})
    gap_steps = {g["step"] for g in wf["gaps"]}
    assert "lora-train" in gap_steps and "print-something-new" in gap_steps
    assert wa.validate(wf) == []


def test_type_mismatches_are_caught():
    wf = wa.author(["tts"], "t", "epalle", {"test": True})
    audio = next(n for n in wf["nodes"] if n["kind"] == "voiceover")
    wf["nodes"].append({"id": "x", "kind": "carousel", "position": {"x": 0, "y": 0}, "data": {"params": {}}})
    wf["edges"].append({"id": "bad", "source": audio["id"], "sourceHandle": "audio",
                        "target": "x", "targetHandle": "image", "type": "audio"})
    assert any("cannot feed" in p for p in wa.validate(wf))


def test_a_sheng_whatsapp_brief_gets_voice_in_sheng_and_a_status_publisher():
    wf = wa.from_brief("Sheng WhatsApp status ad for a mama mboga using M-Pesa", "ongea-pesa")
    kinds = [n["kind"] for n in wf["nodes"]]
    assert "whatsapp-status" in kinds and "voiceover" in kinds and "claim-check" in kinds
    voice = next(n for n in wf["nodes"] if n["kind"] == "voiceover")
    assert voice["data"]["params"]["language"] == "sheng"
    assert wa.validate(wf) == []


def test_face_and_character_steps_flag_consent():
    assert wa.from_idea("S01", "epalle")["consent_required"] is True
    assert wa.from_idea("V08", "epalle")["consent_required"] is False


def test_seeded_client_workflows_exist_and_validate():
    for client, ideas in wa.SEED.items():
        for iid in ideas:
            name = wa.from_idea(iid, client)["id"]
            p = REPO / "brands" / client / "workflows" / f"{name}.studio.json"
            assert p.exists(), f"missing seeded workflow {p}"
            assert wa.validate(json.loads(p.read_text(encoding="utf-8"))) == []


def test_every_idea_has_a_saved_template():
    for idea in IDEAS:
        wf = wa.from_idea(idea["id"], wa.TEMPLATES)
        p = REPO / "brands" / wa.TEMPLATES / "workflows" / f"{wf['id']}.studio.json"
        assert p.exists(), f"missing template for {idea['id']}"


def test_combining_marries_one_workflows_media_into_the_next():
    video = wa.from_idea("M01", "epalle")
    rollout = wa.from_idea("M04", "epalle")
    wf = wa.combine([video, rollout], "MV to rollout", "epalle")
    assert wa.validate(wf) == []
    ids = {n["id"] for n in wf["nodes"]}
    assert len(ids) == len(wf["nodes"])
    assert sum(1 for n in wf["nodes"] if n["kind"] == "brand-kit") <= 1, "shared brand kit must merge"
    married = [e for e in wf["edges"] if e.get("married")]
    assert married and all(e["source"].startswith("a") and e["target"].startswith("b") for e in married)
    publish = [n for n in wf["nodes"] if CAT["by_kind"].get(n["kind"], {}).get("category") == "publish"]
    assert publish and all(n["id"].startswith("b") for n in publish), "only the last part keeps its ending"


def test_combining_keeps_every_gap_of_the_surviving_nodes():
    a = wa.author(["lora"], "lora part", "epalle", {"t": 1})
    b = wa.from_idea("M03", "epalle")
    wf = wa.combine([a, b], "gap check", "epalle")
    assert any(g["step"] == "lora-train" for g in wf["gaps"])
    assert wa.validate(wf) == []


def test_combining_needs_two_parts():
    with pytest.raises(wa.AuthorError):
        wa.combine([wa.from_idea("V08", "epalle")], "one", "epalle")


def test_saving_to_an_unknown_client_is_refused():
    wf = wa.from_idea("V08", "no-such-client")
    with pytest.raises(wa.AuthorError):
        wa.save(wf)
