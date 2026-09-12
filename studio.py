#!/usr/bin/env python
"""Task runner for the studio.

`make` is not installed on this machine, so this is the entry point rather than a
Makefile. Run with `uv run studio.py <task>`.

    check          fail if anything secret-shaped is tracked by git
    skills-sync    mirror shared-skills/approved into every runtime's skills dir
    graph          rebuild the corpus knowledge graph
    plan           plan every calendar item across backends (costs nothing)
    doctor         what is installed, reachable and blocked, right now
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

SECRET_PATTERNS = r"apik_[A-Za-z0-9]{8}|rpa_[A-Z0-9]{20}|BEGIN OPENSSH PRIVATE|BEGIN RSA PRIVATE"
# Docs and the skill describe these shapes on purpose; they hold no real values.
SECRET_EXCLUDES = [":(exclude)docs/*", ":(exclude)shared-skills/*", ":(exclude).claude/*"]

SKILL_TARGETS = [".claude/skills", ".agents/skills"]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO, text=True, encoding="utf-8",
                          errors="replace", env=ENV, **kw)


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
    return _run(["uv", "run", "--quiet", "packages/library/graph_build.py"]).returncode


def plan() -> int:
    return _run(["uv", "run", "--quiet", "--with", "pyyaml",
                 "packages/image-router/router.py", "--plan-all"]).returncode


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
        print("  graph            NOT BUILT — run: uv run studio.py graph")
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
        for b in ("local", "serverless"):
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
         "plan": plan, "doctor": doctor}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        print(__doc__)
        print("tasks:", ", ".join(TASKS))
        raise SystemExit(2)
    raise SystemExit(TASKS[sys.argv[1]]())


if __name__ == "__main__":
    main()
