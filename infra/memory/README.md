# Memory — SQLite now, Graphiti/Neo4j optionally

## You probably do not need this yet

`packages/memory/store.py` is the memory layer. It is SQLite, it runs on a laptop, it needs
no key, and it already does the thing that matters: **bitemporal facts**, so you can ask
what the system believed on any past date and see what superseded what.

```bash
uv run packages/memory/store.py believed
uv run packages/memory/store.py believed --as-of 2026-07-15
uv run packages/memory/store.py history --subject pearl_editorial
uv run packages/memory/store.py context --brand ongea-pesa
uv run packages/memory/store.py vault          # Obsidian-openable mirror
```

Deploy the stack below only when you want something SQLite genuinely cannot give you.

## What Neo4j + Graphiti adds

- **A real graph view.** Neo4j Browser renders the relationship structure; SQLite cannot.
- **LLM entity extraction.** Graphiti reads free text ("the carousel did well with
  professionals but flopped on TikTok") and derives entities and edges. The SQLite store
  needs facts recorded explicitly.
- **MCP access.** The Graphiti MCP server exposes memory tools to Claude Code and, later,
  Hermes — so an agent can query memory without going through this CLI.

## What it costs

An LLM call per ingested episode, a running Postgres-class database, and a second place
where truth lives. The SQLite store stays authoritative in this design; Graphiti is a
projection over it, not a replacement. Two authoritative stores is how they diverge.

## Deploy

```bash
cd infra/memory
cp .env.example .env && chmod 600 .env
openssl rand -hex 24        # -> NEO4J_PASSWORD
nano .env
docker compose up -d
```

Both services bind to **127.0.0.1 only**. Reach them over a tunnel:

```bash
ssh -L 7474:127.0.0.1:7474 -L 7687:127.0.0.1:7687 -L 8010:127.0.0.1:8010 user@your-vps
```

Then open http://127.0.0.1:7474.

## Connect it to Claude Code

```json
{ "mcpServers": { "graphiti-memory": {
    "transport": "http", "url": "http://127.0.0.1:8010/mcp/" } } }
```

Hermes allows only one external memory provider at a time while keeping its own native
memory; going in over MCP sidesteps that, which is why this is an MCP server rather than a
Hermes memory plugin.

## What must never enter memory

Enforced by `_scrub()` in `store.py`, which refuses secret-shaped keys outright:

- API keys, tokens, passwords, cookies
- raw chain-of-thought or full prompt text
- image or video binaries — store ids, checksums and descriptions; assets live on disk
- every message an agent exchanged
- unverified rumour presented as fact
- personal information that is not needed

## Backups

```bash
docker compose exec -T neo4j neo4j-admin database dump neo4j --to-stdout > neo4j-$(date +%F).dump
cp packages/memory/memory.sqlite3 memory-$(date +%F).sqlite3   # the authoritative one
```
