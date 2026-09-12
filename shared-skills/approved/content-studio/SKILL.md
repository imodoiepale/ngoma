---
name: content-studio
description: Use when producing branded content end to end for ANY brand — social posts, carousels, reels, UGC, or a music video — turning an idea, song, brief or calendar into generated assets and a schedule. Covers brand kits and style grammars, reference harvesting (Instagram/Pinterest/YouTube), studying a reference creator's grammar without copying their work, the ComfyUI workflow graph, generation via OpenRouter or open-source ComfyUI models, deterministic 4K compositing, song-to-shot-list treatments, and publishing. Trigger on "make content for <brand>", "generate a carousel", "build a content plan", "plan a music video", "turn this song into a treatment", "study this creator", "clone this account's approach", "harvest references", "which workflow should I use", "what do I need to install for <workflow>".
---

# Content Studio

A brand-safe content pipeline. The organising idea: **models make pictures, code makes
brands.** Generation is probabilistic and allowed to be; everything a viewer reads as
identity — the headline text, the logo, the palette, the disclosure — is applied
deterministically afterwards and is never left to a model.

Repo root: `C:\Users\inkno\Documents\GitHub\comfy`. Run everything with `uv run`.

**Two brands live here, and the system is built to take more.**

| Brand | What it is | Arc | Palette |
|---|---|---|---|
| `ongea-pesa` | voice-activated M-Pesa, by NSAIT | none — calendar-driven | `#0A0A0A` ground, `#22C55E` accent |
| `epalle` | music project | ASALI six-stage | charcoal / ivory / dust gold |

Adding a third means a `brands/<key>/` with `brand.yaml` + `styles/` + `calendar/`. Nothing
in the pipeline is brand-specific.

## Standing rules

These are not style preferences. Each one exists because violating it produced a real
failure in this codebase or its predecessor.

1. **Queued is not success.** A submitted job, a reachable endpoint and a returned
   `IN_QUEUE` all mean nothing happened yet. Only a completed history with outputs counts.
2. **Unknown is not OK.** If a check could not run, report `UNVERIFIED`, never `OK`.
3. **Dry-run by default.** Spending money or publishing needs an explicit flag AND,
   for anything outward-facing, a human yes.
4. **Composite the logo, never regenerate it.** No image model is ever asked to draw
   the mark, the wordmark, or any text.
5. **Agents create, deterministic code validates, humans approve.** A generating agent
   may not approve its own `claim_class: sensitive` or `pitch` item.

## Pick the path

| The ask | Start here |
|---|---|
| "what do I need to run X?" | `graph_query.py deps` |
| "what breaks without Y?" | `graph_query.py dependents` |
| "who said this works?" | `graph_query.py evidence` |
| "make a post / carousel / reel" | brandkit → image-router → compositor |
| "find references" | `packages/ingest/` |
| "learn from creators" | `yt_learn.py` |
| "run a ComfyUI graph" | `packages/comfy-client/client.py` |
| "analyse these references" | `packages/vision/analyze.py` |
| "study / clone this creator" | `packages/strategy/study.py` |
| "plan the next 30 days" | `packages/strategy/plan.py` |
| "turn this song into a video" | `packages/strategy/treatment.py` |
| "queue / approve / budget work" | `packages/orchestrator/control.py` |
| "run a task on an agent" | `packages/orchestrator/workers.py` |

## 1. Know the corpus before generating

The graph (602 nodes) answers dependency questions exactly. Rebuild it after adding
workflows or transcripts.

```bash
uv run packages/library/graph_build.py
uv run packages/library/graph_query.py deps Carousel_Pose_changer.json
uv run packages/library/graph_query.py dependents comfyui-kjnodes
uv run packages/library/graph_query.py evidence flux-2-klein
```

`evidence` returns a deep link to the second a creator made a claim. Treat that as
**evidence of a claim, not proof it works** — say "Icekiub demonstrates X at 14:22", not
"X works".

## 2. Brand kit

`brands/<brand>/` holds `brand.yaml` (palette, logo rules, typography, languages, claim
safety), `styles/*.yaml` (24 style grammars), `calendar/seed.yaml` (ideas) and
`references/`.

```bash
uv run --with pyyaml packages/brandkit/brandkit.py --list-styles
uv run --with pyyaml packages/brandkit/brandkit.py --list-ideas     # ! = needs approval
uv run --with pyyaml packages/brandkit/brandkit.py --idea 1         # full request JSON
```

**A style grammar fixes the system and varies only the subject** — field colour,
composition, light, palette, finish and negatives are constant; the subject and copy
change. That is what makes a hundred posts look like one brand. Adapted from the TUDOR
poster method (`brands/ongea-pesa/styles/tudor-poster-prompts-source.pdf`).

**Palette provenance matters.** Ongea Pesa's palette was measured from the live site, the
app screens and the logo master — not assumed. When adding a brand, measure; do not accept
a palette from a document without checking it against the real product.

## 3. Route the generation

Hosted and open-source are **peers**, not a hierarchy.

```bash
uv run --with pyyaml packages/image-router/router.py --plan-all
uv run --with pyyaml packages/image-router/router.py --idea 3 --backend auto
```

- **hosted** (OpenRouter: Nano Banana 2/Pro, GPT-Image-2) — a single still with no edit,
  identity or motion requirement. No GPU, per-call cost.
- **comfy** (FLUX.2 Klein, Qwen-Image/Edit, Z-Image, WAN, LTX, SCAIL) — anything needing
  an edit, character consistency across slides, faceswap, or motion. Hosted endpoints
  cannot do those reproducibly, so `auto` sends them here regardless of cost.

## 4. Run a ComfyUI graph

```bash
uv run packages/comfy-client/client.py probe --backend local
uv run packages/comfy-client/client.py validate <workflow> --backend local
uv run packages/comfy-client/client.py run <workflow> --prompt "..." --seed 123
```

Validation is three-state. `UNVERIFIED` means the backend was unreachable so nothing could
be checked — `--live` deliberately refuses in that state. Injection targets
`CR Prompt List`; if a graph has none, the tool says so rather than silently running the
template's built-in prompts.

## 5. Composite

```bash
uv run --with pillow --with pyyaml packages/compositor/compositor.py \
  --base out/base.png --idea 1 --ratio 4:5 --slide 1/5
```

Applies headline, subhead, CTA, attribution, disclosure, slide number and the logo, checks
contrast, and writes a sha256 sidecar manifest. Masters: 1:1 3840², 4:5 3072×3840,
3:4 2880×3840, 9:16 2160×3840, 16:9 3840×2160.

On dark grounds the Ongea Pesa lockup (navy + pale cyan) sits on a pearl plate with the
declared clear space. That is a *placement* decision — the master is never recoloured.

## 6. Harvest references

```bash
uv run --with pyyaml packages/ingest/ig_harvest.py <handle> --limit 12
uv run --with pyyaml packages/ingest/pin_harvest.py --limit 10
uv run --with pyyaml packages/ingest/yt_learn.py --channel kiubai --max-videos 6
```

All three write the same `posts.jsonl` shape. Instagram routes through agent-reach →
OpenCLI and **needs the OpenCLI browser extension connected**; when it is not, the
harvester reports `not_enumerable` with the reason. It refuses every write subcommand
(follow/like/comment/post) — this is reference gathering, never engagement.

## 7. Analyse references, then derive a grammar

```bash
uv run --with pillow --with pyyaml packages/vision/analyze.py --brand epalle --path <dir>
uv run packages/strategy/study.py --path brands/<brand>/references/<handle>
```

`analyze.py` runs **offline** — palette, crushed blacks, warm ratio, subject quadrant,
quiet zones, edge density, symmetry; for video, duration/fps/pacing. No API key. That is
deliberate: a measurement is checkable in a way a description is not, which is what lets a
brand be *enforced* rather than merely described. Violations against `brand.yaml` come back
as numbers.

`study.py` is the "clone someone's approach" capability, and it takes the **grammar, never
the images**. Three refusals are enforced in code, not documented as advice:

- no caption text is retained — only its structural shape (length, hook position, hashtag
  and emoji density)
- no subject, location or object is carried forward
- **it refuses below 12 samples**, because a pattern from four posts is noise wearing a suit

When reporting a derived grammar, say what it is: a set of constraints to compose original
work inside. Never present it as a template to refill.

## 8. Plan and treat

```bash
uv run --with pyyaml packages/strategy/plan.py --brand ongea-pesa --days 30
uv run --with pyyaml packages/strategy/treatment.py --brand epalle \\
    --audio "~/Downloads/Ancestral Pulse.wav" --title "Ancestral Pulse"
```

`plan.py` enforces the portfolio policy (60% proven / 25% adjacent / 15% exploratory) and
makes adjacent briefs vary **exactly one dimension** from a named proven parent — change
three at once and the result is unattributable, so you learn nothing. It blocks
`sensitive`/`pitch` items and flags format/ratio mismatches rather than shipping a 4:5
"reel".

`treatment.py` maps a brand's narrative arc onto a real audio master. It locks the audio and
frame rate first, derives shot count per stage from that stage's length, and gives every
shot a generation route (`still_push`, `performance`, `motion_xfer`, `segmented`, `texture`)
resolved to a real profile or workflow. Hero shots are held; connective shots are cut short
— even distribution is what makes a music video feel like a slideshow.

## 9. Gate the work

```bash
uv run packages/orchestrator/control.py init      # seed claude / codex / verifier
uv run packages/orchestrator/control.py queue
uv run packages/orchestrator/workers.py runtimes
uv run packages/orchestrator/workers.py flow --title "some change"
```

The control plane decides **what** may happen and who pays; `workers.py` decides **how**.
Keep them apart — merged, the thing that decides what is allowed is the same thing that
wants to do it.

Four things it enforces, not suggests: risky kinds (`publish`, `skill_promote`,
`spend_increase`, `whatsapp_status`) always need a human; a worker cannot approve its own
task; budget is checked BEFORE work starts; and the audit log is hash-chained, so
`control.py verify` detects tampering.

**Local-first routing.** A task whose kind has a deterministic entrypoint runs the script,
not a model, even when assigned to an LLM worker — and says so. Routing `graph_rebuild`
through an LLM would be slower, costlier and less reliable. `spec.force_runtime` overrides.

Hermes and Paperclip are real and optional. Neither is installed; both adapters degrade to
an instruction. Install Hermes for a persistent agent with its own memory; deploy Paperclip
when more than one person supervises.

## Gotchas that will bite you

- **`uv run` needs deps declared**: `--with pyyaml`, `--with pillow`.
- **Windows + MSYS paths**: inside a bash heredoc, `/c/Users/...` is not translated.
  Use `C:\Users\...` in Python literals, or pass paths as argv.
- **Console encoding**: set `PYTHONIOENCODING=utf-8`; `agent-reach doctor` emits non-ASCII
  and cp1252 will throw.
- **YouTube auto-subs use a rolling window** — each cue repeats the previous line. Always
  go through `yt_learn.vtt_to_cues`, which collapses it; naive parsing triples every fact.
- **`yt-dlp` ignores `--playlist-end` on channel URLs** (it walks every tab). Cap locally.
- **Node packs have two ids** — `cnr_id` (lowercase registry) and `aux_id` (Owner/Repo).
  Normalise, or one pack becomes two nodes with half its true dependency count.
- **A fixed shots-per-stage truncates long songs.** A longer master needs MORE shots, not
  longer ones; fixing the count pinned every shot to the clamp and lost 46s of a 177s song.
- **Format/ratio is a preference list, not one value.** Instagram accepts 1:1, 4:5 and 3:4
  for a feed post; only reels and stories are strictly 9:16. Modelling it as a single
  required ratio flags perfectly publishable 4:5 singles as broken.
- **A backslash-n inside a bash heredoc that writes Python** becomes a real newline and an
  unterminated f-string. Use a bare `print()` for the blank line, or the Write tool.

## Current blockers

- **Credentials need rotating** before any live run — see `docs/BLOCKERS.md`.
- **RunPod serverless has never completed a generation** (only `IN_QUEUE`). Pod-side
  execution is proven. Prove serverless first: `uv run packages/comfy-client/client.py smoke --backend serverless --live` (passes only on COMPLETED with files).
- **FLUX.2 Klein 9B KV is licence-gated on HuggingFace**, which blocks `carousel_pose`.
  The fp8 variant is accepted; accept the KV licence or use fp8.
- **Postiz and OpenWA are not installed**; nothing publishes yet.
- **Instagram publishing** needs the account converted to Professional and linked to a
  Meta Business Page. That is a human step.
- **EPALLE's shipped cover art violates its own visual language** (30-47% crushed blacks
  where the brand says never pure black), and its live footage is 29.97fps while treatments
  default to 24. Both need a decision — see `brands/epalle/FINDINGS.md`.
