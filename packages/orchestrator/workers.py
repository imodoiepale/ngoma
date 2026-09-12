"""Worker runtimes — how a task actually gets done.

The control plane decides what may happen. This decides how, and it is the only place that
knows a runtime exists. Adding a runtime means one class and one registry entry; nothing
in `control.py` changes.

Installed and usable today:

    claude-code   `claude -p` headless      implement, analyse, report
    codex-cli     `codex exec`              review, verify, second opinion
    local         a python entrypoint       the repo's own CLIs, no LLM at all
    hermes        HTTP gateway :8642        NousResearch/hermes-agent, when installed

`local` is not a placeholder. Most tasks in this studio are deterministic — rebuild the
graph, harvest a channel, composite an image, run the plan — and routing those through an
LLM would be slower, costlier and less reliable than calling the script. A worker runtime
should be the exception, not the default.

The cross-review flow the architecture called for, expressed in tasks rather than in a
framework:

    claude implements  ->  codex reviews  ->  verifier checks a clean tree  ->  human approves

Nothing here calls a model without an explicit `--live`. A dry run prints the exact command
that would be executed, which is also how you debug a prompt without paying for it.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Protocol

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Rough per-task cost used for budget admission. Real spend is reported back after the run
# where the runtime tells us; where it does not, the estimate stands and is marked as such.
COST_HINTS = {"claude-code": 0.15, "codex-cli": 0.12, "local": 0.0, "hermes": 0.10}

TIMEOUT_S = 1800


class WorkerError(RuntimeError):
    pass


@dataclass
class Outcome:
    ok: bool
    runtime: str
    command: str
    stdout: str = ""
    stderr: str = ""
    elapsed_s: float = 0.0
    cost_usd: float = 0.0
    cost_is_estimate: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["stdout"] = self.stdout[-4000:]
        d["stderr"] = self.stderr[-2000:]
        return d


class Runtime(Protocol):
    name: str

    def available(self) -> tuple[bool, str]: ...
    def build(self, task: dict[str, Any]) -> list[str]: ...
    def run(self, task: dict[str, Any], live: bool) -> Outcome: ...


class _Base:
    name = "base"
    binary = ""

    def available(self) -> tuple[bool, str]:
        p = shutil.which(self.binary)
        return (p is not None, p or f"{self.binary} not on PATH")

    def _exec(self, cmd: list[str], live: bool, cwd: Path | None = None) -> Outcome:
        printable = " ".join(shlex.quote(c) for c in cmd)
        if not live:
            return Outcome(ok=True, runtime=self.name, command=printable,
                           note="dry run — nothing executed",
                           cost_usd=COST_HINTS.get(self.name, 0.0))
        ok_bin, where = self.available()
        if not ok_bin:
            return Outcome(ok=False, runtime=self.name, command=printable,
                           stderr=where, note=f"{self.binary} is not installed")
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=str(cwd or REPO), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=TIMEOUT_S,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            return Outcome(ok=False, runtime=self.name, command=printable,
                           elapsed_s=round(time.time() - t0, 1),
                           note=f"timed out after {TIMEOUT_S}s")
        return Outcome(ok=r.returncode == 0, runtime=self.name, command=printable,
                       stdout=r.stdout or "", stderr=r.stderr or "",
                       elapsed_s=round(time.time() - t0, 1),
                       cost_usd=COST_HINTS.get(self.name, 0.0))


class ClaudeCode(_Base):
    name, binary = "claude-code", "claude"

    def build(self, task: dict[str, Any]) -> list[str]:
        return ["claude", "-p", _prompt(task)]

    def run(self, task: dict[str, Any], live: bool) -> Outcome:
        return self._exec(self.build(task), live)


class CodexCLI(_Base):
    name, binary = "codex-cli", "codex"

    def build(self, task: dict[str, Any]) -> list[str]:
        # `codex exec review` is purpose-built for the review half of the flow.
        if task.get("kind") in ("review", "verify"):
            return ["codex", "exec", "review"]
        return ["codex", "exec", _prompt(task)]

    def run(self, task: dict[str, Any], live: bool) -> Outcome:
        return self._exec(self.build(task), live)


class Local(_Base):
    """Runs the repo's own CLIs. No model, no cost, no nondeterminism."""
    name, binary = "local", "uv"

    # Allowlisted, because a task spec is data and data must not choose what executes.
    ENTRYPOINTS = {
        "graph_rebuild": ["uv", "run", "--quiet", "packages/library/graph_build.py"],
        "plan": ["uv", "run", "--quiet", "--with", "pyyaml",
                 "packages/strategy/plan.py"],
        "analyse": ["uv", "run", "--quiet", "packages/analytics/learn.py"],
        "harvest": ["uv", "run", "--quiet", "--with", "pyyaml",
                    "packages/ingest/yt_learn.py"],
        "validate": ["uv", "run", "--quiet", "packages/comfy-client/client.py",
                     "validate", "--all"],
        "test": ["uv", "run", "--quiet", "python", "studio.py", "test"],
        "report": ["uv", "run", "--quiet", "python", "studio.py", "doctor"],
    }

    def build(self, task: dict[str, Any]) -> list[str]:
        kind = task.get("kind", "")
        if kind not in self.ENTRYPOINTS:
            raise WorkerError(
                f"no local entrypoint for task kind {kind!r}. Local workers run an "
                f"allowlist, never a command from the task spec — a spec is data, and data "
                f"must not choose what executes. Known: {sorted(self.ENTRYPOINTS)}")
        return self.ENTRYPOINTS[kind] + list(task.get("spec", {}).get("args", []))

    def run(self, task: dict[str, Any], live: bool) -> Outcome:
        o = self._exec(self.build(task), live)
        o.cost_usd, o.cost_is_estimate = 0.0, False
        return o


class HermesGateway(_Base):
    """NousResearch/hermes-agent over its OpenAI-compatible gateway.

    Unlike the other runtimes this is not a subprocess: `hermes gateway` is a long-running
    HTTP server on 127.0.0.1:8642, so a task is one chat completion. Hermes supplies its
    own skills (from ~/.hermes/skills/, which studio.py skills-sync populates), its own
    memory, and its own tools.
    """
    name, binary = "hermes", "hermes"

    def available(self) -> tuple[bool, str]:
        from hermes import gateway_up, gateway_url, installed  # noqa: PLC0415
        up, why = gateway_up()
        if up:
            return True, f"{gateway_url()} ({why})"
        ok, where = installed()
        return False, (f"gateway down at {gateway_url()}: {why}"
                       if ok else "hermes not installed; see packages/orchestrator/hermes.py check")

    def build(self, task: dict[str, Any]) -> list[str]:
        # There is no command line; this exists so `runtimes` can show something useful.
        from hermes import gateway_url  # noqa: PLC0415
        return ["POST", f"{gateway_url()}/v1/chat/completions", "<prompt>"]

    def run(self, task: dict[str, Any], live: bool) -> Outcome:
        from hermes import HermesError, ask, gateway_url  # noqa: PLC0415
        printable = f"POST {gateway_url()}/v1/chat/completions"
        if not live:
            return Outcome(ok=True, runtime=self.name, command=printable,
                           note="dry run — nothing sent",
                           cost_usd=COST_HINTS.get(self.name, 0.0))
        ok, why = self.available()
        if not ok:
            return Outcome(ok=False, runtime=self.name, command=printable,
                           stderr=why, note="gateway unavailable")
        t0 = time.time()
        try:
            reply = ask(_prompt(task))
        except HermesError as e:
            return Outcome(ok=False, runtime=self.name, command=printable,
                           stderr=str(e), elapsed_s=round(time.time() - t0, 1))
        return Outcome(ok=bool(reply), runtime=self.name, command=printable,
                       stdout=reply, elapsed_s=round(time.time() - t0, 1),
                       cost_usd=COST_HINTS.get(self.name, 0.0),
                       note="cost depends on the provider Hermes is configured with "
                            "(OpenRouter, Kimi, local); the figure here is a placeholder")


REGISTRY: dict[str, Runtime] = {
    r.name: r for r in (ClaudeCode(), CodexCLI(), Local(), HermesGateway())  # type: ignore[misc]
}


def _prompt(task: dict[str, Any]) -> str:
    spec = task.get("spec") or {}
    lines = [
        f"Task: {task.get('title', 'untitled')}",
        f"Kind: {task.get('kind')}",
        f"Brand: {task.get('brand')}",
        "",
        "Repository: this content studio. Read shared-skills/approved/content-studio/SKILL.md",
        "before acting; it carries the standing rules and the known traps.",
        "",
        "Standing rules that apply to you:",
        "  - queued is not success; verify before claiming done",
        "  - unknown is not OK; report UNVERIFIED rather than guessing",
        "  - dry-run by default; never publish or spend without explicit instruction",
        "  - you may not approve your own work",
        "",
    ]
    if spec.get("instructions"):
        lines += ["Instructions:", str(spec["instructions"]), ""]
    if spec.get("context"):
        lines += ["Context:", json.dumps(spec["context"], indent=1)[:1500], ""]
    lines.append("Report what you did, what you verified, and what you could not verify.")
    return "\n".join(lines)


def dispatch(task_id: int, live: bool = False, db: Path | None = None) -> Outcome:
    """Take a task through the control plane's gates, run it, and report back."""
    from control import connect, finish, start, worker  # noqa: PLC0415

    con = connect(db) if db else connect()
    row = start(con, task_id)                 # raises unless approved, budgeted, assigned
    w = worker(con, row["assigned_to"])
    rt = REGISTRY.get(w["runtime"])
    if rt is None:
        finish(con, task_id, False, 0.0, {"error": f"unknown runtime {w['runtime']}"})
        raise WorkerError(f"worker {w['name']} declares runtime {w['runtime']!r}, which is "
                          f"not registered. Known: {sorted(REGISTRY)}")

    task = {"kind": row["kind"], "title": row["title"], "brand": row["brand"],
            "spec": json.loads(row["spec"] or "{}")}

    # LOCAL-FIRST. The docstring says a worker runtime should be the exception; this is
    # where that is true rather than merely stated. If the task kind has a deterministic
    # entrypoint, run it — routing `graph_rebuild` through an LLM is slower, costlier and
    # less reliable than calling the script. `spec.force_runtime` overrides deliberately.
    forced = task["spec"].get("force_runtime")
    if forced:
        rt = REGISTRY.get(forced, rt)
    elif row["kind"] in Local.ENTRYPOINTS and w["runtime"] != "local":
        rt = REGISTRY["local"]
    try:
        out = rt.run(task, live)
    except WorkerError as e:
        finish(con, task_id, False, 0.0, {"error": str(e)})
        raise
    if rt.name != w["runtime"] and not forced:
        out.note = (f"routed to `{rt.name}` instead of the worker's `{w['runtime']}`: "
                    f"`{row['kind']}` has a deterministic entrypoint, so no model was "
                    f"needed. Set spec.force_runtime to override."
                    + (f" {out.note}" if out.note else ""))
    finish(con, task_id, out.ok, out.cost_usd if live else 0.0, out.to_dict())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Run a control-plane task on a worker runtime.")
    ap.add_argument("command", choices=["runtimes", "dispatch", "flow"])
    ap.add_argument("--id", type=int)
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--title", default="")
    ap.add_argument("--live", action="store_true", help="actually invoke the runtime")
    a = ap.parse_args()

    if a.command == "runtimes":
        for name, rt in REGISTRY.items():
            ok, where = rt.available()
            print(f"{name:<14} {'READY' if ok else 'MISSING':<9} "
                  f"~${COST_HINTS.get(name, 0):.2f}/task   {where}")
        return

    if a.command == "dispatch":
        if not a.id:
            raise SystemExit("--id is required")
        out = dispatch(a.id, a.live)
        print(json.dumps(out.to_dict(), indent=2)[:2000])
        if not a.live:
            print("\n(dry run — pass --live to actually invoke the runtime)")
        return

    if a.command == "flow":
        # The cross-review flow, created as real gated tasks rather than described.
        from control import Task, connect, propose, queue  # noqa: PLC0415
        con = connect()
        title = a.title or "untitled change"
        ids = []
        for kind, who, what in (
            ("generate_draft", "claude", f"implement: {title}"),
            ("review", "codex", f"review the implementation of: {title}"),
            ("verify", "verifier", f"independently verify a clean tree for: {title}"),
        ):
            if kind == "review" or kind == "verify":
                # review/verify are not in the control plane's task vocabulary by design:
                # they are analysis, so they map onto `analyse`.
                kind = "analyse"
            ids.append(propose(con, Task(brand=a.brand, kind=kind, title=what,
                                         assigned_to=who, estimate_usd=0.15,
                                         spec={"instructions": what},
                                         created_by="orchestrator")))
        print(f"created tasks {ids} — implement, review, verify")
        print("Each runs on a different worker, so no runtime reviews its own output.")
        for r in queue(con, a.brand, "ready"):
            print(f"  [{r['id']}] {r['assigned_to']:<10} {r['title']}")
        return


if __name__ == "__main__":
    from control import ControlError  # noqa: E402

    try:
        main()
    except (WorkerError, ControlError) as e:
        # A gate refusing a task is the system working, not failing. Say so in one line.
        raise SystemExit(f"refused: {e}")
