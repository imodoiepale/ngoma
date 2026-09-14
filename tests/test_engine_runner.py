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
    outcome = "COMPLETED"

    def __init__(self, backend="pod"):
        self.backend, self.base_url = backend, "http://fake"

    def submit(self, graph, workflow_name=None, dry_run=True):
        FakeComfy.calls.append({"dry_run": dry_run, "name": workflow_name})
        assert not dry_run
        return {"prompt_id": f"p{len(FakeComfy.calls)}"}

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
    monkeypatch.setattr(runner, "_fetch", lambda c, o, dest: (f"brands/zz-test/runs/x/{o['filename']}", "0" * 64))
    FakeComfy.calls, FakeComfy.outcome = [], "COMPLETED"
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
    assert "refs.refmod-create" in gens[0]["note"]


def test_approved_stages_within_budget_run_and_complete(world, monkeypatch):
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)
    refs = _run(world, "refs", mode="stage-approval", approve_as="human")
    assert refs["ok"] and {r["kind"]: r["status"] for r in refs["results"]}["refmod-create"] == "completed"
    out = _run(world, "scene1", mode="stage-approval", approve_as="human")
    gens = [r for r in out["results"] if r["kind"] == "h3-reference-image"]
    assert len(gens) == 3 and all(r["status"] == "completed" for r in gens)
    assert len(FakeComfy.calls) == 2 + 3 and out["pending_picks"]


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
    assert out["ok"] and len(FakeComfy.calls) == 5
    # the motion stage hangs off the pick, which nobody has made: it waits rather than runs
    out = _run(world, "scene1-motion", mode="auto")
    assert out["waiting_on_pick"] and len(FakeComfy.calls) == 5


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
