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
