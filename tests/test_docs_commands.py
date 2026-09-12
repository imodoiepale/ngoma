"""Every command the docs tell a person to run must actually run.

This exists because a green suite once coexisted with a roadmap that sent the reader to
`set_secret.py --name ...` and `run_workflow.py --template ...` — neither flag existed.
The unit tests all passed; the instructions a human would follow were broken. A check
that never touches the path a person actually takes proves nothing.

For each documented `packages/...py`, `infra/...py` or `studio.py` invocation this asserts:
the script exists, `--help` works, every `--flag` used is one the script accepts, and a
subcommand word right after the script is one of its declared choices.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCS = [
    "README.md", "docs/ROADMAP.md", "docs/SETUP.md", "docs/WHAT-THIS-DOES.md",
    "docs/BLOCKERS.md", "shared-skills/approved/content-studio/SKILL.md",
    "infra/postiz/README.md", "infra/openwa/README.md", "infra/hermes/README.md",
    "infra/memory/README.md",
]
SCRIPT_RE = re.compile(r"((?:packages|infra|tests)/[\w\-/.]+\.py|\bstudio\.py)")
# Scripts whose --help cannot run here for a reason unrelated to the docs being right.
HELP_EXEMPT = {"packages/publish/whop/whop_upload.py"}


@lru_cache(maxsize=None)
def help_text(script: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, script, "--help"], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def documented_commands() -> list[tuple[str, str, str]]:
    found: dict[tuple[str, str], str] = {}
    for rel in DOCS:
        p = REPO / rel
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = SCRIPT_RE.search(line)
            if not m:
                continue
            tail = re.split(r"[`|#]|\s{3,}|\(", line[m.end():])[0].strip()
            found.setdefault((m.group(1), tail), rel)
    return [(script, tail, rel) for (script, tail), rel in sorted(found.items())]


COMMANDS = documented_commands()


def test_docs_cite_at_least_the_core_commands():
    scripts = {s for s, _, _ in COMMANDS}
    for must in ("studio.py", "infra/runpod/set_secret.py",
                 "packages/comfy-client/client.py", "packages/publish/postiz.py"):
        assert must in scripts, f"docs no longer mention {must}; the parser may be broken"


@pytest.mark.parametrize("script,tail,doc", COMMANDS,
                         ids=[f"{d}:{s} {t}"[:90] for s, t, d in COMMANDS])
def test_documented_command_resolves(script, tail, doc):
    assert (REPO / script).exists(), f"{doc} cites {script}, which does not exist"
    if script in HELP_EXEMPT:
        return
    code, text = help_text(script)
    assert "usage" in text.lower(), f"{script} --help did not print usage (exit {code}):\n{text[-400:]}"

    try:
        toks = shlex.split(tail)
    except ValueError:
        toks = tail.split()

    for t in toks:
        if t.startswith("--"):
            flag = t.split("=")[0]
            assert flag in text, f"{doc}: `{script} {tail}` uses {flag}, which {script} does not accept"

    # A subcommand is the first bare word, provided it does not follow a flag.
    choices: set[str] = set()
    for group in re.findall(r"\{([^}]+)\}", text):
        choices.update(x.strip() for x in re.split(r"[,|]", group))
    if toks and choices and not toks[0].startswith("-"):
        word = toks[0]
        if re.fullmatch(r"[a-z][a-z\-]+", word):
            assert word in choices, (f"{doc}: `{script} {tail}` uses subcommand {word!r}; "
                                     f"{script} accepts {sorted(choices)}")
