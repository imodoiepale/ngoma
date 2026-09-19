"""Describe to workflow: a sentence becomes (or extends) a workflow, the seven intent gaps
from the spec are closed, a person's name is refused before any node exists.

Spec: docs/superpowers/specs/2026-09-20-general-creative-studio-design.md, Part 2C and W2.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import intents  # noqa: E402
import session  # noqa: E402
import workflow_author as wa  # noqa: E402

CAT = wa.load_catalog()
SENTENCE = "change the character in my 50 reference images to my persona, then a carousel of 10 slides for each"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A throwaway workspace with two reference collections, so nothing touches brands/."""
    root = tmp_path / "brands"
    ws = root / "zz-describe"
    (ws / "workflows").mkdir(parents=True)
    (ws / "brand.yaml").write_text("name: ZZ Describe\n", encoding="utf-8")
    for name, n in (("red-dress", 3), ("wardrobe-red-dress", 2)):
        d = ws / "references" / name
        d.mkdir(parents=True)
        (d / "collection.json").write_text(json.dumps({"name": name, "use": "data", "rights": "owned", "kind": "image", "consent": False}), encoding="utf-8")
        for i in range(n):
            (d / f"look-{i}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(wa, "BRANDS", root)
    return "zz-describe"


def steps_of(out: dict) -> list[str]:
    return out["steps"]


# ---------------------------------------------------------------- the seven intents

def test_intent_1_quantity_and_collection_attach_a_reference_folder_with_its_count(workspace):
    out = session.describe(workspace, "change the character in my 50 reference images from red-dress to our persona", mode="plan")
    refs = [n for n in out["workflow"]["nodes"] if n["kind"] == "reference-images"]
    batch = next(n for n in refs if n["data"].get("collection") == "red-dress")
    assert batch["data"]["params"]["folder"] == f"brands/{workspace}/references/red-dress"
    assert batch["data"]["expected_count"] == 50
    assert out["plan"]["estimate"]["items"] == 3, "the folder on disk (3 files) is the run-time truth over the brief's 50"
    assert out["plan"]["estimate"]["items_basis"] == "disk"


def test_intent_1_an_unnamed_batch_keeps_the_count_and_asks_for_the_folder_as_an_input(workspace):
    out = session.describe(workspace, SENTENCE, mode="plan")
    batch = next(n for n in out["workflow"]["nodes"] if n["kind"] == "reference-images" and n["data"].get("expected_count"))
    assert batch["data"]["expected_count"] == 50 and not batch["data"]["params"].get("folder")
    assert any(i["kind"] == "reference-images" and i["expected_count"] == 50 and "red-dress" in i["options"] for i in out["plan"]["inputs"])
    assert out["plan"]["estimate"]["items"] == 50 and out["plan"]["estimate"]["items_basis"] == "brief"


def test_intent_2_change_the_character_is_a_swap_never_a_refmod(workspace):
    for text in ("change the character in my 50 reference images to my persona",
                 "swap the face in these photos to our persona", "run the character changer on my references",
                 "put our persona in the red-dress photos"):
        out = session.describe(workspace, text, mode="plan")
        kinds = [n["kind"] for n in out["workflow"]["nodes"]]
        assert "klein-headswap" in kinds and "refmod-create" not in kinds, text
        swap = next(n for n in out["workflow"]["nodes"] if n["kind"] == "klein-headswap")
        assert swap["data"]["alias"] == "character-swap"
        face, image = [e for e in out["workflow"]["edges"] if e["target"] == swap["id"] and e["targetHandle"] == "face"], \
                      [e for e in out["workflow"]["edges"] if e["target"] == swap["id"] and e["targetHandle"] == "image"]
        assert face and image and face[0]["source"] != image[0]["source"], "the face to put in is not the batch it goes into"
    out = session.describe(workspace, "change the outfit in my 20 photos to the clothes from wardrobe-red-dress", mode="plan")
    kinds = [n["kind"] for n in out["workflow"]["nodes"]]
    assert "wardrobe" in kinds and "klein-headswap" not in kinds and "refmod-create" not in kinds
    clothes = next(n for n in out["workflow"]["nodes"] if n["data"].get("role") == "clothes")
    assert clothes["data"]["collection"] == "wardrobe-red-dress"


def test_intent_3_per_item_phrases_mark_the_step_each(workspace):
    for text in ("a carousel for each image", "carousels per post from my references", "make a carousel for each of them",
                 "a carousel across all of them"):
        assert "carousel@each" in wa.steps_from_brief(text), text
    assert "carousel" in wa.steps_from_brief("a carousel from one product photo") and \
        "carousel@each" not in wa.steps_from_brief("a carousel from one product photo")
    out = session.describe(workspace, SENTENCE, mode="plan")
    assert {"character-swap@each", "carousel@each"} <= set(steps_of(out))
    assert wa.validate(out["workflow"]) == []


def test_intent_4_n_slides_sets_the_carousel_parameter(workspace):
    out = session.describe(workspace, SENTENCE, mode="plan")
    car = next(s for s in out["plan"]["steps"] if s["kind"] == "carousel")
    assert car["params"]["slides"] == 10 and car["each"] is True
    assert wa.parse_brief("a carousel of five slides")["params"]["carousel"]["slides"] == 5
    assert wa.parse_brief("carousel, slides: 8")["params"]["carousel"]["slides"] == 8
    assert wa.parse_brief("a carousel")["params"] == {}, "no count means the catalogue default"
    # the estimate prices a carousel per slide: 50 items x 10 slides
    car_cost = next(p for p in out["plan"]["estimate"]["per_node"] if p["kind"] == "carousel")
    assert car_cost["items"] == 500


def test_intent_5_then_keeps_the_users_order_over_rule_order():
    # rule order would put the carousel before the voice-over; the sentence says otherwise
    steps = wa.steps_from_brief("a swahili voiceover, then a carousel of 6 slides")
    assert steps.index("tts") < steps.index("carousel")
    steps = wa.steps_from_brief("a carousel of 6 slides, then a swahili voiceover")
    assert steps.index("carousel") < steps.index("tts")
    assert [c["text"] for c in wa.parse_brief("upscale it. After that, publish on instagram")["clauses"]] == ["upscale it", "publish on instagram"]


def test_intent_6_a_continuation_extends_the_same_workflow_and_keeps_ids_and_each(workspace):
    first = session.describe(workspace, SENTENCE, session_id="s-cont")
    assert first["id"] and first["saved"] and first["session"]["route"] == "author"
    before = {n["id"]: n for n in first["workflow"]["nodes"]}
    second = session.describe(workspace, "now add captions and export", session_id="s-cont")
    assert second["extended"] and second["id"] == first["id"]
    after = {n["id"]: n for n in second["workflow"]["nodes"]}
    assert set(before) <= set(after), "extending renames nothing"
    for nid, node in before.items():
        assert wa.is_each(after[nid]) == wa.is_each(node) and after[nid]["kind"] == node["kind"]
    assert "captions" in [after[i]["kind"] for i in second["added"]]
    assert wa.validate(second["workflow"]) == []
    saved = json.loads((wa.workflow_dir(workspace) / f"{first['id']}.studio.json").read_text(encoding="utf-8"))
    assert saved["source"]["extended"][-1]["steps"] == ["captions"] or "captions" in saved["source"]["extended"][-1]["steps"]
    sess = json.loads((wa.workflow_dir(workspace) / f"{first['id']}.session.json").read_text(encoding="utf-8"))
    assert sess["utterances"] == [SENTENCE, "now add captions and export"]


def test_intent_6_the_canvas_spelling_extends_too_and_an_option_becomes_a_proposed_continuation(workspace):
    first = session.describe(workspace, "a carousel of 6 slides from red-dress", session_id="s-canvas")
    out = session.describe(workspace, "wan-i2v@each seconds=6", workflow_id=first["id"])
    added = [n for n in out["workflow"]["nodes"] if n["id"] in out["added"]]
    i2v = next(n for n in added if n["kind"] == "image-to-video")
    assert wa.is_each(i2v) and i2v["data"]["params"]["seconds"] == 6
    assert wa.validate(out["workflow"]) == []
    plan = session.describe(workspace, "a carousel of 5 slides from red-dress, then we could also make a reel for each", mode="plan")
    assert plan["continuations"] and plan["continuations"][0]["step"] == "wan-i2v" and plan["continuations"][0]["each"] is True
    assert "estimate" in plan["continuations"][0] and "image-to-video" not in [n["kind"] for n in plan["workflow"]["nodes"]]


def test_intent_7_an_unknown_collection_is_a_question_with_the_real_options_and_nothing_is_saved(workspace):
    out = session.describe(workspace, "use my 50 reference images from persona-nadia and make carousels for each", session_id="s-q")
    assert out["id"] is None and not out["saved"]
    assert [q["key"] for q in out["questions"]] == ["collection"]
    assert out["questions"][0]["options"] == ["red-dress", "wardrobe-red-dress"]
    assert not list(wa.workflow_dir(workspace).glob("*.studio.json"))
    answered = session.describe(workspace, "use my 50 reference images from persona-nadia and make carousels for each",
                                session_id="s-q", answers={"collection": "red-dress"})
    assert answered["questions"] == [] and answered["id"]
    batch = next(n for n in answered["workflow"]["nodes"] if n["kind"] == "reference-images")
    assert batch["data"]["collection"] == "red-dress"


def test_intent_7_a_brief_with_no_recognisable_step_asks_what_to_make_and_never_more_than_two_questions(workspace):
    out = session.describe(workspace, "something for the launch", mode="plan")
    assert [q["key"] for q in out["questions"]] == ["kind"] and len(out["questions"]) <= 2
    out = session.describe(workspace, SENTENCE, mode="plan")
    assert out["questions"] == []


# ---------------------------------------------------------------- the gates and the contract

@pytest.mark.parametrize("text", ["a city evening in the style of Fincher", "portraits shot by Deakins for each image",
                                  "swap the face to a celebrity in my 50 photos"])
def test_forbidden_names_are_refused_at_brief_level_before_any_node_exists(workspace, text):
    with pytest.raises(session.DescribeError, match="names a person"):
        session.describe(workspace, text)
    assert not list(wa.workflow_dir(workspace).glob("*.studio.json"))
    assert intents.refusal(text) and "Describe the look instead" in intents.refusal(text)


def test_the_describe_cli_returns_the_contract_and_a_json_error_on_refusal(workspace):
    # the CLI runs in another process, so it sees the real brands/; plan mode writes nothing
    env = {"PYTHONIOENCODING": "utf-8"}
    import os
    r = subprocess.run([sys.executable, str(REPO / "packages" / "engine" / "cli.py"), "describe", "--client", "epalle",
                        "--text", SENTENCE, "--mode", "plan", "--json"], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, **env}, cwd=REPO)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert set(out) >= {"id", "workflow", "plan", "steps", "continuations", "questions", "route", "reply", "added", "extended", "saved", "mode", "session"}
    assert out["id"] is None and out["route"] == "author" and out["questions"] == []
    assert {"character-swap@each", "carousel@each"} <= set(out["steps"])
    assert set(out["plan"]) >= {"steps", "gaps", "estimate", "consent_required", "inputs"}
    assert set(out["plan"]["steps"][0]) >= {"id", "kind", "step", "each", "params", "backend", "status"}
    assert set(out["plan"]["estimate"]) >= {"usd", "basis", "items"}
    assert out["plan"]["consent_required"] is True
    assert all(s["status"] in ("ready", "needs-setup", "gap", "input", "decide") for s in out["plan"]["steps"])
    bad = subprocess.run([sys.executable, str(REPO / "packages" / "engine" / "cli.py"), "describe", "--client", "epalle",
                          "--text", "a city evening in the style of Fincher", "--json"], capture_output=True, text=True,
                         encoding="utf-8", env={**os.environ, **env}, cwd=REPO)
    assert bad.returncode == 2
    err = json.loads(bad.stdout)
    assert err["refused"] is True and "names a person" in err["error"] and err["id"] is None


def test_a_profile_or_preset_routes_to_the_director_and_a_plain_brief_to_the_author(workspace):
    assert intents.route("a rooftop lookbook for a fictional persona") == "director"
    assert intents.route("a product demo in the neon noir look") == "director"
    assert intents.route(SENTENCE) == "author"
    out = session.describe(workspace, "a rooftop lookbook for a fictional persona", session_id="s-dir")
    assert out["route"] == "director" and out["workflow"].get("stages") and out["session"]["route"] == "director"
    assert out["plan"]["pending_picks"]
    more = session.describe(workspace, "give me 3 angles per scene", session_id="s-dir")
    assert more["extended"] and more["route"] == "director" and more["id"] == out["id"]
    assert sum(1 for n in more["workflow"]["nodes"] if n["kind"] == "krea2-t2i") == 3 * 4


def test_plan_mode_writes_nothing_on_either_route(workspace):
    session.describe(workspace, SENTENCE, mode="plan")
    session.describe(workspace, "a rooftop lookbook for a fictional persona", mode="plan")
    assert not list(wa.workflow_dir(workspace).glob("*"))


def test_continuation_phrases_are_stripped_to_what_to_add():
    assert intents.continuation("now add captions and export") == "captions and export"
    assert intents.continuation("Also, a carousel for each") == "a carousel for each"
    assert intents.continuation("then publish on instagram") == "publish on instagram"
    assert intents.continuation("carousel@each slides=10") is None


def test_session_intents_still_live_where_the_tests_expect_them():
    assert session.intent is intents.intent and session.Intent is intents.Intent
    assert session.intent("add a scene at a rooftop").name == "add_scene"
