#!/usr/bin/env python
"""Task runner for the studio.

`make` is not installed on this machine, so this is the entry point rather than a
Makefile. Run with `python studio.py <task>`.

    check          fail if anything secret-shaped is tracked by git
    skills-sync    mirror shared-skills/approved into every runtime's skills dir
    graph          rebuild the corpus knowledge graph
    plan           plan every calendar item across backends (costs nothing)
    test           run the end-to-end suite (no key, no GPU, no network)
    loop           full pipeline on fixture data: plan -> analytics -> memory -> curator
    doctor         what is installed, reachable and blocked, right now

graph, plan, test and loop run Python scripts. When `uv` is on PATH they go through
`uv run --with <dep> ...`, which resolves pyyaml/pytest/pillow without a global install.
When it is not, they run with the interpreter executing this file (`sys.executable`), so
`python -m pip install pyyaml pillow pytest` once and `python studio.py test` works.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

# Assembled from fragments so this file does not match its own scan. Writing the
# literal here made `check` fail on itself — a false positive teaches people to ignore
# the check, which is worse than not having one.
SECRET_PATTERNS = "|".join([
    "apik" + r"_[A-Za-z0-9]{8}",
    "rpa" + r"_[A-Z0-9]{20}",
    "BEGIN OPENSSH PRIV" + "ATE",
    "BEGIN RSA PRIV" + "ATE",
])
# Docs and the skill describe these shapes on purpose; they hold no real values.
SECRET_EXCLUDES = [":(exclude)docs/*", ":(exclude)shared-skills/*",
                   ":(exclude).claude/*", ":(exclude).agents/*", ":(exclude)studio.py"]

SKILL_TARGETS = [".claude/skills", ".agents/skills"]
_NOTICED: list[bool] = []  # the uv fallback notice prints once per invocation, not per step


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO, text=True, encoding="utf-8",
                          errors="replace", env=ENV, **kw)


def _python(*args: str, with_: tuple[str, ...] = ()) -> list[str]:
    """The command that runs a Python script or module here.

    `uv` when it is on PATH: `uv run --quiet [--with dep]... <args>`, with `python` inserted
    before a `-m module` so the module runs in the resolved environment. Otherwise the
    interpreter running this file, which must already have the deps installed (BLOCKERS 17).
    """
    if shutil.which("uv"):
        cmd = ["uv", "run", "--quiet"]
        for dep in with_:
            cmd += ["--with", dep]
        if args and args[0].startswith("-"):
            cmd.append("python")
        return cmd + list(args)
    if not _NOTICED:
        _NOTICED.append(True)
        # stdout on purpose: PowerShell 5 turns native stderr under `2>&1` into red error records.
        print(f"uv not on PATH; running with {sys.executable} (deps must be installed: "
              f"{', '.join(with_) or 'none needed'})", flush=True)
    return [sys.executable, *args]


def check() -> int:
    r = _run(["git", "grep", "-InE", SECRET_PATTERNS, "--", ".", *SECRET_EXCLUDES],
             capture_output=True)
    if r.stdout.strip():
        print("SECRET-SHAPED CONTENT IS TRACKED:\n")
        print(r.stdout[:2000])
        return 1
    print("no secrets tracked")

    untracked = _run(["git", "status", "--porcelain", "--ignored"], capture_output=True).stdout
    risky = [l[3:] for l in untracked.splitlines()
             if any(k in l.lower() for k in ("ed25519", ".env", ".dpapi", "id_rsa"))]
    if risky:
        print(f"\n{len(risky)} secret-shaped file(s) present but correctly ignored:")
        for p in risky[:10]:
            print(f"  {p}")
    return 0


def skills_sync() -> int:
    src = REPO / "shared-skills" / "approved"
    if not src.exists():
        print("no approved skills")
        return 1
    n = 0
    for target in SKILL_TARGETS:
        dst = REPO / target
        dst.mkdir(parents=True, exist_ok=True)
        for skill in src.iterdir():
            if skill.is_dir():
                shutil.copytree(skill, dst / skill.name, dirs_exist_ok=True)
                n += 1
    print(f"mirrored {n // len(SKILL_TARGETS)} skill(s) to {', '.join(SKILL_TARGETS)}")
    return 0


def graph() -> int:
    return _run(_python("packages/library/graph_build.py")).returncode


def plan() -> int:
    return _run(_python("packages/image-router/router.py", "--plan-all", with_=("pyyaml",))).returncode


def test() -> int:
    return _run(_python("-m", "pytest", "tests/", "-q", with_=("pytest", "pillow", "pyyaml"))).returncode


def loop() -> int:
    """Exercise the whole learning loop on fixture data, end to end."""
    brand = "ongea-pesa"
    plan_md = REPO / "brands" / brand / "calendar" / "plan-loop.md"
    data = REPO / "out" / "analytics" / f"{brand}-loop.jsonl"
    steps = [
        ("plan 180 days", _python("packages/strategy/plan.py", "--brand", brand,
                                  "--days", "180", "--start", "2026-03-01",
                                  "--out", str(plan_md), with_=("pyyaml",))),
        ("collect fixture analytics", _python("packages/analytics/collect.py", "fixture",
                                              "--brand", brand, "--plan",
                                              str(plan_md.with_suffix(".json")),
                                              "--out", str(data))),
        ("derive learnings -> memory", _python("packages/analytics/learn.py", "--brand", brand,
                                               "--data", str(data), "--metric", "saves",
                                               "--audience", "kenyan professionals", "--write")),
        ("what memory believes", _python("packages/memory/store.py", "believed", "--brand", brand)),
        ("curator verdict", _python("packages/strategy/skill_curator.py", "evaluate",
                                    "--subject", "kenyan_meme_original")),
    ]
    bar = "=" * 66
    for i, (label, cmd) in enumerate(steps, 1):
        print()
        print(bar)
        print(f"[{i}/{len(steps)}] {label}")
        print(bar)
        if _run(cmd).returncode != 0:
            print(f"FAILED at step {i}")
            return 1
    print()
    print("NOTE: analytics above are FIXTURE data, tagged source=fixture. "
          "The loop is real; the numbers are not.")
    return 0


def doctor() -> int:
    print("=== tools ===")
    for t in ("docker", "node", "uv", "ffmpeg", "yt-dlp", "agent-reach", "opencli",
              "gallery-dl", "codex", "git"):
        p = shutil.which(t)
        print(f"  {t:<12} {p or 'MISSING'}")

    print("\n=== secrets in environment ===")
    for k in ("OPENROUTER_API_KEY", "RUNPOD_API_KEY", "RUNPOD_ENDPOINT_ID", "COMFY_POD_URL"):
        print(f"  {k:<20} {'set' if os.environ.get(k) else 'not set'}")

    print("\n=== corpus ===")
    gj = REPO / "graph" / "graph.json"
    if gj.exists():
        d = json.loads(gj.read_text(encoding="utf-8"))
        print(f"  graph            {len(d['nodes'])} nodes, {len(d['edges'])} edges")
    else:
        print("  graph            NOT BUILT — run: python studio.py graph")
    mf = REPO / "workflows" / "manifest.json"
    if mf.exists():
        print(f"  workflows        {json.loads(mf.read_text(encoding='utf-8'))['count']}")
    facts = REPO / "packages/library/corpus/youtube/facts.jsonl"
    if facts.exists():
        print(f"  mined videos     {sum(1 for l in facts.read_text(encoding='utf-8').splitlines() if l.strip())}")

    print("\n=== comfy backends ===")
    sys.path.insert(0, str(REPO / "packages" / "comfy-client"))
    try:
        from client import ComfyClient  # noqa: PLC0415
        for b in ("local", "pod", "serverless"):
            try:
                c = ComfyClient(b)
                print(f"  {b:<12} {'reachable' if c.reachable() else 'not reachable'}  {c.base_url}")
            except Exception as e:  # noqa: BLE001
                print(f"  {b:<12} {e}")
    except ImportError as e:
        print(f"  could not import client: {e}")

    print("\n=== blockers ===")
    bl = REPO / "docs" / "BLOCKERS.md"
    if bl.exists():
        for line in bl.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                print(f"  {line[3:]}")
    return 0


TASKS = {"check": check, "skills-sync": skills_sync, "graph": graph,
         "plan": plan, "doctor": doctor, "test": test, "loop": loop}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        # BLOCKERS.md headings contain arrows; a cp1252 console crashed `doctor` mid-report.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("usage: studio.py {" + ",".join(TASKS) + "}")
        raise SystemExit(0)
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        print(__doc__)
        print("tasks:", ", ".join(TASKS))
        raise SystemExit(2)
    raise SystemExit(TASKS[sys.argv[1]]())


if __name__ == "__main__":
    main()
