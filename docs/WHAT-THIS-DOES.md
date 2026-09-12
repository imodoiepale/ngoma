# What this repo does

A branded content studio. You give it an idea, a song, or a calendar; it produces finished,
on-brand assets and schedules them — for any brand, not one.

The organising idea is one sentence:

> **Models make pictures. Code makes brands.**

Generation is probabilistic and allowed to be. Everything a viewer reads as *identity* —
the headline text, the logo, the palette, the disclosure line — is applied deterministically
afterwards and is never left to a model. That single split is why a hundred posts can look
like one brand instead of a hundred experiments.

---

## The pipeline

```
  idea / song / calendar
          │
          ▼
    ┌───────────┐   brand.yaml + style grammars
    │ brandkit  │   "what is this brand, and what are its rules?"
    └─────┬─────┘
          │  GenRequest  (provider-agnostic)
          ▼
    ┌──────────────┐
    │ image-router │   hosted (OpenRouter) ─┐
    └──────┬───────┘   comfy (open source) ─┤ peers, not a hierarchy
           │                                │
           ▼                                ▼
      base visual  ◀───── comfy-client ──── ComfyUI (local | pod | serverless)
           │                                     ▲
           ▼                                     │
    ┌─────────────┐                        graph/ tells it what
    │ compositor  │  headline · logo ·      packs and models a
    └──────┬──────┘  CTA · disclosure       workflow actually needs
           │         contrast check
           │         sha256 manifest
           ▼
      finished master  (5 ratios, up to 3840px)
           │
           ▼
    ┌──────────┐   Postiz  → Instagram / X / LinkedIn / TikTok …
    │ publish  │   OpenWA  → WhatsApp Status
    └──────────┘   Whop    → course lessons
```

Feeding all of it:

```
  ingest (Instagram · Pinterest · YouTube)
      │
      ├──▶ vision    measure every reference: palette, composition, pacing
      │       │
      │       ▼
      │    strategy  study → grammar · plan → briefs · treatment → shot list
      │
      └──▶ library   SQLite FTS + a 602-node typed knowledge graph
```

---

## The packages

| Package | What it does | Runs without a key? |
|---|---|---|
| `brandkit` | Loads `brand.yaml` + style grammars, builds a provider-agnostic request. Validates that every calendar entry points at a real grammar. | yes |
| `image-router` | Chooses hosted vs open-source ComfyUI **by capability, not cost**. Real contract prices, never guesses. | yes (dry-run) |
| `compositor` | Applies headline, subhead, CTA, attribution, disclosure, slide number and the logo. Measures contrast. Writes a sha256 sidecar. | yes |
| `comfy-client` | Validates a workflow against what the target backend actually has, then runs it on local / RunPod pod / RunPod serverless. | yes (validate) |
| `ingest` | Instagram (via OpenCLI), Pinterest (gallery-dl), YouTube (yt-dlp → mined facts). One schema for all three. | YouTube yes |
| `vision` | Measures references offline: palette, crushed blacks, subject quadrant, quiet zones, edge density, video pacing. | yes |
| `strategy` | `study` derives a creator's grammar; `plan` builds dated briefs; `treatment` turns a song into a shot list. | yes |
| `library` | SQLite FTS index + the typed corpus graph and its query tools. | yes |
| `voice` | spoken briefs in (whisper); voiceover and burned-in captions out | yes |
| `analytics` | pull Instagram/Postiz metrics, attribute them to briefs, derive learnings | yes (fixture) |
| `memory` | bitemporal facts — what worked, when, and what superseded it | yes |
| `orchestrator` | goals, tasks, budgets, approvals, audit; dispatch to a worker runtime | yes (dry-run) |
| `publish` | Postiz (social), OpenWA (WhatsApp Status), Whop (course). Draft by default. | yes (dry-run) |
| `studio-ui` | Next.js canvas, library browser, job view. Ported from the earlier EPALLE studio. | yes |

Almost everything works with no API key at all. That is deliberate — you can plan a full
month, validate every workflow, analyse every reference and inspect every payload before
spending anything.

---

## The two brands

| | `ongea-pesa` | `epalle` |
|---|---|---|
| What | Voice-activated M-Pesa, by NSAIT | Music project |
| Palette | `#0A0A0A` ground, `#22C55E` accent | charcoal / ivory / dust gold |
| Structure | 30-idea calendar | ASALI six-stage narrative arc |
| Grammars | 24 style specs | 6 ASALI stage + 5 shot grammars |
| Output | carousels, reels, single posts | music videos, covers |

Both palettes were **measured**, not accepted from a document. Ongea Pesa's came from the
live site, the app screens and the logo master. EPALLE's came from the cover art and was
then *corrected* against its own written visual language, which the art violates.

Adding a third brand is a `brands/<key>/` directory. Nothing in the pipeline is
brand-specific.

---

## The knowledge layer

`graph/` holds a typed graph of 602 nodes and 2,077 edges built from the 50 deduped
ComfyUI workflows and 22 mined creator transcripts.

It answers questions that are structural, not textual:

```bash
uv run packages/library/graph_query.py deps Carousel_Pose_changer.json
#   -> 3 node packs, 4 model files, 18 node types

uv run packages/library/graph_query.py dependents comfyui-kjnodes
#   -> 31 workflows break without it

uv run packages/library/graph_query.py evidence flux-2-klein
#   -> a deep link to the second a creator made the claim
```

That last one matters: transcript facts are attached as **evidence of a claim**, with a
video id, a timestamp and a quote. A creator saying something works is not proof it works,
and the graph is careful to record which it has.

---

## The rules that are actually enforced

Not style preferences. Each exists because violating it produced a real failure here.

1. **Queued is not success.** A submitted job, a reachable endpoint and an `IN_QUEUE`
   response all mean nothing happened. Only a completed history with outputs counts.
2. **Unknown is not OK.** If a check could not run, it reports `UNVERIFIED` — never `OK`.
   An unreachable backend once validated as passing; now `--live` refuses in that state.
3. **Dry-run by default.** Spending money or publishing needs an explicit flag, and
   anything outward-facing needs a human yes on top.
4. **Composite the logo, never regenerate it.** No model is ever asked to draw the mark or
   any text.
5. **Agents create, deterministic code validates, humans approve.** A generating agent may
   not clear its own `sensitive` or `pitch` brief — and the publisher refuses those briefs,
   so the gate is enforced at the boundary, not just recorded upstream.
6. **Take the grammar, never the images.** Studying a reference derives structural
   constraints. It retains no caption text, carries forward no subject or location, and
   refuses below 12 samples because a pattern from four posts is noise.

---

## What it cannot do yet

- **Publish to Instagram.** The account must be converted to Professional and linked to a
  Facebook Page before the Graph API will accept it. Human step.
- **Run ComfyUI serverless.** The RunPod endpoint has never completed a generation — only
  `IN_QUEUE`. Pod-side execution is proven; serverless is not.
- **Carousel pose generation.** `flux-2-klein-9b-kv` is licence-gated on HuggingFace.
- **Enumerate Instagram references.** Needs the OpenCLI browser extension connected.
- **Learn from real results.** The analytics and memory loop is built and tested, but it
  refuses per-grammar claims below 6 posts per grammar — correctly, since at 3 posts it
  reported a deliberately under-performing grammar as +28%. Expect 4-6 weeks of consistent
  posting in a narrow rotation before it says anything trustworthy.
- **Sheng voiceover.** Refused by design: no TTS system supports it, so every provider
  renders it as mispronounced Swahili. Record a human, or write Kiswahili.

Full register with owners: `docs/BLOCKERS.md`.

---

## Try it, right now, with nothing installed

```bash
uv run studio.py doctor        # what is present, reachable and blocked
uv run studio.py plan          # plan all 30 Ongea Pesa ideas — costs nothing
uv run studio.py graph         # rebuild the knowledge graph
uv run studio.py test          # 36 end-to-end tests
uv run studio.py loop          # the whole learning loop on fixture data

uv run --with pillow --with pyyaml packages/compositor/compositor.py \
    --base out/_synthetic_base.png --idea 1 --ratio 4:5 --slide 1/5
```

That last command produces a finished 3072×3840 branded master from any image, with
measured contrast and a checksum manifest — no API key, no GPU.
