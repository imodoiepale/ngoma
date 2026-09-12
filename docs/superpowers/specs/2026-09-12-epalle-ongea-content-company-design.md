# EPALLE Studio × Ongea Pesa — Autonomous Content Company

## Context

You want a voice-driven "super intelligence" that turns any idea into published content: brief → strategy grounded in scraped reference profiles → generated images/carousels/video/UGC → scheduled publishing — with the entire corpus graphified so the system can reason about its own workflows, nodes and playbooks, and eventually create its own skills when analytics warrant. Ongea Pesa (voice-activated M-Pesa, `ongeapesa.nsait.co.ke`, by NSAIT) is the first brand it must serve.

Two prior bodies of work must be reconciled, not duplicated:

1. **EPALLE Studio** (`Documents\Codex\2026-09-06\…-2\outputs\`) — real, partly proven code: RunPod compute tooling, a 349-asset FTS library with a daily watcher, a Whop course publisher, a Next.js canvas. Explored in full; inventory below.
2. **"Ongea Pesa Content Company v3–v5"** — the architecture in your ChatGPT thread (Paperclip + Hermes + Graphiti + OpenRouter image router + 4K compositor + OpenWA + 24-style engine). **The zips are not on disk** and Docker never ran in that sandbox. It is a spec, not code. Its best ideas are adopted below; its infrastructure is rebuilt inside this monorepo rather than trusted.

**Your decisions recorded:** everything ships (phased); fresh monorepo at `GitHub\comfy`; all four compute paths; voice for control *and* voiceover; clean sibling node pack; I research the YouTube channels; brand kit built from the live site + your materials + the ChatGPT tokens; IG account exists but is not Business-linked.

---

## What exists (reuse, do not rebuild)

### Proven code — EPALLE Studio

| Asset | Path (under `…-2\outputs\`) | Notes |
|---|---|---|
| RunPod client (REST + GraphQL) | `deployment/runpod_api.py` | Credentials, pod lifecycle, capacity discovery, job submission |
| Serverless handler | `deployment/handler.py` | Allowlist-only templates, `dry_run=True` default, per-job idempotency, path-traversal guard, SHA-256 outputs |
| GPU capacity picker | `deployment/provision_pod.py` | Cheapest card meeting a VRAM floor in the volume's datacenter |
| Model auditor chain | `deployment/audit_models.py` → `resolve_models.py` → `download_planned.py` | Workflow JSON → model files → HF manifest → resumable download on-pod |
| Library + FTS5 index | `libraries/library.sqlite3`, `tools/build_library_index.py`, `search_library.py` | `assets(path,kind,bytes,sha256,source_id,title,text)` + `search` virtual table |
| Daily watcher | `libraries/tools/source_watch.py` | 5 sources, dedupes by ID, honest `not_enumerable` for Instagram |
| Whop publisher | `course/build_course.py`, `whop_publish.py`, `whop_upload.py` | Verified API contract; never run live |
| Studio canvas | `studio-ui/client/` | Next.js 16.1.1 / React 19.2.3 / reactflow; `/`, `/library`, `/jobs`, `/workflow` |
| RunPod status + library routes | `studio-ui/client/app/api/{runpod-status,library,generate}/route.js` | Server-side only; note the required `User-Agent: epalle-studio/1.0` (Cloudflare 1010) |
| SageAttention toolkit | `deployment/install_sage_a100.sh`, `guard_kjnodes_sage.py`, … | Per-arch build caveat on shared volume |
| DPAPI secret store | `deployment/set_secret.py` | The intended credential pattern |

### Workflow corpus

- **14 Icekiub packs** in `Documents\COMFY\` — dataset gen (Z-Image/Qwen/Klein), IG carousel pose, Qwen faceswap, SCAIL-2 motion, LTX-2/2.3 video, WAN 2.2 I2V infinite, surgery repair. 27 distinct custom node packs; `comfyui-kjnodes` in every workflow; `CR Prompt List` is the universal batch driver.
- **40 curated workflows** in `libraries/workflows/` (aininja 12, h3 12, scail2 5, matrix 3, local-comfy 4, api-tests 4).
- Docker reference `comfyui-scail-docker/` (CUDA 12.4.1, Sage from source) — **pinned to ComfyUI 0.3.26, stale**.
- `work/matrix-power-nodes/` — 2 hosted-API nodes with excellent money-safety patterns (`ExecutionBlocker` on `live=False`, semantic-key double-spend guard). **Compiler-generated; read-only reference.**
- `work/h3/` — 38 MiniMax H3 nodes, GPL-3.0.

### Brand inputs found on disk (`~/Downloads`)

| File | Use |
|---|---|
| `ongea-pesa-lockup-transparent.png` | **The official logo master.** Composited post-generation, never regenerated |
| `ongeapesa.jpeg`, `screencapture-ongeapesa-nsait-co-ke-2026-07-18.png` | Reference for site palette/type |
| `OngeaPesa_Content_Calendar.xlsx` | **30 ready content ideas** with angle/hook/CTA — Mandazi Payment, Matatu Fare, Mama Mboga, Chama Contribution, Grandma Learns, Gen Z vs Old Way, Safaricom Demo… This is the Phase 1 seed |
| `How_Ongea_Parses_Spoken_Transactions.mp4` | Product demo footage for UGC/B-roll |
| `poster prompts.pdf` (TUDOR.AI, 11 pp) | Nine 1:1 replication specs for GPT Image 2 — the style-grammar model: fix field colour + subject placement + typography + exact strings + finish + negatives; vary only the subject |
| `Ongea_Access_OS_Submission_Kit/` | Sister product (voice-first accessibility, Gemma). Accessibility angle for content pillar |
| Pitch/EIC/YC packs | Positioning language, claims already vetted for investors |

### Live infrastructure

RunPod volume `7y7jyghmua` (300 GB, US-KS-2) · serverless endpoint `ugtmfoidpnh8pd` (0–1 workers) · template `s7eg4zafj9` · 12 models verified on volume (103.25 GB: SAM 3.1, WAN 2.1 repack, SCAIL-2, MiniMax H3 ×6).

### Installed here

`docker 29.5.3` · `codex-cli 0.144.1` (+ `codex:*` plugin active in this session) · `agent-reach` · `opencli` · `yt-dlp` · `mcporter` · `uv` · `ffmpeg` · `node` · `python 3.12` · `graphify` skill.
**Not installed:** Hermes, Paperclip (`GitHub\paperclip` is an empty dir), Graphiti/Neo4j, Postiz, OpenWA, `gallery-dl`, `faster-whisper`, poppler.

---

## Blockers and stale state — resolved in Phase 0

1. **Plaintext credentials.** `course/.env.whop` (real `WHOP_API_KEY`, `exp_CCRZF9mdhrPeip`), `studio-ui/client/.env.local` (real `RUNPOD_API_KEY`), `outputs/epalle_runpod_ed25519` + `work/ssh/epalle_runpod_ed25519` (unencrypted SSH keys). **Rotate before `git init`.**
2. **Serverless has never completed a generation** — only `{"status":"IN_QUEUE"}` recorded. Pod-side execution is proven (364.87 s / 45 images).
3. **FLUX.2 Klein 9B KV is HF-gated** → blocks IG Carousel Pose. FP8 accepted; ModelScope fallback documented.
4. **`studio-ui/server/` (FastAPI) proxies everything to `api.muapi.ai`** — dead weight, delete.
5. **Stale counts**: docs/UI say 1,583 assets; DB has 349.
6. `libraries/analysis/`, `libraries/models/` empty though referenced.
7. **Postiz, OpenWA not installed** — nothing publishes today.
8. **`matrix-power-nodes` compiler is absent** → new nodes go in a clean sibling pack (your decision).

---

## Architecture

```
comfy/                                  (git, npm workspaces + uv)
├─ brands/ongea-pesa/
│   ├─ brand.yaml            tokens · modes · voice · languages · claim rules
│   ├─ styles/               24 style grammars (YAML), TUDOR-style exact specs
│   ├─ assets/logo/          lockup masters (never regenerated)
│   ├─ calendar/             30-idea seed → generated plans
│   └─ references/<handle>/  harvested IG/Pinterest + vision features
├─ packages/
│   ├─ image-router/         OpenRouter (Nano Banana 2/Pro, GPT Image 2) with capability checks
│   ├─ compositor/           deterministic 4K text+logo+brand-frame overlay (Pillow)
│   ├─ comfy-client/         templating · validation · 4 backends (local|pod|serverless|hosted)
│   ├─ nodes/epalle-nodes/   clean custom ComfyUI node pack
│   ├─ ingest/               ig-harvest · pin-harvest · yt-learn
│   ├─ library/              SQLite+FTS (ported) · graphify bridge · source watcher
│   ├─ vision/               reference analysis → structured creative features
│   ├─ strategy/             brand + references + graph + memory → content plan + briefs
│   ├─ memory/               Graphiti + Neo4j (temporal, operational) · Markdown vault mirror
│   ├─ video/                HyperFrames deterministic renders + ComfyUI video + ffmpeg mux
│   ├─ voice/                faster-whisper STT (control) · TTS bake-off (voiceover)
│   ├─ publish/              Postiz adapter · OpenWA WhatsApp Status · Whop course
│   └─ studio-ui/            Next.js canvas (ported), brief console, approvals
├─ shared-skills/{candidates,approved,deprecated}/   one canonical skill source
├─ graph/                    graphify-out (static corpus graph)
├─ workflows/                canonical deduped ComfyUI templates + manifest
└─ infra/                    RunPod (ported), docker-compose for postiz/openwa/neo4j/graphiti
```

### Two graphs, two jobs — not redundant

| | `graph/` (graphify) | `packages/memory` (Graphiti + Neo4j) |
|---|---|---|
| Content | Static corpus: workflows, node types, node packs, models, transcripts, lessons, source code | Operational, temporal: campaigns, content items, hooks, styles, audiences, experiments, learnings, approvals |
| Question it answers | "Which workflow makes a 4:5 carousel from one reference? Minimum node packs?" | "What worked for Kenyan professionals in July? Which style is fatigued? What superseded what?" |
| Update cadence | On corpus change | Every publish + every analytics pull |
| Access | `packages/library/query.py` (BFS/DFS + FTS hybrid) | Graphiti MCP server (`/mcp/`) — usable by Claude Code now, Hermes later |

Rule: **binaries never enter either graph** — IDs, checksums, descriptions, relationships only.

### Image provider hierarchy (from the v4 spec, adopted)

1. **OpenRouter** — `google/gemini-3.1-flash-lite-image` (concept), `google/gemini-3.1-flash-image` (daily), `google/gemini-3-pro-image` + `openai/gpt-image-2` (flagship 4K). Capability check per endpoint before every call (resolution, ratio, reference-image support, transparency, pricing). No GPU needed → **this is how Ongea Pesa gets output in week one.**
2. **RunPod ComfyUI** — serverless for scheduled/batch; pod for interactive; local for dev. Owns: video, dataset/LoRA, faceswap, motion, upscales, anything needing Klein/WAN/LTX.
3. **Meta AI via OpenWA** — the v5 thread proposed it as a tertiary experimental provider. **Deferred out of scope**: region-gated, no job IDs, ToS-fragile. Revisit only after Phases 0–6 are stable.

**Hard rule (compositor):** models generate the base visual only. Headline, subhead, logo, "By NSAIT", slide numbers, AI disclosure, source lines, campaign ID and checksum are composited in code from `brand.yaml` — exact spelling, exact palette, no logo mutation. Masters at 1:1 3840², 4:5 3072×3840, 3:4 2880×3840, 9:16 2160×3840, 16:9 3840×2160.

### Orchestration — Claude Code now, Hermes/Paperclip later

Neither Hermes nor Paperclip is installed. Pulling them in now adds two unproven control planes before a single post exists. The plan:

- **Now:** Claude Code skills in `shared-skills/approved/` are the orchestrator; Codex CLI (already installed, `codex:*` plugin active) is the review/verify counterpart exactly as the v4 flow describes (implement → cross-review → independent verify → human approval). `make skills-sync` mirrors approved skills to `.claude/skills/`, `.agents/skills/`, and later `~/.hermes/skills/`.
- **Phase 8:** add Hermes Gateway as the employee runtime and Paperclip as the company control plane, connecting Graphiti via MCP (Hermes allows one external memory provider; MCP sidesteps that). The skill-lifecycle gates from v5 (3 repeated wins, 3 days, 12 items, ≥12 % lift, brand score ≥0.90, holdout ≥0.80, 15 % canary, Paperclip approval, protected-skill list) are adopted verbatim as the promotion policy, enforced in `packages/strategy/skill_curator.py` regardless of which runtime calls it.

---

## Brand kit — Ongea Pesa (seeded now, refined in review)

**Tokens (from v4, adopted):** Obsidian `#010B0C` · Deep Ink `#071416` · Pearl `#EEF1EE` · Porcelain `#F7F8F5` · Emerald `#30E0A8` · Mint `#70E8C0` · Deep Emerald `#006C52` · Cyan `#00A7C8` · Ocean Blue `#075B94` · Electric Blue `#008CD6` · Warm Gold `#D8B35A` (rare) · Graphite `#263331`.

**Six modes:** Orbital Dark · Pearl Editorial · Split Editorial · African Human · Editorial Experimental · Meme Local.

**24 style grammars**, each a TUDOR-style exact spec (audience hypothesis, ratios, background hex, composition system, subject direction, typography rules, palette subset, finish, cultural notes, negative prompt, accessibility, logo safe-zone, AI-disclosure field, experiment variables). Families include Premium African editorial, Apple-style fintech minimalism, Editorial cartoon, Original Kenyan meme, Sheng culture poster, Swiss interleaved typography, Museum pop colour, Risograph, Chama/community storytelling, Founder documentary, Kinetic typography, HyperFrames motion editorial.

**Voice/positioning:** "Money, made natural." · "Speak, send and manage money your way." · by NSAIT. Languages: English, Kenyan English, Kiswahili, Sheng, French (spec in `PROJECT-SUMMARY.md`, reused).

**Claim safety:** reuse `course/lessons/03-02-claim-safe-scripts.md`. No returns/rates/guarantees; no implied Safaricom endorsement (idea #30 "Tag Safaricom" is a *pitch* post, framed as such); payments shown are demo/sandbox; a creator agent cannot approve its own financial claim.

**Portfolio policy:** 60 % proven / 25 % adjacent / 15 % exploratory; vary one factor at a time (hook, language, Sheng intensity, style family, character, pace, duration, CTA, structure, trend, first slide).

---

## YouTube learning corpus (researched on your behalf)

Resolved: **Icekiub** (`UCQDpVBFF5TSu3B27JvTA_oQ`; also "KiubAI" `UCxRwH7p6H8dmLTvkzz6jm_w` already monitored) · **Hearmeman** (HearmemanAI — RunPod templates, serverless, character consistency; GitHub `Hearmeman24`) · **AiorBust** (`@aiorbust` — your "Airbrust").

Proposed additions (prune in review): Mickmumpitz (consistent-character film pipelines) · Latent Vision (Matteo, IPAdapter author — ComfyUI internals) · Aitrepreneur · Pixaroma (ComfyUI tutorial series, 50+ social workflows) · Sebastian Kamph · Olivio Sarikas · Nerdy Rodent · Purz · Scott Detweiler · Benji's AI Playground / Future Thinker · SECourses (Furkan Gözükara — Wan/Flux installs) · ComfyUI official (`@comfyorg`) · Tensor Alchemist · Kevin Stratvert (beginner-facing) · Matt Wolfe · AI Search · Theoretically Media · Curious Refuge · MDMZ · Enigmatic_E · Bijan Bowen · Nathan Shipley · Prompting Pixels · plus the 3 single-video sources already in `monitored-sources.json` (`IksoPQm7Sog`, `SMAaksR_1qg`, `mMfvaNZlf3Q`) resolved to their channels.

Subtitle policy unchanged from the existing archive: `en`, `sw`, `fr` tracks; `faster-whisper` fallback.

---

## Phases and gates

Sequenced so a real Ongea Pesa post exists by the end of Phase 1, before any GPU work.

### Phase 0 — Secure & consolidate
1. Rotate Whop key, RunPod key, SSH keypair. Confirm old ones revoked.
2. `git init` `GitHub\comfy`; `.gitignore` for `.env*`, `*.dpapi`, `*_ed25519*`, `node_modules`, `.next`, `*.safetensors`, `*.pt`, `*.mp4`, `library.sqlite3`, `graph/*.html`.
3. DPAPI (`set_secret.py`) is the only local secret store; `.env.example` files only.
4. Port: `deployment/` → `infra/runpod/`; `libraries/{tools,manifests}` → `packages/library/`; `course/` → `packages/publish/whop/`; `studio-ui/client` + `packages/workflow-builder` → `packages/studio-ui/`. Delete `studio-ui/server/`.
5. Dedupe workflows → `workflows/` + `manifest.json` (SHA-256, node_count, cnr_ids, models). Carousel Pose ×3, ICY SCAIL ×4, Dataset Revamped ×2 → one each.
6. Copy brand inputs from Downloads into `brands/ongea-pesa/assets/` (logo, calendar, demo mp4, PDF).
7. Fix the 1,583→349 count in docs and UI footer.

**Gate:** clean initial commit; `git grep -inE "apik_|rpa_|BEGIN OPENSSH"` empty; old keys confirmed dead.

### Phase 1 — Brand engine + first output (no GPU)
1. `brands/ongea-pesa/brand.yaml` + 24 `styles/*.yaml` from the tokens/modes above and the TUDOR grammar.
2. `packages/image-router`: OpenRouter client with model discovery + per-endpoint capability check, profiles `concept_draft` / `daily_premium` / `brand_master_4k`, cost ledger (reuse `spend_admission` ideas from matrix-power-nodes), semantic-key dedupe.
3. `packages/compositor`: Pillow-based; inputs = base image + `brand.yaml` + copy block; outputs the five master ratios with checksum + campaign ID in metadata.
4. Convert the 30-idea calendar to `brands/ongea-pesa/calendar/seed.yaml` (idea, angle, hook, CTA, language mix, suggested style family, format).
5. Generate the first 5 carousels (ideas 1, 3, 8, 12, 15) end-to-end → review.

**Gate:** 5 reviewed carousels in all five ratios, exact copy, logo composited, costs logged.

### Phase 2 — Ingestion
- **`ig-harvest`** — `agent-reach` (`opencli instagram user <handle>`; run `agent-reach doctor --json` first) for enumeration; `gallery-dl` (`uv tool install`) for carousel/Reel media with browser cookies. Output `brands/<b>/references/<handle>/posts.jsonl` + media, SHA-256'd. Schema precedent: `fanuel-leul-public-profile.json`. Public profiles only; `not_enumerable` honoured.
- **`pin-harvest`** — `gallery-dl` over `COMFY\pinterest.txt` (56 pins) + boards; same schema. Fold in your script when you share it.
- **`yt-learn`** — `yt-dlp --write-auto-sub --sub-langs en,sw,fr --skip-download` across the approved channel list; structured extraction (workflows, node packs, models, settings, claims) → library + graph.

**Gate:** ≥3 Ongea Pesa reference profiles, 56 pins, ≥10 channels; index rebuilds; FTS returns sensible hits.

### Phase 3 — Graphify the corpus
1. `graphify` over workflows + transcripts + lessons + node source + release notes + brand styles → `graph/`.
2. Typed ComfyUI extraction pass: `class_type`, `properties.cnr_id`/`aux_id`, widget model filenames → `workflow→node_type→node_pack`, `workflow→model_file` edges.
3. `packages/library/query.py` hybrid retrieval; surface in `studio-ui` `/library`.

**Gate:** graph correctly answers "minimum node packs + models for Klein carousel pose" and "every workflow depending on `comfyui-kjnodes`", with citations.

### Phase 4 — ComfyUI engine (all four backends)
1. `packages/comfy-client`: template load → validate against graph + target backend inventory → inject (`CR Prompt List`, `LoadImage`, seeds, LoRA names) → submit → poll → SHA-256 manifest. Policy picks `local|pod|serverless|hosted` by model availability, VRAM floor (`audit_models.py`), cost ceiling, latency.
2. Make serverless actually complete: `smoke-test.json` first, then a Klein T2I. "Queued is not success."
3. Refresh Docker: fork `comfyui-scail-docker`, unpin from 0.3.26, install the 27-pack set the graph lists, keep the per-arch Sage guard.
4. `packages/nodes/epalle-nodes/`: brief→prompt-list expander, brand-kit applier, compositor bridge, output-manifest emitter. Standard `NODE_CLASS_MAPPINGS` per module, `async def execute`, CPU-safe tests (h3's `try: import folder_paths` pattern).
5. Models by leverage: `flux-2-klein-9b-fp8` + `flux2-vae` + `qwen_3_8b_fp8mixed` first; chase KV gate in parallel.

**Gate:** one command yields a 5-image carousel and a 5-s video from a brief on ≥2 backends, with manifests.

### Phase 5 — Vision, strategy, memory
1. `packages/vision`: per-asset features (composition, palette, framing, text placement, overlay style, pacing, 3-s hook, caption pattern, hashtags) → JSON beside asset → library.
2. `packages/memory`: Graphiti + Neo4j via docker-compose (`infra/memory/`), Graphiti MCP server, ontology from v5 (Brand, Campaign, ContentItem, Hook, VisualStyle, Audience, Platform, Trend, Experiment, Learning, Skill, Claim, Source, Approval…), Markdown vault mirror under `memory-vault/` (Obsidian-openable). LLM provider: OpenRouter, model per bake-off.
3. `packages/strategy`: brand kit + references + graph + memory → 30-day plan; each brief carries format, style family, language mix, provider/workflow template + params, claim-safety verdict. `skill_curator.py` implements the promotion gates (proposal only — never self-approves).

**Gate:** a reviewed 30-day Ongea Pesa calendar; memory answers the seven pre-campaign questions (valid brand rules, what worked, what's fatigued, last 30 days, failures, human corrections, applicable skills).

### Phase 6 — Publishing
1. Self-host **Postiz** (`infra/postiz/`, Node + Postgres). `packages/publish/postiz.ts` → `POST /public/v1/posts`; IG carousels (ordered slides, one ≤2,200-char caption) and Reels via Graph API. **Default `draft`; `scheduled` only on explicit approval.**
2. **IG prerequisite (your account is not Business-linked):** convert to Professional → link a Facebook Page → Meta Business Suite → connect in Postiz. Documented as a checklist; publishing waits on it. Prove the pipeline on a test Business account first.
3. **OpenWA** (`infra/openwa/`, pin v4.76.0 — v5 is alpha) for WhatsApp Status: text/image/video, one session, conservative limits, human approval gate, idempotency key per publish. Evolution API disabled by default; never both on one number.
4. Whop course publisher retained as second target; its first live run is a first-create against `exp_CCRZF9mdhrPeip`.
5. Seven-day pilot: Postiz drafts only, WhatsApp manual approval.

**Gate:** one carousel + one Reel scheduled to the test IG via Postiz, one Status via OpenWA, all approved by you, rollback verified.

### Phase 7 — Voice + video
1. **Control-in:** push-to-talk in `studio-ui` → `faster-whisper` (en/sw/fr) → brief → plan preview. Confirmation always textual; voice never triggers generation or publishing unattended.
2. **Voiceover:** TTS bake-off scored on Kiswahili/Sheng naturalness before committing a provider; mux with `ffmpeg`; subtitle burn-in from the same script.
3. **HyperFrames** (`packages/video`) for deterministic Reels, animated carousels, kinetic type, charts, phone mockups; ComfyUI video (WAN/LTX/SCAIL) for generative shots; `How_Ongea_Parses_Spoken_Transactions.mp4` as B-roll.

**Gate:** speak a 20-s English brief → reviewed plan → Kiswahili-voiceover Reel → scheduled draft.

### Phase 8 — Skills, Hermes, Paperclip
1. Author `shared-skills/approved/content-studio/` (router) + `ig-harvest`, `pin-harvest`, `yt-learn`, `comfy-run`, `brand-strategy`, `postiz-publish`, `wa-status` via `superpowers:writing-skills`; `make skills-sync`.
2. Deploy Hermes Gateway + Paperclip (pinned releases) in docker-compose; connect Graphiti via MCP; register Claude Code and Codex as workers; import company/employee definitions; protected-skill list enforced.
3. Re-graphify the monorepo itself.

**Gate:** Paperclip assigns a task → Hermes runs the skill → Claude implements → Codex reviews → verifier → your approval → draft created. Skill curator proposes one candidate from real analytics and it is correctly *blocked* pending approval.

---

## Open items you own

1. Your Pinterest download script (fold into `pin-harvest`).
2. Prune/approve the YouTube channel list.
3. Meta Business linking for the Ongea Pesa IG account (creating/linking accounts is yours; I document the steps).
4. OpenRouter key, RunPod key (rotated), Postiz/OpenWA/Graphiti secrets — into DPAPI, never files.

## Verification

```bash
# Phase 0
git -C ~/Documents/GitHub/comfy grep -inE "apik_|rpa_|BEGIN OPENSSH PRIVATE"      # empty

# Phase 1
uv run packages/image-router/cli.py --brand ongea-pesa --idea 1 --profile daily_premium --dry-run
uv run packages/compositor/cli.py --brand ongea-pesa --in out/base.png --copy calendar/seed.yaml#1

# Phase 2
python packages/library/tools/build_library_index.py && python packages/library/tools/search_library.py "carousel pose klein"

# Phase 4
python infra/runpod/run_workflow.py --template smoke-test --backend serverless   # COMPLETED, not IN_QUEUE

# Phase 6
npm run publish -- --brand ongea-pesa --dry-run     # inspect payload; nothing leaves as 'scheduled' without approval
```

Inherited standing rules, kept explicit: **queued is not success** · **dry-run by default, allowlists not arbitrary input** · **composite the logo, never regenerate it** · **agents create, deterministic code validates, humans approve**.
