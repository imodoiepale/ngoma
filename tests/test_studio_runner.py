"""`studio.py` tasks run with or without `uv` (BLOCKERS 17).

`plan`, `test`, `graph` and `loop` shell out to Python scripts. With `uv` on PATH they go
through `uv run --with ...`; without it they must use the interpreter running the task
runner, not a bare `python` that may resolve to something else. Nothing here executes a
subprocess: `_run` is replaced and the command lines are asserted.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def studio():
    spec = importlib.util.spec_from_file_location("studio_task_runner", REPO / "studio.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def calls(studio, monkeypatch):
    seen: list[list[str]] = []

    def fake_run(cmd, **kw):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(studio, "_run", fake_run)
    return seen


def _with_uv(monkeypatch, studio, present: bool):
    monkeypatch.setattr(studio.shutil, "which",
                        lambda name, *a, **k: (r"C:\tools\uv.exe" if present else None)
                        if name == "uv" else shutil.which(name, *a, **k))


def test_uv_is_preferred_when_on_path(studio, monkeypatch, calls):
    _with_uv(monkeypatch, studio, True)
    assert studio.plan() == 0 and studio.test() == 0 and studio.graph() == 0
    plan, test, graph = calls
    assert plan == ["uv", "run", "--quiet", "--with", "pyyaml", "packages/image-router/router.py", "--plan-all"]
    assert test[:3] == ["uv", "run", "--quiet"] and test[-6:] == ["--with", "pyyaml", "python", "-m", "pytest", "tests/", "-q"][-6:]
    assert "python" in test and test.index("python") < test.index("-m"), "a module runs inside uv's python"
    assert graph == ["uv", "run", "--quiet", "packages/library/graph_build.py"]


def test_sys_executable_when_uv_is_missing(studio, monkeypatch, calls):
    _with_uv(monkeypatch, studio, False)
    assert studio.plan() == 0 and studio.test() == 0 and studio.graph() == 0
    plan, test, graph = calls
    assert plan == [sys.executable, "packages/image-router/router.py", "--plan-all"]
    assert test == [sys.executable, "-m", "pytest", "tests/", "-q"]
    assert graph == [sys.executable, "packages/library/graph_build.py"]
    assert not any("uv" in c or "--with" in c for c in calls)


def test_loop_runs_every_step_through_the_same_helper(studio, monkeypatch, calls):
    _with_uv(monkeypatch, studio, False)
    assert studio.loop() == 0
    assert len(calls) == 5 and all(c[0] == sys.executable for c in calls)
    assert [c[1] for c in calls] == ["packages/strategy/plan.py", "packages/analytics/collect.py",
                                     "packages/analytics/learn.py", "packages/memory/store.py",
                                     "packages/strategy/skill_curator.py"]
    for c in calls:
        assert (REPO / c[1]).exists(), f"loop cites {c[1]}, which does not exist"
    calls.clear()
    _with_uv(monkeypatch, studio, True)
    assert studio.loop() == 0
    assert all(c[:3] == ["uv", "run", "--quiet"] for c in calls)
    assert calls[0][3:5] == ["--with", "pyyaml"], "plan.py needs pyyaml under uv"


def test_loop_stops_at_the_first_failing_step(studio, monkeypatch):
    _with_uv(monkeypatch, studio, False)
    seen: list[list[str]] = []

    def fake_run(cmd, **kw):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 1 if len(seen) == 2 else 0, "", "")

    monkeypatch.setattr(studio, "_run", fake_run)
    assert studio.loop() == 1 and len(seen) == 2


def test_help_documents_the_fallback(studio):
    assert "sys.executable" in studio.__doc__ and "uv run" in studio.__doc__
    assert "uv run studio.py" not in studio.__doc__
