"""The runner: dry runs write manifests and submit nothing; modes gate spending; picks and
publishing stop auto; queued is never completed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
sys.path.insert(0, str(REPO / "packages" / "orchestrator"))
import cost  # noqa: E402
import director  # noqa: E402
import runner  # noqa: E402
import workflow_author as wa  # noqa: E402
from brief import EngineBrief  # noqa: E402

FIXTURE = json.loads((REPO / "tests" / "fixtures" / "engine_brief.json").read_text(encoding="utf-8"))


class FakeComfy:
    """Pretends to be ComfyUI. Records submissions; completes or stays queued on demand."""
    calls: list[dict] = []
    uploads: list[str] = []
    outcome = "COMPLETED"

    def __init__(self, backend="pod"):
        self.backend, self.base_url = backend, "http://fake"

    def submit(self, graph, workflow_name=None, dry_run=True):
        FakeComfy.calls.append({"dry_run": dry_run, "name": workflow_name})
        assert not dry_run
        return {"prompt_id": f"p{len(FakeComfy.calls)}"}

    def upload(self, path, subfolder="studio", overwrite=True):
        FakeComfy.uploads.append(Path(path).name)
        return f"{subfolder}/{Path(path).name}"

    def wait(self, pid, **_):
        if FakeComfy.outcome == "COMPLETED":
            return {"status": "COMPLETED", "outputs": [{"filename": f"{pid}.png", "subfolder": "", "type": "output"}]}
        return {"status": FakeComfy.outcome}


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "brands"
    (root / "zz-test").mkdir(parents=True)
    (root / "zz-test" / "brand.yaml").write_text("name: ZZ\n", encoding="utf-8")
    monkeypatch.setattr(wa, "BRANDS", root)
    monkeypatch.setattr(runner, "BRANDS", root)
    for name in ("avatar-lead", "wardrobe-red", "location-rooftop", "mood-neon"):   # what the brief attaches
        (root / "zz-test" / "references" / name).mkdir(parents=True)
        (root / "zz-test" / "references" / name / "one.png").write_bytes(b"\x89PNG stub")
    def fetch(c, o, dest):
        rel = f"brands/zz-test/runs/x/{o['filename']}"
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"\x89PNG stub")
        return rel, "0" * 64
    monkeypatch.setattr(runner, "_fetch", fetch)
    FakeComfy.calls, FakeComfy.uploads, FakeComfy.outcome = [], [], "COMPLETED"
    wf = director.plan(EngineBrief.from_dict({**FIXTURE, "client": "zz-test", "scenes": 1, "angles_per_scene": 3, "vfx": []}))
    wa.save(wf)
    return {"client": "zz-test", "wf": wf, "db": tmp_path / "control.sqlite3", "tmp": tmp_path}


def test_dry_run_writes_manifests_and_submits_nothing(world):
    out = runner.run_stage(world["client"], world["wf"]["id"], "scene1", mode="dry-run", db=world["db"], comfy_factory=FakeComfy)
    assert out["ok"] and FakeComfy.calls == []
    gens = [r for r in out["results"] if r["kind"] == "h3-reference-image"]
    assert gens and all(r["status"] == "dry-run" for r in gens)
    manifests = list((world["tmp"] / "brands" / "zz-test" / "runs").rglob("manifest.json"))
    assert manifests and all(json.loads(m.read_text(encoding="utf-8"))["status"] == "dry-run" for m in manifests)
    assert all(r["cost_estimate"]["usd"] > 0 for r in gens)


def test_next_stage_treats_a_dry_run_as_finished(world):
    cat = wa.load_catalog()
    assert runner.next_stage(world["wf"], cat) == "refs"
    out = runner.run_stage(world["client"], world["wf"]["id"], "next", mode="dry-run",
                           db=world["db"], comfy_factory=FakeComfy, wf=world["wf"])
    assert out["ok"] and out["stage"] == "refs"
    nxt = runner.next_stage(world["wf"], cat)
    assert nxt not in (None, "refs")


def test_stage_approval_never_submits_before_a_human_approves(world):
    out = runner.run_stage(world["client"], world["wf"]["id"], "scene1", mode="stage-approval", db=world["db"], comfy_factory=FakeComfy)
    assert not out["ok"] and "approve" in out["note"] and FakeComfy.calls == []


def test_a_budget_of_zero_blocks_spending_even_when_approved(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 0.0)
    out = runner.run_stage(world["client"], world["wf"]["id"], "scene1", mode="stage-approval", approve_as="human", db=world["db"], comfy_factory=FakeComfy)
    assert not out["ok"] and "Budget" in out["note"] and FakeComfy.calls == []


def _run(world, stage, **kw):
    return runner.run_stage(world["client"], world["wf"]["id"], stage, db=world["db"], comfy_factory=FakeComfy, **kw)


def test_a_stage_whose_inputs_were_never_made_is_blocked_not_faked(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    out = _run(world, "scene1", mode="stage-approval", approve_as="human")
    gens = [r for r in out["results"] if r["kind"] == "h3-reference-image"]
    assert not out["ok"] and all(r["status"] == "blocked" for r in gens) and FakeComfy.calls == []
    assert "refs.character-sheet" in gens[0]["note"]


def test_approved_stages_within_budget_run_and_complete(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    refs = _run(world, "refs", mode="stage-approval", approve_as="human")
    assert refs["ok"] and {r["kind"]: r["status"] for r in refs["results"]}["character-sheet"] == "completed"
    out = _run(world, "scene1", mode="stage-approval", approve_as="human")
    gens = [r for r in out["results"] if r["kind"] == "h3-reference-image"]
    assert len(gens) == 3 and all(r["status"] == "completed" for r in gens)
    assert len(FakeComfy.calls) == 1 + 3 and out["pending_picks"]
    # every input went onto the pod first: the reference photo, then the sheet for each angle
    assert FakeComfy.uploads == ["one.png"] + ["p1.png"] * 3


def test_an_input_that_is_not_on_disk_is_an_error_not_a_submission(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    monkeypatch.setattr(runner, "_provided", lambda node: {"run_id": "provided", "status": "provided", "files": ["brands/zz-test/gone.png"]})
    out = _run(world, "refs", mode="stage-approval", approve_as="human")
    assert not out["ok"] and FakeComfy.calls == []
    assert any(r["status"] == "error" for r in out["results"])


def test_queued_or_timed_out_is_never_completed(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    FakeComfy.outcome = "TIMEOUT"
    out = _run(world, "refs", mode="stage-approval", approve_as="human")
    assert not out["ok"] and any(r["status"] == "timeout" for r in out["results"])


def test_auto_needs_one_engine_run_approval_then_stops_at_the_pick(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    out = _run(world, "refs", mode="auto")
    assert not out["ok"] and "engine_run" in out["note"] and FakeComfy.calls == []
    assert _run(world, "refs", mode="auto", approve_as="human")["ok"]
    out = _run(world, "scene1", mode="auto")          # the one approval covers later stages
    assert out["ok"] and len(FakeComfy.calls) == 4
    # the motion stage hangs off the pick, which nobody has made: it waits rather than runs
    out = _run(world, "scene1-motion", mode="auto")
    assert out["waiting_on_pick"] and len(FakeComfy.calls) == 4


def _edit_world(world, monkeypatch, narrated=True):
    """A finished clip on every motion step and the pick made, so the edit stage has inputs."""
    import edit
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    wf = director.plan(EngineBrief.from_dict({**FIXTURE, "client": "zz-test", "scenes": 1, "angles_per_scene": 3, "vfx": [],
                                              "profile": "product-demo" if narrated else "lookbook"}))
    clip = world["tmp"] / "brands" / "zz-test" / "runs" / "x" / "clip.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"stub")
    for n in wf["nodes"]:
        if n["data"].get("stage", "").endswith("-motion"):
            n["data"]["results"] = [{"run_id": "r1", "status": "completed", "files": ["brands/zz-test/runs/x/clip.mp4"]}]
        if n["kind"] == "pick":
            n["data"]["picked"] = ["x#r#0"]
    calls = []

    def fake(name, produce):
        def f(*a, dry_run=True, **k):
            calls.append(name)
            if dry_run:
                return {"status": "dry-run", "files": []}
            dest = next(x for x in list(a) + list(k.values()) if isinstance(x, Path) and x.suffix in (".mp4", ".mp3"))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"made")
            return {"status": "completed", "files": [str(dest)]}
        return f
    monkeypatch.setattr(edit, "voiceover", fake("voiceover", True))
    monkeypatch.setattr(edit, "concat", fake("cut", True))
    monkeypatch.setattr(edit, "captions", fake("captions", True))
    return wf, calls


def test_the_edit_stage_cuts_narrates_and_captions_on_this_machine(world, monkeypatch):
    wf, calls = _edit_world(world, monkeypatch)
    out = runner.run_stage("zz-test", wf["id"], "edit", mode="stage-approval", approve_as="human", db=world["db"],
                           comfy_factory=FakeComfy, wf=wf, save=False)
    status = {r["kind"]: r["status"] for r in out["results"]}
    assert out["ok"], out
    assert status == {"cut": "completed", "voiceover": "completed", "captions": "completed"}
    assert calls.index("captions") > calls.index("cut") and calls.index("captions") > calls.index("voiceover")
    assert FakeComfy.calls == []


def test_paid_narration_waits_for_approval(world, monkeypatch):
    wf, calls = _edit_world(world, monkeypatch)
    out = runner.run_stage("zz-test", wf["id"], "edit", mode="stage-approval", db=world["db"], comfy_factory=FakeComfy, wf=wf, save=False)
    assert not out["ok"] and "approve" in out["note"] and calls == []


def test_the_edit_stage_dry_run_calls_nothing_that_spends(world, monkeypatch):
    wf, calls = _edit_world(world, monkeypatch)
    out = runner.run_stage("zz-test", wf["id"], "edit", mode="dry-run", db=world["db"], wf=wf, save=False)
    assert out["ok"] and all(r["status"] == "dry-run" for r in out["results"])


def test_export_copies_the_final_files(world, tmp_path):
    import edit
    src = tmp_path / "final.mp4"
    src.write_bytes(b"final")
    r = edit.export([src], tmp_path / "out", dry_run=False)
    assert r["status"] == "completed" and (tmp_path / "out" / "final.mp4").read_bytes() == b"final"
    assert edit.export([src], tmp_path / "out2")["status"] == "dry-run" and not (tmp_path / "out2").exists()


def test_publishing_always_needs_a_person(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    wf = director.plan(EngineBrief.from_dict({**FIXTURE, "client": "zz-test", "scenes": 1, "outputs": ["postiz"], "vfx": []}))
    wa.save(wf)
    out = runner.run_stage("zz-test", wf["id"], "publish", mode="auto", approve_as="human", db=world["db"], comfy_factory=FakeComfy)
    assert not out["ok"] and "human" in out["note"]


def test_cost_estimates_say_measured_or_assumed():
    assert cost.estimate("klein-t2i", 10)["basis"] == "measured"
    v = cost.estimate("image-to-video", 2, seconds_of_video=6)
    assert v["basis"] == "assumed" and v["usd"] > 0
    assert cost.estimate("cut")["usd"] == 0
    # every estimate says how many items it covers; a plain node is one item
    assert cost.estimate("klein-t2i")["items"] == 1 and cost.estimate("klein-t2i")["per_item_gpu_seconds"] == 8.1


def test_a_carousel_is_priced_per_slide():
    assert cost.estimate("carousel", slides=6)["gpu_seconds"] == 60
    node = {"kind": "carousel", "data": {"params": {"slides": 6}}}
    assert cost.estimate_node(node)["gpu_seconds"] == 60 and cost.estimate_node(node, items=4)["gpu_seconds"] == 240


def test_manifests_carry_the_studio_workflow_id_and_the_comfy_workflow_separately(world):
    runner.run_stage(world["client"], world["wf"]["id"], "refs", mode="dry-run", db=world["db"], comfy_factory=FakeComfy)
    m = next(json.loads(p.read_text(encoding="utf-8")) for p in (world["tmp"] / "brands" / "zz-test" / "runs").rglob("manifest.json")
             if "character-sheet" in p.as_posix())
    assert m["workflow"] == world["wf"]["id"] and m["comfy_workflow"].endswith(".json") and m["each"] is False
    assert m["cost_estimate"]["items"] == 1


def test_a_run_stage_result_totals_the_estimate(world):
    out = runner.run_stage(world["client"], world["wf"]["id"], "scene1", mode="dry-run", db=world["db"], comfy_factory=FakeComfy)
    assert out["cost_estimate"]["usd"] > 0 and out["cost_estimate"]["basis"] == "assumed" and out["cost_estimate"]["items"] == 3


# ---------------------------------------------------------------- python steps the engine runs itself

def test_local_steps_cover_the_python_kinds_the_ideas_need():
    assert {"compositor", "claim-check", "hooks", "transcribe", "export", "cut", "captions", "voiceover",
            "motion-graphics", "translate", "lora-train"} <= runner.LOCAL_STEPS
    cat = wa.load_catalog()
    for kind in runner.LOCAL_STEPS:
        assert cat["by_kind"][kind]["backend"]["kind"] == "python", f"{kind} is local but not a python backend"


def _authored(world, steps, texts=None):
    """An authored (stage-less) workflow for the scratch client, saved so run_stage can read it."""
    wf = wa.author(steps, "local steps", "zz-test", {"test": True})
    for n in wf["nodes"]:
        if n["kind"] == "brief":
            n["data"]["params"]["text"] = (texts or {}).get("brief", "A savings app for small traders")
        if n["kind"] == "reference-images":
            n["data"]["params"]["folder"] = "brands/zz-test/references/avatar-lead"
    wa.save(wf)
    return wf


def test_a_workflow_without_stages_runs_as_one_stage_called_all(world):
    wf = _authored(world, ["claim-check"])
    cat = wa.load_catalog()
    assert runner.next_stage(wf, cat) == "all"
    out = runner.run_stage("zz-test", wf["id"], "next", mode="dry-run", db=world["db"], wf=wf, save=False)
    assert out["stage"] == "all" and out["ok"]
    assert runner.next_stage(wf, cat) is None


def test_claim_check_blocks_money_promises_and_passes_clean_copy(world):
    import edit
    wf = _authored(world, ["claim-check"], {"brief": "Guaranteed returns of 20% per month, risk-free!"})
    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    status = {r["kind"]: r["status"] for r in out["results"]}
    assert status["brief"] == "provided"
    r = next(r for r in out["results"] if r["kind"] == "claim-check")
    assert not out["ok"] and r["status"] == "blocked" and "guarantee" in r["note"] and "risk-free" in r["note"]
    clean = edit.claim_check("Save a little every market day. Withdraw any time.", dry_run=False)
    assert clean["status"] == "completed" and clean["verdict"] == "pass" and clean["text"].startswith("Save")
    assert edit.claim_check("Guaranteed 10x", dry_run=True)["status"] == "dry-run"


def test_hooks_are_deterministic_and_counted(world):
    import edit
    a = edit.hooks("A savings app for small traders. More text.", count=12, seed=3, dry_run=False)
    b = edit.hooks("A savings app for small traders. More text.", count=12, seed=3, dry_run=False)
    assert a["hooks"] == b["hooks"] and len(a["hooks"]) == 12 and len(set(a["hooks"])) == 12
    assert all("savings app for small traders" in h.lower() for h in a["hooks"])
    assert edit.hooks("x", seed=1, dry_run=False)["hooks"] != edit.hooks("x", seed=2, dry_run=False)["hooks"]
    wf = _authored(world, ["hook-variants"])
    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    r = next(r for r in out["results"] if r["kind"] == "hooks")
    assert out["ok"] and r["status"] == "completed" and r["files"] and r["files"][0].endswith("hooks.txt")
    # the text a step makes feeds the next text port
    node = next(n for n in wf["nodes"] if n["kind"] == "hooks")
    assert len(runner._feeder_text(wf, {"id": "z"}, "text")) == 0
    assert node["data"]["results"][-1]["text"].count("\n") == 9


def test_transcribe_reads_a_sidecar_and_blocks_honestly_without_whisper(tmp_path, monkeypatch):
    import edit
    clip = tmp_path / "talk.mp4"
    clip.write_bytes(b"stub")
    assert edit.transcribe(clip, tmp_path / "t.txt", dry_run=True)["status"] == "dry-run"
    (tmp_path / "talk.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nHabari, karibu.\n\n2\n00:00:02,000 --> 00:00:04,000\nTuanze.\n", encoding="utf-8")
    r = edit.transcribe(clip, tmp_path / "t.txt", dry_run=False)
    assert r["status"] == "completed" and r["text"] == "Habari, karibu.\nTuanze." and (tmp_path / "t.txt").exists()
    (tmp_path / "talk.srt").unlink()
    import transcribe as voice
    monkeypatch.setattr(voice, "whisper_available", lambda: False)
    r = edit.transcribe(clip, tmp_path / "t2.txt", dry_run=False)
    assert r["status"] == "blocked" and "faster-whisper" in r["note"]


def test_compositor_needs_a_real_kit_and_derives_palette_roles(tmp_path):
    import edit
    root = tmp_path / "kit"
    root.mkdir()
    (root / "brand.yaml").write_text("palette:\n  measured: {charcoal: '#1A1512', ivory: '#F2EBE0', dust_gold: '#8A6B45'}\n"
                                     "logo: {master: logo.png, min_width_pct: 12}\n", encoding="utf-8")
    spec, problem = edit.brand_kit(root)
    assert "not on disk" in problem
    (root / "logo.png").write_bytes(b"\x89PNG")
    spec, problem = edit.brand_kit(root)
    assert problem == ""
    pal = spec["palette"]["measured"]
    assert pal["ground"] == "#1A1512" and pal["surface"] == "#F2EBE0" and pal["accent"] == "#8A6B45"
    assert spec["_palette_roles_derived"]["ground"] == "charcoal"
    (root / "brand.yaml").write_text("palette:\n  measured: {ground: '#000000', surface: '#ffffff', accent: '#ff0000', hairline: '#222222'}\n"
                                     "logo: {master: logo.png, min_width_pct: 0}\n", encoding="utf-8")
    assert "no mark to place" in edit.brand_kit(root)[1]
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    dry = edit.composite_batch([img, img], ["0", "1"], root, "Headline\nSub", "4:5", tmp_path / "out", "c", dry_run=True)
    assert dry["status"] == "dry-run" and dry["expected"] == {"files": 2, "groups": ["0", "1"]} and "blocked until fixed" in dry["note"]
    assert edit.composite_batch([img], [None], root, "", "4:5", tmp_path / "out", "c", dry_run=False)["status"] == "blocked"
    assert edit.copy_block("Big line\nsmall line\nTap to save", spec) == {"headline": "Big line", "subhead": "small line", "cta": "Tap to save",
                                                                          "attribution": "", "disclosure": ""}


def _result(out, kind):
    return next(r for r in out["results"] if r["kind"] == kind)


def _manifest_of(world, wf, kind):
    node = next(n for n in wf["nodes"] if n["kind"] == kind)
    run = node["data"]["results"][-1]
    d = runner.run_dir("zz-test", wf["id"], node["id"], run["run_id"])
    return run, d, json.loads((d / "manifest.json").read_text(encoding="utf-8"))


def test_motion_graphics_dry_run_writes_the_frame_plan_and_no_video(world):
    wf = _authored(world, ["motion-graphics"], {"brief": "Pay in 3 taps\nNo queue. No paperwork.\nAmina, Nairobi"})
    node = next(n for n in wf["nodes"] if n["kind"] == "motion-graphics")
    node["data"]["params"] = {"aspect": "16:9", "duration": 3, "style": "subhead"}
    out = runner.run_stage("zz-test", wf["id"], "all", mode="dry-run", db=world["db"], wf=wf, save=False)
    r = _result(out, "motion-graphics")
    assert out["ok"] and r["status"] == "dry-run" and r["files"] == [] and "would render 72 frames" in r["note"]
    run, d, manifest = _manifest_of(world, wf, "motion-graphics")
    plan = Path(run["plan"])
    assert plan.exists() and plan.name == "motion.mp4.plan.json" and not (d / "motion.mp4").exists()
    p = json.loads(plan.read_text(encoding="utf-8"))
    assert (p["width"], p["height"], p["frame_count"]) == (1920, 1080, 72)
    assert [l["text"] for l in p["lines"]] == ["Pay in 3 taps", "No queue. No paperwork.", "Amina, Nairobi"]
    assert all(l["style"] == "subhead" for l in p["lines"]) and manifest["spec"]["client"] == "zz-test"
    # the same brief plans the same frames: the plan is the deterministic test surface
    again = runner.run_stage("zz-test", wf["id"], "all", mode="dry-run", db=world["db"], wf=wf, save=False)
    run2, _, _ = _manifest_of(world, wf, "motion-graphics")
    assert again["ok"] and json.loads(Path(run2["plan"]).read_text(encoding="utf-8"))["frames"] == p["frames"]


def test_motion_graphics_live_renders_through_the_module_and_reports_ffmpeg_honestly(world, monkeypatch):
    sys.path.insert(0, str(REPO / "packages" / "video"))
    import motion_graphics as mg
    wf = _authored(world, ["motion-graphics"], {"brief": "One line"})
    monkeypatch.setattr(mg, "ffmpeg_path", lambda: None)
    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    r = _result(out, "motion-graphics")
    assert not out["ok"] and r["status"] == "error" and "ffmpeg" in r["note"]

    def fake_render(spec, out_path, dry_run=False):
        assert not dry_run and spec["lines"][0]["text"] == "One line"
        p = mg.plan(spec, out_path)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"mp4 stub")
        return {**p, "status": "completed", "file": Path(out_path).as_posix(), "plan_path": "x.plan.json", "note": "rendered"}

    monkeypatch.setattr(mg, "render", fake_render)
    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    r = _result(out, "motion-graphics")
    assert r["status"] == "completed" and len(r["files"]) == 1 and r["files"][0].endswith("motion.mp4")
    assert _result(out, "export")["status"] == "completed", "the clip feeds the export step like any other video"


def test_translate_dry_run_writes_the_request_and_live_blocks_without_the_key(world, monkeypatch):
    sys.path.insert(0, str(REPO / "packages" / "voice"))
    import translate as tr
    wf = _authored(world, ["translate"], {"brief": "Save KES 200 every market day with Ongea Pesa."})
    node = next(n for n in wf["nodes"] if n["kind"] == "translate")
    node["data"]["params"] = {"source": "en", "language": "sw"}
    out = runner.run_stage("zz-test", wf["id"], "all", mode="dry-run", db=world["db"], wf=wf, save=False)
    r = _result(out, "translate")
    assert out["ok"] and r["status"] == "dry-run" and r["files"] == [] and "nothing sent" in r["note"]
    run, d, _ = _manifest_of(world, wf, "translate")
    req = json.loads((world["tmp"] / run["request"]).read_text(encoding="utf-8"))
    assert req["model"] == tr.DEFAULT_MODEL and "KES 200" in json.dumps(req) and not (d / "translated.sw.txt").exists()

    monkeypatch.setattr(tr, "_secret", lambda name: None)
    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    r = _result(out, "translate")
    assert not out["ok"] and r["status"] == "blocked" and "OPENROUTER_API_KEY" in r["note"] and "set_secret.py" in r["note"]

    monkeypatch.setattr(tr, "_secret", lambda name: "k")
    sent = {}

    def fake_translate(src_path, out_path, src, dst, glossary_path=None, **kw):
        sent.update(src=src, dst=dst, dry=kw.get("dry_run"), text=Path(src_path).read_text(encoding="utf-8"))
        Path(out_path).write_text("Weka KES 200 kila siku ya soko na Ongea Pesa.\n", encoding="utf-8")
        return {"status": "completed", "format": "text", "units": 1, "file": Path(out_path).as_posix(),
                "glossary": {}, "problems": [], "model": tr.DEFAULT_MODEL, "elapsed_s": 0.1, "note": "1 unit(s) en->sw"}

    monkeypatch.setattr(tr, "translate_file", fake_translate)
    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    r = _result(out, "translate")
    assert out["ok"] and r["status"] == "completed" and r["files"][0].endswith("translated.sw.txt")
    assert sent["src"] == "en" and sent["dst"] == "sw" and sent["dry"] is False and "Ongea Pesa" in sent["text"]
    assert node["data"]["results"][-1]["text"].startswith("Weka KES 200"), "the translation feeds the next text port"


def _persona(world, with_meta=True):
    folder = world["tmp"] / "brands" / "zz-test" / "references" / "persona"
    folder.mkdir(parents=True)
    for i in range(4):
        (folder / f"p{i}.png").write_bytes(b"\x89PNG stub")
    if with_meta:
        (folder / "collection.json").write_text(json.dumps({"name": "persona", "use": "data", "rights": "owned",
                                                             "consent": False, "fictional": True}), encoding="utf-8")
    wf = _authored(world, ["reference-images", "lora"])
    for n in wf["nodes"]:
        if n["kind"] == "reference-images":
            n["data"]["params"]["folder"] = "brands/zz-test/references/persona"
        if n["kind"] == "lora-train":
            n["data"]["params"] = {"trigger": "prsna", "base": "klein-9b", "steps": 1000, "rank": 16}
    return wf


def test_lora_train_dry_run_plans_the_job_and_live_blocks_instead_of_training(world):
    wf = _persona(world)
    out = runner.run_stage("zz-test", wf["id"], "all", mode="dry-run", db=world["db"], wf=wf, save=False)
    r = _result(out, "lora-train")
    assert out["ok"] and r["status"] == "dry-run" and r["files"] == [] and "nothing trained" in r["note"]
    run, d, manifest = _manifest_of(world, wf, "lora-train")
    assert (d / "config.yaml").exists() and (d / "launch.sh").exists() and not (d / "dataset").exists()
    cfg = (d / "config.yaml").read_text(encoding="utf-8")
    assert "prsna" in cfg and "flux2" in cfg and "steps: 1000" in cfg
    assert manifest["images"] == 4 and manifest["base"]["id"] == "klein-9b" and manifest["rights"]["fictional"] is True
    assert any("ai-toolkit" in s for s in manifest["needs_setup"]) and any("item 3" in s for s in manifest["needs_setup"])
    assert manifest["command"].startswith("bash ") and manifest["command"].endswith("launch.sh")

    out = runner.run_stage("zz-test", wf["id"], "all", mode="auto", approve_as="human", db=world["db"], wf=wf, save=False)
    r = _result(out, "lora-train")
    assert not out["ok"] and r["status"] == "blocked" and "docs/BLOCKERS.md item 3" in r["note"] and "never runs" in r["note"]
    run, d, manifest = _manifest_of(world, wf, "lora-train")
    assert manifest["reason"] == "training" and (d / "dataset" / "p0.txt").read_text(encoding="utf-8").startswith("prsna")
    assert {Path(f).name for f in r["files"]} == {"config.yaml", "launch.sh", "manifest.json"}
    assert runner.next_stage(wf, wa.load_catalog()) == "all", "blocked is not finished"


def test_lora_train_refuses_a_folder_without_rights(world):
    wf = _persona(world, with_meta=False)
    out = runner.run_stage("zz-test", wf["id"], "all", mode="dry-run", db=world["db"], wf=wf, save=False)
    r = _result(out, "lora-train")
    assert not out["ok"] and r["status"] == "blocked" and "rights are 'unclear'" in r["note"]
    _, _, manifest = _manifest_of(world, wf, "lora-train")
    assert manifest["reason"] == "rights"
    # an images folder outside the client's references is never a training set
    for n in wf["nodes"]:
        if n["kind"] == "reference-images":
            n["data"]["params"]["folder"] = "brands/other/references/persona"
            n["data"]["results"] = []
    (world["tmp"] / "brands" / "other" / "references" / "persona").mkdir(parents=True)
    (world["tmp"] / "brands" / "other" / "references" / "persona" / "a.png").write_bytes(b"x")
    out = runner.run_stage("zz-test", wf["id"], "all", mode="dry-run", db=world["db"], wf=wf, save=False)
    r = _result(out, "lora-train")
    assert r["status"] == "blocked" and "not a reference collection of zz-test" in r["note"]


def test_a_comfy_kind_without_a_port_map_is_blocked_not_a_crash(world, monkeypatch):
    import ports
    monkeypatch.setattr(ports, "load_port_map", lambda rel: (_ for _ in ()).throw(ports.PortMapError(f"no port map for {rel}")))
    out = runner.run_stage(world["client"], world["wf"]["id"], "refs", mode="dry-run", db=world["db"], comfy_factory=FakeComfy)
    sheet = next(r for r in out["results"] if r["kind"] == "character-sheet")
    assert sheet["status"] == "blocked" and "no usable port map" in sheet["note"]


def test_a_rights_gate_on_the_director_workflow_reads_the_attached_ref(world):
    # the director attaches each collection's rights to its input node; no collection.json is needed for a dry run
    out = runner.run_stage(world["client"], world["wf"]["id"], "scene1", mode="dry-run", db=world["db"], comfy_factory=FakeComfy)
    gens = [r for r in out["results"] if r["kind"] == "h3-reference-image"]
    assert gens and all(r["status"] == "dry-run" for r in gens)
    lead = next(n for n in world["wf"]["nodes"] if n["kind"] == "reference-images" and "avatar-lead" in n["id"])
    lead["data"]["ref"]["rights"] = "unclear"
    out = runner.run_stage(world["client"], world["wf"]["id"], "scene1", mode="dry-run", db=world["db"], comfy_factory=FakeComfy, wf=world["wf"], save=False)
    gens = [r for r in out["results"] if r["kind"] == "h3-reference-image"]
    assert all(r["status"] == "blocked" and "rights gate" in r["note"] for r in gens)
