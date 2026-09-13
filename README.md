# EPALLE Studio × Ongea Pesa — Autonomous Content Company

Monorepo for a voice-driven content studio: brief → strategy → generation (OpenRouter / ComfyUI on RunPod) → deterministic brand compositing → scheduled publishing (Postiz, WhatsApp Status) — with a graphified corpus and temporal memory.

Design spec: `docs/superpowers/specs/2026-09-12-epalle-ongea-content-company-design.md`

Standing rules: queued is not success · dry-run by default, allowlists not arbitrary input · composite the logo, never regenerate it · agents create, deterministic code validates, humans approve.

Secrets live in Windows DPAPI via `infra/runpod/set_secret.py` (stored outside the repo; `--list` shows what is set) and every adapter reads them through `packages/common/vault.py`. No `.env` with real values is ever committed.

## Start here

```bash
uv run studio.py doctor          # what is installed, reachable and blocked
uv run studio.py plan            # plan all 30 Ongea Pesa ideas (costs nothing)
uv run studio.py check           # fail if anything secret-shaped is tracked
uv run studio.py test            # 36 end-to-end tests, no key/GPU/network
uv run studio.py loop            # the whole pipeline on fixture data
```

### Studio canvas and workflows

The studio UI (`packages/studio-ui`) is a node canvas organised by client. Every client in
`brands/` has its own workflows, and `brands/_templates/` holds one ready-made workflow per
business idea. You can start a workflow from an idea, a plain description, or by combining
workflows so one result feeds the next. The canvas and the author share one node catalogue
(`packages/studio-ui/catalog/nodes.json`), and any step the studio cannot run yet is shown as
a gap.

```bash
npm install --prefix packages/studio-ui
npm run dev --prefix packages/studio-ui
uv run --with pyyaml packages/strategy/workflow_author.py --list
uv run --with pyyaml packages/strategy/workflow_author.py --idea V02 --client ongea-pesa
uv run --with pyyaml packages/strategy/workflow_author.py --combine M01 M04 --client epalle
uv run --with pyyaml packages/strategy/workflow_author.py --check
```

- **`docs/ABOUT.md` — what this project is about and why it is built this way**
- `docs/WHAT-THIS-DOES.md` — the system tour: what the system is and how it fits together**
- `docs/ROADMAP.md` — every step to go live, in dependency order, with owners and gates
- `graphify-out/graph.html` — the whole system as an interactive graph (1,493 nodes, 103 communities). Different from `graph/`, which is the typed ComfyUI dependency graph the pipeline itself queries
- `docs/SETUP.md` — A-Z, with human-only steps marked **[you]**
- `docs/BLOCKERS.md` — the honest register of what is not working, each item assigned
- `shared-skills/approved/content-studio/SKILL.md` — how to drive the pipeline
- `docs/superpowers/specs/2026-09-12-epalle-ongea-content-company-design.md` — the full design

### Built so far

| Package | Does |
|---|---|
| `brandkit` | loads brand.yaml + 24 style grammars, builds provider-agnostic requests |
| `image-router` | routes to hosted (OpenRouter) or comfy (open-source) as peers |
| `compositor` | deterministic 4K text + logo compositing with a sha256 manifest |
| `comfy-client` | validate + run ComfyUI graphs on local / pod / serverless |
| `ingest` | Instagram, Pinterest and YouTube harvesters, one schema |
| `library` | 602-node corpus graph + query tools |
| `vision` | offline reference analysis: palette, composition, pacing, brand-rule checks |
| `strategy` | study a creator's grammar, plan 30 days, turn a song into a shot list |
| `publish` | Postiz (social), OpenWA (WhatsApp Status), Whop (course) - draft by default |
| `voice` | spoken briefs in (whisper), voiceover + burned-in captions out |
| `analytics` | pull Instagram/Postiz metrics, attribute them to briefs, derive learnings |
| `memory` | bitemporal facts: what worked, when, and what superseded it |
| `orchestrator` | goals, tasks, budgets, approvals, audit; dispatch to Claude/Codex/local/Hermes |
| `studio-ui` | Next.js canvas (ported) |
