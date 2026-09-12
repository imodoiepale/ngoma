---
name: content-studio
description: Use when producing branded social content end to end — turning an idea, brief or content calendar into generated images, carousels, reels or UGC and scheduling them. Covers brand kits and style grammars, reference harvesting from Instagram/Pinterest/YouTube, the ComfyUI workflow graph, image generation via OpenRouter or open-source ComfyUI models, deterministic 4K brand compositing, and publishing. Trigger on "make content for <brand>", "generate a carousel", "build a content plan", "harvest references", "which workflow should I use", "what do I need to install for <workflow>".
---

# Content Studio

A brand-safe content pipeline. The organising idea: **models make pictures, code makes
brands.** Generation is probabilistic and allowed to be; everything a viewer reads as
identity — the headline text, the logo, the palette, the disclosure — is applied
deterministically afterwards and is never left to a model.

Repo root: `C:\Users\inkno\Documents\GitHub\comfy`. Run everything with `uv run`.

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

## Current blockers

- **Credentials need rotating** before any live run — see `docs/BLOCKERS.md`.
- **RunPod serverless has never completed a generation** (only `IN_QUEUE`). Pod-side
  execution is proven. Prove serverless with `infra/runpod/smoke-test.json` first.
- **FLUX.2 Klein 9B KV is licence-gated on HuggingFace**, which blocks `carousel_pose`.
  The fp8 variant is accepted; accept the KV licence or use fp8.
- **Postiz and OpenWA are not installed**; nothing publishes yet.
- **Instagram publishing** needs the account converted to Professional and linked to a
  Meta Business Page. That is a human step.
