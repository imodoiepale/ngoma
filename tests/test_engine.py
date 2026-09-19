"""The director engine: deterministic plans, presets as grammar, sessions that replay."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import director  # noqa: E402
import mutate  # noqa: E402
import presets  # noqa: E402
import session  # noqa: E402
import workflow_author as wa  # noqa: E402
from brief import EngineBrief  # noqa: E402

FIXTURE = json.loads((REPO / "tests" / "fixtures" / "engine_brief.json").read_text(encoding="utf-8"))
SNAPSHOT = REPO / "tests" / "fixtures" / "engine_plan_basic.json"


def brief(**over) -> EngineBrief:
    return EngineBrief.from_dict({**FIXTURE, **over})


def test_plan_is_deterministic_and_matches_the_snapshot():
    a, b = director.plan(brief()), director.plan(brief())
    assert a == b
    got = json.dumps(a, indent=2, ensure_ascii=False, sort_keys=True)
    if not SNAPSHOT.exists():
        SNAPSHOT.write_text(got, encoding="utf-8")
    assert got == SNAPSHOT.read_text(encoding="utf-8").replace("\r\n", "\n"), \
        "the director's plan changed; delete tests/fixtures/engine_plan_basic.json to accept it"


@pytest.mark.parametrize("k", [3, 5, 10, 20])
def test_expand_angles_returns_exactly_k(k):
    sc = director.storyboard(brief(scenes=1))[0]
    shots = director.expand_angles(sc, k, "neon-noir")
    assert len(shots) == k and len({s.camera for s in shots}) == k


def test_four_scenes_by_five_angles_gives_twenty_stills_and_four_picks():
    wf = director.plan(brief())
    gens = [n for n in wf["nodes"] if n["kind"] in ("h3-reference-image", "krea2-t2i")]
    picks = [n for n in wf["nodes"] if n["kind"] == "pick"]
    assert len(gens) == 20 and len(picks) == 4
    assert wa.validate(wf) == []
    assert {n["data"]["scene"] for n in gens} == {1, 2, 3, 4}


def test_a_scene_without_a_consented_or_fictional_character_uses_a_text_generator():
    wf = director.plan(brief(roles=[], refs=[]))
    kinds = {n["kind"] for n in wf["nodes"]}
    assert "krea2-t2i" in kinds and "h3-reference-image" not in kinds and "refmod-create" not in kinds


def test_a_real_person_without_a_release_gets_a_gap_not_a_face():
    b = brief(roles=[{"name": "me", "consent": False, "fictional": False, "ref_collection": "avatar-lead"}])
    with pytest.raises(director.DirectorError):
        director.plan(b)   # check_brief refuses a real person with no release


def test_unclear_rights_never_feed_a_node():
    b = brief(refs=[{"name": "wardrobe-x", "kind": "image", "use": "data", "rights": "unclear"}], roles=[])
    wf = director.plan(b)
    assert not any(n["kind"] == "wardrobe" for n in wf["nodes"])


def test_unknown_vfx_is_a_declared_gap_and_relight_stays_one():
    wf = director.plan(brief(vfx=["relight", "hologram"]))
    steps = {g["step"] for g in wf["gaps"]}
    assert "relight" in steps and "vfx-hologram" in steps


def test_presets_are_grammar_with_every_key_and_no_person():
    doc = presets.load_presets()
    assert len(doc["presets"]) >= 10 and len(doc["cameras"]) >= 20
    for key, p in doc["presets"].items():
        assert all(k in p for k in presets.GRAMMAR_KEYS), key
        assert presets.scene_fragments(p, 0)
        assert not presets.FORBIDDEN.search(" ".join(str(v) for v in p.values())), key


def test_forbidden_words_are_refused(tmp_path):
    bad = tmp_path / "d.yaml"
    bad.write_text("version: 1\ncameras: []\npresets:\n  x: {label: x, inspired_by: 'the face of a celebrity', framing: [a], lens: l, palette: [p], pacing: p, blocking: [b], grade: g, motion: m, negatives: []}\n", encoding="utf-8")
    presets.load_presets.cache_clear()
    with pytest.raises(presets.PresetError):
        presets.load_presets(bad)
    presets.load_presets.cache_clear()


@pytest.mark.parametrize("text", [
    "fincher", "Deakins", "malick", "wong kar-wai", "Wong Kar Wai", "gerwig", "cuaron", "Cuarón", "lubezki",
    "snyder", "coppola", "noe", "Noé",
    "shot by a famous cinematographer", "in the style of a famous director", "directed by someone",
])
def test_forbidden_refuses_the_names_and_attribution_phrases_the_guides_use(text):
    assert presets.FORBIDDEN.search(f"a wide shot {text} at dusk"), text


@pytest.mark.parametrize("text", ["snow", "no", "no daylight", "coppa", "shot on 35mm", "nolanesque", "noel", "the style block"])
def test_forbidden_leaves_innocent_words_alone(text):
    assert not presets.FORBIDDEN.search(text), text


def test_a_brief_that_names_a_director_is_refused_before_any_node_exists():
    with pytest.raises(director.DirectorError, match="names a person"):
        director.plan(brief(idea="a city evening in the style of Fincher"))
    with pytest.raises(director.DirectorError, match="scene_hints\\[1\\] names a person"):
        director.plan(brief(scene_hints=["rooftop", "wet street shot by Deakins"]))


def test_compose_motion_prompt_is_deterministic_and_has_the_beat_structure():
    p = presets.preset("impact-slow-motion")
    locks = ["same face and body", "wardrobe as attached", "vertical, figure centred"]
    neg = "no text, no logos, no spectators"
    args = ("Scene 1 (arrival): a sprinter leaves the blocks", p, 6, locks, neg)
    a = presets.compose_motion_prompt(*args, framing=p["framing"][0], blocking=p["blocking"][0])
    b = presets.compose_motion_prompt(*args, framing=p["framing"][0], blocking=p["blocking"][0])
    assert a == b
    lines = a.split("\n")
    assert lines[0].startswith("0-6s: ") and p["motion"] in lines[0] and p["framing"][0] in lines[0] and p["blocking"][0] in lines[0]
    assert lines[1].startswith("Style: ") and p["lens"] in lines[1] and p["grade"] in lines[1]
    assert lines[2].startswith("Hold constant across the whole clip: ") and all(lock in lines[2] for lock in locks)
    assert lines[3] == "Audio: sound effects and diegetic sound only. No music. No dialogue. No subtitles."
    assert lines[4] == f"Strictly exclude: {neg}."
    assert "\u2014" not in a and not presets.FORBIDDEN.search(a)
    # without locks or negatives the two optional lines are simply absent
    short = presets.compose_motion_prompt("a still", p, 4, [], "")
    assert short.startswith("0-4s: ") and "Hold constant" not in short and "Strictly exclude" not in short


@pytest.mark.parametrize("name", ["papercraft-relief", "painterly-cel", "impact-slow-motion"])
def test_the_presets_from_the_creator_guides_load_as_grammar(name):
    p = presets.preset(name)
    assert all(k in p for k in presets.GRAMMAR_KEYS)
    assert presets.scene_fragments(p, 0) and presets.negatives(p).startswith("no ")
    assert not presets.FORBIDDEN.search(" ".join(str(v) for v in p.values()))
    wf = director.plan(brief(preset=name))
    motion = [n for n in wf["nodes"] if n["kind"] in ("image-to-video", "motion-control")]
    assert motion and all(p["motion"] in n["data"]["prompt"] for n in motion)


def test_the_motion_prompt_says_the_blocking_exactly_once():
    wf = director.plan(brief())
    for sc in director.storyboard(brief()):
        node = next(n for n in wf["nodes"] if n["kind"] == "image-to-video" and n["data"]["scene"] == sc.n)
        beat = node["data"]["prompt"].split("\n")[0]
        assert beat.count(sc.blocking) == 1, beat
        assert sc.setting in beat and sc.framing in beat


def test_a_motion_clip_routes_the_scene_through_motion_control_with_a_prompt():
    b = brief(refs=[*FIXTURE["refs"], {"name": "motion-dance", "kind": "video", "use": "data", "rights": "owned"}])
    wf = director.plan(b)
    mc = [n for n in wf["nodes"] if n["kind"] == "motion-control"]
    assert len(mc) == 4 and not any(n["kind"] == "image-to-video" for n in wf["nodes"])
    for n in mc:
        assert n["data"]["prompt"].startswith("0-") and "prompt" in n["data"]["why"]
        assert any(e["target"] == n["id"] and e["source"] == "refs.video-clip.motion-dance" for e in wf["edges"])
    assert wa.validate(wf) == []
    # an unowned clip may not feed the step, so the scene falls back to still-to-video
    b = brief(refs=[*FIXTURE["refs"], {"name": "motion-dance", "kind": "video", "use": "data", "rights": "unclear"}])
    assert not any(n["kind"] == "motion-control" for n in director.plan(b)["nodes"])


def test_intents_are_recognised():
    i = session.intent
    assert i("add a scene at a rooftop at golden hour").name == "add_scene"
    assert i("add a scene at a rooftop at golden hour").args["hint"] == "a rooftop at golden hour"
    assert i("give me 10 angles per scene") == session.Intent("set_angles", {"k": 10})
    assert i("make the clips 6 seconds long").args["seconds"] == [6]
    assert i("use the neon noir look").name == "preset"
    assert i("wardrobe from my red-dress").args == {"purpose": "wardrobe", "name": "red-dress", "rights": "owned", "use": "data", "kind": "image"}
    assert i("switch to auto mode").name == "mode"
    assert i("keep at scene1.pick.keep: 1, 3, 4") == session.Intent("pick", {"node": "scene1.pick.keep", "indices": [1, 3, 4]})
    assert i("run the next stage").name == "run"
    assert i("undo that").name == "undo"
    assert i("something poetic about dusk").name == "note"


@pytest.fixture
def scratch_client(tmp_path, monkeypatch):
    """A throwaway client so sessions never touch real brand folders."""
    root = tmp_path / "brands"
    (root / "zz-test").mkdir(parents=True)
    (root / "zz-test" / "brand.yaml").write_text("name: ZZ Test\n", encoding="utf-8")
    monkeypatch.setattr(wa, "BRANDS", root)
    return "zz-test"


def test_session_replay_rebuilds_the_same_workflow(scratch_client):
    lines = ["a rooftop lookbook for a fictional persona", "use the neon noir look", "add a scene at a wet street",
             "give me 3 angles per scene", "wardrobe from my red-dress", "make the clips 5 seconds long"]
    a = session.replay(scratch_client, "s1", lines)
    h1 = hashlib.sha256(json.dumps(a["workflow"], sort_keys=True).encode()).hexdigest()
    shutil.rmtree(wa.workflow_dir(scratch_client))
    b = session.replay(scratch_client, "s1", lines)
    h2 = hashlib.sha256(json.dumps(b["workflow"], sort_keys=True).encode()).hexdigest()
    assert h1 == h2
    # "lookbook" in the first line picks that profile (4 scenes); "add a scene" makes 5
    assert b["session"]["brief"]["profile"] == "lookbook" and b["session"]["brief"]["scenes"] == 5
    assert b["session"]["brief"]["preset"] == "neon-noir"
    assert b["session"]["brief"]["angles_per_scene"] == 3 and any(r["name"] == "wardrobe-red-dress" for r in b["session"]["brief"]["refs"])
    assert b["pending_picks"] and wa.validate(b["workflow"]) == []


def test_undo_restores_the_previous_brief(scratch_client):
    session.replay(scratch_client, "s2", ["a test piece", "give me 10 angles per scene"])
    out = session.say(scratch_client, "s2", "undo")
    assert out["session"]["brief"]["angles_per_scene"] == 5
    assert sum(1 for n in out["workflow"]["nodes"] if n["kind"] == "krea2-t2i") == 5 * 3


def test_a_pick_survives_a_rebuild(scratch_client):
    out = session.replay(scratch_client, "s3", ["a test piece"])
    pick_id = out["pending_picks"][0]
    out = session.say(scratch_client, "s3", f"keep at {pick_id}: 1, 2")
    assert out["workflow"] and next(n for n in out["workflow"]["nodes"] if n["id"] == pick_id)["data"]["picked"]
    out = session.say(scratch_client, "s3", "add a scene at a market")
    assert next(n for n in out["workflow"]["nodes"] if n["id"] == pick_id)["data"]["picked"]
    with pytest.raises(mutate.MutateError):
        mutate.pick(out["workflow"], pick_id, [1, 2, 3, 4])
