# Hermes — optional fourth worker runtime

`NousResearch/hermes-agent` — MIT, Python + Node, v0.21.2 at the time of writing. Verified
against the GitHub API and the repo's own docs on 2026-09-12.

> **Disambiguation.** This is *not* the Nous Research Hermes **LLM model series**, not
> Facebook's Hermes JS engine, and not any Hermes messaging protocol. Same vendor as the
> models, different artifact: an agent runtime. There is also a notable ring of SEO sites
> around this project (hermesatlas.com, hermes-agent.org, and others) — go to the GitHub
> repo, not the first search result.

## Do you need it?

Probably not yet. The orchestrator already has three working runtimes:

| runtime | what it is | when |
|---|---|---|
| `local` | the studio's own CLIs | **most tasks** — deterministic, free, no model |
| `claude-code` | `claude -p` headless | implement, analyse, report |
| `codex-cli` | `codex exec` | review and verify, so nothing reviews its own work |

Hermes adds a fourth: a persistent agent with **its own** skills, memory and tools, reached
over an HTTP gateway. It is worth adding when you want an agent that accumulates context
across sessions and can be messaged from Telegram/Discord/Slack — not to run a script.

## Install

```bash
# Windows
iex (irm https://hermes-agent.nousresearch.com/install.ps1)

# Linux / macOS
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

`pip install hermes-agent` is **not** equivalent — PyPI lags the npm release. Use the
official installer.

## Configure

```bash
uv run packages/orchestrator/hermes.py config      # prints config for THIS studio
```

It prints rather than writes, because silently overwriting an agent config that another
tool also manages is not a thing to do quietly. Merge the block into
`~/.hermes/config.yaml` yourself.

Key points, all from Hermes' own docs:

- **Provider**: `base_url: https://openrouter.ai/api/v1` with `OPENROUTER_API_KEY`, or
  `provider: kimi-coding` with `KIMI_API_KEY`. Secrets go in `~/.hermes/.env`.
- **Memory**: exactly **one** external provider may be active, and the built-in
  `MEMORY.md`/`USER.md` memory is always on alongside it. So attach Graphiti over **MCP**
  rather than as a memory provider — otherwise it consumes the single slot, and this
  studio's own store (`packages/memory`) stays authoritative regardless.
- **MCP**: `mcp_servers:` with `command`/`args` for stdio, or `transport: http` + `url`
  for remote. That is how `infra/memory/` attaches at `http://127.0.0.1:8010/mcp/`.

## Skills — one source, three runtimes

Hermes reads `~/.hermes/skills/`, one folder per skill containing `SKILL.md`, following the
same agentskills.io standard as Claude Skills. So the studio's skills copy across verbatim:

```bash
uv run studio.py skills-sync                          # .claude/ and .agents/
uv run packages/orchestrator/hermes.py sync-skills --live   # ~/.hermes/skills/
```

Keeping `shared-skills/approved/` as the single source is what stops Claude Code, Codex and
Hermes drifting into three versions of the same procedure.

## Gateway

```bash
# in ~/.hermes/.env
API_SERVER_ENABLED=true
API_SERVER_KEY=<openssl rand -hex 24>
```

```bash
hermes gateway                  # OpenAI-compatible API on 127.0.0.1:8642
export HERMES_API_KEY=<same value as API_SERVER_KEY>
uv run packages/orchestrator/hermes.py check
```

Then register it as a worker:

```bash
uv run packages/orchestrator/control.py add-worker \
    --name hermes --runtime hermes --role "persistent agent" --budget 5
```

## Security

Hermes' own MCP documentation warns that installing a catalog entry runs `git clone` plus
arbitrary `bootstrap` commands and then the server's own code. Read a manifest before
`hermes mcp install`. The same caution applies to `skill_manage`: set
`skills.write_approval: true` so the agent must ask before writing a skill.

The gateway binds to `127.0.0.1`. Keep it there. An exposed agent gateway with tool access
is a remote shell.
