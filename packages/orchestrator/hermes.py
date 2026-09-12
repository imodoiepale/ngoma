"""Hermes adapter — the fourth worker runtime.

Hermes is real: `NousResearch/hermes-agent`, MIT, Python + Node. Verified 2026-09-12
against the GitHub API and the repo's own docs rather than the considerable ring of SEO
pages that surround it.

What matters for this integration, all confirmed from primary sources:

  * config lives at `~/.hermes/config.yaml`, secrets at `~/.hermes/.env`
  * **skills live at `~/.hermes/skills/`**, one folder per skill containing `SKILL.md`,
    following the same agentskills.io standard as Claude Skills — so `studio.py
    skills-sync` already emits exactly the right shape
  * `hermes gateway` exposes an **OpenAI-compatible** HTTP API on `127.0.0.1:8642`,
    gated by `API_SERVER_ENABLED=true` and `API_SERVER_KEY`
  * MCP servers are configured under `mcp_servers:` with `command`/`args`, which is how
    the Graphiti memory server in `infra/memory/` attaches
  * exactly **one** external memory provider may be active at a time; the built-in
    `MEMORY.md`/`USER.md` memory is always on alongside it
  * it bundles `claude-code` and `codex` skills, so it can delegate coding work onward

Because the gateway speaks the OpenAI chat-completions shape, this adapter is thin: post a
prompt, read a reply. Hermes' own skills, memory and tools do the work on its side.

Not installed here. Every function degrades to a clear instruction rather than a stack
trace, and `hermes.py check` tells you exactly what is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
CONFIG = HERMES_HOME / "config.yaml"
ENVFILE = HERMES_HOME / ".env"
SKILLS = HERMES_HOME / "skills"
DEFAULT_GATEWAY = "http://127.0.0.1:8642"

INSTALL = {
    "linux/macos": "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash",
    "windows": 'iex (irm https://hermes-agent.nousresearch.com/install.ps1)',
    "note": ("PyPI's `hermes-agent` lags the npm release, so `pip install` is NOT "
             "equivalent. Use the official installer."),
}


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


class HermesError(RuntimeError):
    pass


def installed() -> tuple[bool, str]:
    p = shutil.which("hermes")
    return (p is not None, p or "hermes not on PATH")


def gateway_url() -> str:
    return os.environ.get("HERMES_GATEWAY_URL", DEFAULT_GATEWAY).rstrip("/")


def gateway_up() -> tuple[bool, str]:
    """A reachable port is not a working gateway — check it answers as an API."""
    try:
        req = urllib.request.Request(f"{gateway_url()}/v1/models",
                                     headers=_headers())
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read() or "{}")
        n = len(d.get("data", []))
        return True, f"{n} model(s) advertised"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, ("gateway is up but rejected the key. Set HERMES_API_KEY to the "
                           "same value as API_SERVER_KEY in ~/.hermes/.env")
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 - any transport failure means not usable
        return False, f"not reachable at {gateway_url()} ({type(e).__name__})"


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "User-Agent": "epalle-studio/1.0"}
    key = _secret("HERMES_API_KEY")
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def ask(prompt: str, model: str = "hermes", timeout: int = 900) -> str:
    """One turn through the gateway. Hermes brings its own skills, memory and tools."""
    ok, why = installed()
    if not ok and gateway_url().startswith("http://127.0.0.1"):
        raise HermesError(
            f"hermes is not installed and the gateway is local. Install it:\n"
            f"  {INSTALL['windows']}   (Windows)\n"
            f"  {INSTALL['linux/macos']}   (Linux/macOS)\n"
            f"{INSTALL['note']}")
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "stream": False}).encode()
    req = urllib.request.Request(f"{gateway_url()}/v1/chat/completions",
                                 data=body, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HermesError(f"gateway returned {e.code}: "
                          f"{e.read().decode('utf-8','replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise HermesError(
            f"could not reach the Hermes gateway at {gateway_url()}: {e.reason}. "
            f"Start it with `hermes gateway`, and set API_SERVER_ENABLED=true plus "
            f"API_SERVER_KEY in ~/.hermes/.env.") from e
    return (d.get("choices") or [{}])[0].get("message", {}).get("content", "")


def sync_skills(dry_run: bool = True) -> tuple[int, list[str]]:
    """Mirror approved skills into ~/.hermes/skills/.

    Hermes treats that directory as its source of truth and follows the same
    folder-plus-SKILL.md standard, so this is a copy rather than a translation. One
    canonical source in `shared-skills/approved/` keeps Claude Code, Codex and Hermes from
    drifting into three versions of the same procedure.
    """
    src = REPO / "shared-skills" / "approved"
    if not src.exists():
        raise HermesError(f"no approved skills at {src}")
    names = [d.name for d in sorted(src.iterdir()) if (d / "SKILL.md").exists()]
    if dry_run:
        return len(names), names
    SKILLS.mkdir(parents=True, exist_ok=True)
    for d in sorted(src.iterdir()):
        if (d / "SKILL.md").exists():
            shutil.copytree(d, SKILLS / d.name, dirs_exist_ok=True)
    return len(names), names


def suggested_config() -> str:
    """Config for THIS studio, in Hermes' real format. Printed, never written —
    overwriting someone's agent config from another tool is not a thing to do quietly."""
    return """# ~/.hermes/config.yaml  — additions for the content studio.
# MERGE these into your existing config; do not overwrite the file.

provider: auto
base_url: "https://openrouter.ai/api/v1"     # OPENROUTER_API_KEY in ~/.hermes/.env
# Or Kimi: provider: kimi-coding   (needs KIMI_API_KEY)

skills:
  # `uv run studio.py skills-sync` copies shared-skills/approved/ into ~/.hermes/skills/.
  # external_dirs would let Hermes read the repo directly, but a copy keeps a working
  # tree mid-edit from changing what the agent believes.
  write_approval: true          # skill_manage must ask before writing

# Exactly ONE external memory provider may be active; built-in memory stays on alongside.
# The studio's own store (packages/memory) is authoritative either way — attach Graphiti
# over MCP rather than as a memory provider so the two do not compete for that slot.
mcp_servers:
  graphiti-memory:
    transport: http
    url: "http://127.0.0.1:8010/mcp/"        # infra/memory/docker-compose.yml

  # Optional: give Hermes read access to the studio's own tooling.
  # filesystem:
  #   command: "npx"
  #   args: ["-y", "@modelcontextprotocol/server-filesystem",
  #          "C:/Users/inkno/Documents/GitHub/comfy"]
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Hermes runtime integration.")
    ap.add_argument("command", choices=["check", "config", "sync-skills", "ask"])
    ap.add_argument("--text", default="Summarise what this content studio does.")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    if a.command == "check":
        ok, where = installed()
        print(f"hermes binary   {'READY' if ok else 'MISSING':<8} {where}")
        print(f"HERMES_HOME     {HERMES_HOME}  {'exists' if HERMES_HOME.exists() else 'absent'}")
        print(f"config.yaml     {'present' if CONFIG.exists() else 'absent'}")
        print(f"skills dir      {'present' if SKILLS.exists() else 'absent'}  {SKILLS}")
        up, why = gateway_up()
        print(f"gateway         {'UP' if up else 'DOWN':<8} {gateway_url()}  ({why})")
        print(f"HERMES_API_KEY  {'set' if _secret("HERMES_API_KEY") else 'not set'}")
        if not ok:
            print("\nInstall:")
            print(f"  Windows:      {INSTALL['windows']}")
            print(f"  Linux/macOS:  {INSTALL['linux/macos']}")
            print(f"  {INSTALL['note']}")
        print("\nSecurity note from Hermes' own MCP docs: installing a catalog entry runs "
              "`git clone` plus arbitrary bootstrap commands and then the server's code. "
              "Read a manifest before `hermes mcp install`.")
        raise SystemExit(0 if ok else 1)

    if a.command == "config":
        print(suggested_config())
        return

    if a.command == "sync-skills":
        n, names = sync_skills(dry_run=not a.live)
        verb = "would mirror" if not a.live else "mirrored"
        print(f"{verb} {n} skill(s) to {SKILLS}: {', '.join(names)}")
        if not a.live:
            print("(pass --live to copy)")
        return

    if a.command == "ask":
        print(ask(a.text))


if __name__ == "__main__":
    try:
        main()
    except HermesError as e:
        raise SystemExit(f"error: {e}")
