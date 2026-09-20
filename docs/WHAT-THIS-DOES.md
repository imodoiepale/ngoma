# What this repo does

Director is a creative studio for any brand. You open a workspace, give it an idea, a
song, a brief or a calendar, and it produces finished, on-brand assets and a schedule. The
same pipeline serves a music project, a fintech app and whatever workspace comes next;
nothing in it is brand-specific.

The organising idea is one sentence:

> **Models make pictures. Code makes brands.**

Generation is probabilistic and allowed to be. Everything a viewer reads as identity (the
headline text, the logo, the palette, the disclosure line) is applied deterministically
afterwards and is never left to a model. That single split is why a hundred posts can look
like one brand instead of a hundred experiments.

---

## Workspaces

A workspace is `brands/<key>/` with a `brand.yaml`. The author (`workflow_author.clients()`),
the canvas (`lib/studio.js listClients()`) and the engine all discover any such folder.

```
brands/<key>/
  brand.yaml        name, kind, palette, logo master, typography, voice, languages, claim safety
  references/       collections; each folder has a collection.json with use, rights, consent
  workflows/        *.studio.json the canvas and the author read and write
  runs/             results and manifests, gitignored
  styles/           optional style grammars
  calendar/         optional seed.yaml and plans
```

| | `epalle` | `ongea-pesa` |
|---|---|---|
| What | Music project | Voice-activated M-Pesa, by NSAIT |
| Palette | charcoal, ivory, dust gold | `#0A0A0A` ground, `#22C55E` accent |
| Structure | ASALI six-stage narrative arc | 30-idea calendar |
| Grammars | 6 ASALI stage and 5 shot grammars | 24 style specs |
| Output | music videos, covers, lookbooks | carousels, reels, single posts, WhatsApp Status |

Both palettes were measured, not accepted from a document. Ongea Pesa's came from the live
site, the app screens and the logo master. EPALLE's came from the cover art and was then
corrected against its own written visual language, which the art violates.

A third workspace is one command. `python packages/strategy/workspace.py new <key> --name "..."`
scaffolds the folder from `brands/_kit/` and validates it; `check <key>` reports what is
missing; `list` shows every workspace. The minimum `brand.yaml` and `collection.json` are
documented in `brands/_kit/README.md`.

---

## From a sentence to a workflow

Two paths exist today, and both write a `*.studio.json` the canvas opens:

- **Brief.** `workflow_author.py --brief "..."` matches words to steps and wires them by port
  type, inserting input nodes and declaring gaps.
- **Director.** `cli.py say --client <ws> --session <s> --text "..."` starts a session. The
  kind of piece (a profile) and the look (a preset) are applied; each later utterance grows
  the workflow ("add a scene at a market at dawn", "5 angles", "wardrobe from my red-dress").
  The session is saved, and replaying it rebuilds the workflow byte for byte.

A unified `describe` command and `/api/describe` route that returns a plan card (steps with
their readiness, gaps, estimate, consent, questions back when an input is unknown, and
proposed continuations) is Part 2C of the design spec and in progress.

Steps are the catalogue in `packages/studio-ui/catalog/nodes.json`, typed by what they carry.
Each names exactly what runs it: a ComfyUI workflow in `workflows/manifest.json` with a
`.ports.json` map, a router profile, a studio module, a publisher, or `gap`. A step the
studio cannot run yet is shown as a gap, never faked.

---

## Batches

A reference folder is a batch. A step spelled `<step>@each` runs once per item on its
iterated input, and `data.each: true` on the node is the contract every side reads.
Validation refuses `each` on inputs, the brand kit, human decisions and publishers, requires
an image or video input to iterate, and relaxes the pick's "keep k of offered" check when a
fan-out feeds it (`tests/test_fan_out_contract.py`). The runner semantics (one submission per
item, seed `base + i * variants + v`, `partial` when some items fail, `posts/<group>/` on
export, a `max_items` cap) are Part 2D of the design and in progress.

The worked case: fifty owned or fictional reference images through a character swap, then a
ten-slide carousel per result, so fifty posts of ten slides each. The item count is known
before the gate because the folder is on disk, so the approval shows "50 items, est $X" and
never a per-item surprise.

---

## The pipeline

```
  idea / song / brief / calendar
          |
          v
    +-----------+   brand.yaml + style grammars
    | brandkit  |   "what is this workspace, and what are its rules?"
    +-----+-----+
          |  GenRequest  (provider-agnostic)
          v
    +--------------+
    | image-router |   hosted (OpenRouter) -+
    +------+-------+   comfy (open source) -+ peers, not a hierarchy
           |                                |
           v                                v
      base visual  <----- comfy-client ---- ComfyUI (local | pod | serverless)
           |                                     ^
           v                                     |
    +-------------+                        graph/ tells it what
    | compositor  |  headline, logo,        packs and models a
    +------+------+  CTA, disclosure,       workflow actually needs
           |         contrast check,
           |         sha256 manifest
           v
      finished master  (5 ratios, up to 3840px)
           |
           v
    +----------+   Postiz  -> Instagram / X / LinkedIn / TikTok
    | publish  |   OpenWA  -> WhatsApp Status
    +----------+   Whop    -> course lessons
```

The Director Engine (`packages/engine`) sits on top: it grows the workflow, the runner
executes stages through the same `comfy-client`, and `edit.py` does cut, voiceover, captions
and export on this machine. Feeding all of it:

```
  ingest (Instagram, Pinterest, YouTube)
      |
      +--> vision    measure every reference: palette, composition, pacing
      |       |
      |       v
      |    strategy  study -> grammar; plan -> briefs; treatment -> shot list
      |
      +--> library   SQLite FTS + the typed corpus graph
```

---

## The packages

| Package | What it does | Runs without a key? |
|---|---|---|
| `brandkit` | Loads a workspace's `brand.yaml` and style grammars, builds a provider-agnostic request. Validates that every calendar entry points at a real grammar. | yes |
| `image-router` | Chooses hosted vs open-source ComfyUI by capability, not cost. Real contract prices, never guesses. | yes (dry-run) |
| `compositor` | Applies headline, subhead, CTA, attribution, disclosure, slide number and the logo. Measures contrast. Writes a sha256 sidecar. | yes |
| `comfy-client` | Validates a workflow against what the target backend actually has, then runs it on local, RunPod pod or RunPod serverless. | yes (validate) |
| `engine` | The Director: brief to workflow, sessions, presets and profiles, references and rights, the runner, port maps, cost estimates. | yes (dry-run) |
| `ingest` | Instagram (via OpenCLI), Pinterest (gallery-dl), YouTube (yt-dlp to mined facts). One schema for all three. | YouTube yes |
| `vision` | Measures references offline: palette, crushed blacks, subject quadrant, quiet zones, edge density, video pacing. | yes |
| `strategy` | `workspace` scaffolds and checks workspaces; `workflow_author` authors and combines; `study` derives a creator's grammar; `plan` builds dated briefs; `treatment` turns a song into a shot list; `proposals`, `idea_diagrams` and `workflow_catalog` generate the docs. | yes |
| `library` | SQLite FTS index, the typed corpus graph and its query tools, the Skool pack importer. | yes |
| `voice` | Spoken briefs in (whisper); voiceover and burned-in captions out; the ElevenLabs Director agent definition. | yes |
| `analytics` | Pull Instagram and Postiz metrics, attribute them to briefs, derive learnings. | yes (fixture) |
| `memory` | Bitemporal facts: what worked, when, and what superseded it. | yes |
| `orchestrator` | Goals, tasks, budgets, approvals, audit; dispatch to a worker runtime. | yes (dry-run) |
| `publish` | Postiz (social), OpenWA (WhatsApp Status), Whop (course). Draft by default. | yes (dry-run) |
| `studio-ui` | Node canvas organised by workspace. Steps typed by what they carry; a workflow starts from an idea, a plain brief, or by chaining workflows. Gaps, consent and 18+ are shown on the step. | yes |

Almost everything works with no API key at all. That is deliberate: you can plan a month,
validate every workflow, analyse every reference and inspect every payload before spending
anything.

---

## From workflow to offer

The studio connects four layers, and each one is generated from the one below it:

| Layer | Where | What it answers |
|---|---|---|
| Workflows | `workflows/manifest.json`, [`docs/workflows/WORKFLOWS.md`](workflows/WORKFLOWS.md) | Every ComfyUI graph (free, community, and the bought Icekiub classroom), fingerprinted with its node packs and models |
| Steps | `packages/studio-ui/catalog/nodes.json` | The canvas steps. A step names exactly what runs it |
| Pipelines | `brands/_templates/workflows/` | One studio workflow per idea, built from the idea's pipeline, validated for port types and declared gaps |
| Offers | `brands/_business/ideas.yaml`, [`docs/proposals/`](proposals/README.md), [`docs/diagrams/ideas/`](diagrams/ideas/README.md) | 50 costed ideas, a proposal and a diagram for each |

Models for the pod come from the same manifest: `infra/runpod/plan_models.py` extracts every
model file with the loader that names it and resolves its source from exact Hugging Face
links already in the repo, then public repo listings. A creator's own trained LoRA is marked
private and never swapped for a lookalike; `download_planned.py` fetches only what is
resolved.

Bought material (the Icekiub Skool classroom) is imported by
`packages/library/tools/import_skool_pack.py`: workflows are registered with their lesson as
source, node packs are attributed from their own code, model weights stay out of git, and a
pack that switches off PyTorch's safe loading is never imported.

---

## The knowledge layer

`graph/` holds a typed graph of the ComfyUI workflows, their node packs and models, and
mined creator transcripts. It answers questions that are structural, not textual:

```bash
python packages/library/graph_query.py deps Carousel_Pose_changer.json
python packages/library/graph_query.py dependents comfyui-kjnodes
python packages/library/graph_query.py evidence flux-2-klein
```

Transcript facts are attached as evidence of a claim, with a video id, a timestamp and a
quote. A creator saying something works is not proof it works, and the graph records which
it has.

---

## The rules that are actually enforced

Not style preferences. Each exists because violating it produced a real failure here.

1. **Queued is not success.** A submitted job, a reachable endpoint and an `IN_QUEUE`
   response all mean nothing happened. Only a completed history with outputs counts.
2. **Unknown is not OK.** If a check could not run, it reports `UNVERIFIED`, never `OK`.
3. **Dry-run by default.** Spending money or publishing needs an explicit flag, and anything
   outward-facing needs a human yes on top. `budget_usd` in `brands/_presets/engine.yaml`
   is a hard cap a human raises.
4. **Composite the logo, never regenerate it.** No model is ever asked to draw the mark or
   any text.
5. **Agents create, deterministic code validates, humans approve.** A generating agent may
   not clear its own `sensitive` or `pitch` brief, and the publisher refuses those briefs at
   the boundary.
6. **Take the grammar, never the images.** Studying a reference derives structural
   constraints. It retains no caption text, carries forward no subject or location, and
   refuses below 12 samples.
7. **No person's name or likeness in a prompt.** One regex refuses a preset, a profile or a
   brief that names a director or a likeness. A real face is used as data only with a
   written release recorded in `collection.json`.

---

## What it cannot do yet

- **Describe in one step.** The unified `describe` endpoint and plan card are specified and
  in progress; today the brief author and the Director session are two commands.
- **Run a batch on the pod.** The `@each` contract is in the author and validated; the
  runner loop, per-item manifests and export layout are in progress.
- **Publish to Instagram.** The account must be converted to Professional and linked to a
  Facebook Page before the Graph API will accept it. Human step.
- **Run ComfyUI serverless.** The RunPod endpoint has never completed a generation, only
  `IN_QUEUE`. Pod-side execution is proven; serverless is not.
- **Carousel pose generation.** `flux-2-klein-9b-kv` is licence-gated on HuggingFace.
- **Run the bought and newer workflows end to end.** None of the 50 idea pipelines has run
  end to end on a GPU. Some model files have no source found yet and some are creators'
  private LoRAs (`infra/runpod/download-plan.json`); gated repos also need `HF_TOKEN`.
- **Five canvas steps have no backend:** LoRA training, video relight, photo restoration,
  translation and motion graphics. Ideas that need them say so in their proposal.
- **Enumerate Instagram references.** Needs the OpenCLI browser extension connected.
- **Learn from real results.** The analytics and memory loop is built and tested, but it
  refuses per-grammar claims below 6 posts per grammar. Expect 4 to 6 weeks of consistent
  posting in a narrow rotation before it says anything trustworthy.
- **Sheng voiceover.** Refused by design: no TTS system supports it, so every provider
  renders it as mispronounced Swahili. Record a human, or write Kiswahili.

Full register with owners and the decisions still open: `docs/BLOCKERS.md`.

---

## Try it, right now, with nothing installed but Python

```bash
python studio.py doctor                        # what is present, reachable and blocked
python studio.py check                         # nothing secret-shaped is tracked
python -m pytest -q                            # the full suite, no key, GPU or network
python packages/strategy/workspace.py list     # the workspaces and their kit status
python packages/strategy/workflow_author.py --list
python packages/engine/cli.py possibilities    # what each kind of reference can drive

python packages/compositor/compositor.py --base out/_synthetic_base.png --idea 1 --ratio 4:5 --slide 1/5
```

That last command produces a finished 3072 by 3840 branded master from any image, with
measured contrast and a checksum manifest, no API key, no GPU.
