---
name: content-studio
description: Use when producing branded content end to end for ANY brand's workspace in Director: social posts, carousels, reels, UGC, batches of persona stills, or a music video, turning an idea, song, brief or calendar into generated assets and a schedule. Covers opening a workspace, brand kits and style grammars, reference collections and their rights, harvesting references (Instagram/Pinterest/YouTube), studying a reference creator's grammar without copying their work, the ComfyUI workflow graph, generation via OpenRouter or open-source ComfyUI models, deterministic 4K compositing, song-to-shot-list treatments, and publishing. Trigger on "make content for <brand>", "open a workspace for <brand>", "generate a carousel", "build a content plan", "plan a music video", "turn this song into a treatment", "study this creator", "harvest references", "which workflow should I use", "what do I need to install for <workflow>".
---

# Content Studio

A brand-safe content pipeline for any workspace. The organising idea: **models make
pictures, code makes brands.** Generation is probabilistic and allowed to be; everything a
viewer reads as identity (the headline text, the logo, the palette, the disclosure) is
applied deterministically afterwards and is never left to a model.

Repo root: `C:\Users\ADMIN\Documents\GitHub\ngoma` (the folder keeps its old name; the product is Director). Run everything with plain `python`
(`uv` is not on PATH here; `uv run --with pyyaml python <script>` also works where it is).
Set `PYTHONIOENCODING=utf-8` first.

## Workspaces

A workspace is `brands/<key>/` with a `brand.yaml`. The studio is built to take any number;
two exist today.

| Workspace | What it is | Arc | Palette |
|---|---|---|---|
| `epalle` | music project | ASALI six-stage | charcoal / ivory / dust gold |
| `ongea-pesa` | voice-activated M-Pesa, by NSAIT | none, calendar-driven | `#0A0A0A` ground, `#22C55E` accent |

Opening one for a new brand:

```bash
python packages/strategy/workspace.py new <key> --name "Display Name" --accent "#30E0A8" --kind fashion --dry-run
python packages/strategy/workspace.py new <key> --name "Display Name" --accent "#30E0A8" --kind fashion
python packages/strategy/workspace.py check <key>
python packages/strategy/workspace.py list
```

`new` scaffolds `brand.yaml`, `references/README.md`, `workflows/`, `runs/` (gitignored) and
`assets/logo/` from `brands/_kit/`, then runs `check`. What the person must still do: put
the logo master at `logo.master` (it is composited, never generated), measure the palette
from the real product, write the `positioning` copy, and add at least one style grammar
under `styles/` before asking `brandkit` for a request. `brands/_kit/README.md` documents
the minimum kit and the minimum `collection.json`.

## Standing rules

These are not style preferences. Each one exists because violating it produced a real
failure in this codebase or its predecessor.

1. **Queued is not success.** A submitted job, a reachable endpoint and a returned
   `IN_QUEUE` all mean nothing happened yet. Only a completed history with outputs counts.
2. **Unknown is not OK.** If a check could not run, report `UNVERIFIED`, never `OK`.
3. **Dry-run by default.** Spending money or publishing needs an explicit flag AND, for
   anything outward-facing, a human yes. `budget_usd` in `brands/_presets/engine.yaml` is a
   hard cap only a human raises.
4. **Composite the logo, never regenerate it.** No image model is ever asked to draw the
   mark, the wordmark, or any text.
5. **Agents create, deterministic code validates, humans approve.** A generating agent may
   not approve its own `claim_class: sensitive` or `pitch` item.
6. **No person's name or likeness in a prompt.** Presets and profiles are grammar. A real
   face is data only with a written release recorded in `collection.json` (`consent: true`).
   No exception for public figures, customers, staff or friends.

## Pick the path

| The ask | Start here |
|---|---|
| "open a workspace for X" / "is the kit complete?" | `packages/strategy/workspace.py new` / `check` |
| "describe a piece and grow it" | `packages/engine/cli.py say` (the Director), or `workflow_author.py --brief` |
| "what do I need to run X?" | `graph_query.py deps` |
| "what breaks without Y?" | `graph_query.py dependents` |
| "who said this works?" | `graph_query.py evidence` |
| "make a post / carousel / reel" | brandkit, image-router, compositor |
| "a batch: N references, one step each, then M slides per result" | the `@each` contract, below |
| "find references" | `packages/ingest/` |
| "what can this reference drive?" | `packages/engine/references.py possibilities` |
| "learn from creators" | `yt_learn.py` |
| "run a ComfyUI graph" | `packages/comfy-client/client.py` |
| "analyse these references" | `packages/vision/analyze.py` |
| "study / clone this creator" | `packages/strategy/study.py` |
| "plan the next 30 days" | `packages/strategy/plan.py` |
| "turn this song into a video" | `packages/strategy/treatment.py` |
| "queue / approve / budget work" | `packages/orchestrator/control.py` |
| "run a task on an agent" | `packages/orchestrator/workers.py` |

## 1. Know the corpus before generating

The typed graph answers dependency questions exactly. Rebuild it after adding workflows or
transcripts.

```bash
python packages/library/graph_build.py
python packages/library/graph_query.py deps Carousel_Pose_changer.json
python packages/library/graph_query.py dependents comfyui-kjnodes
python packages/library/graph_query.py evidence flux-2-klein
```

`evidence` returns a deep link to the second a creator made a claim. Treat that as
**evidence of a claim, not proof it works**: say "Icekiub demonstrates X at 14:22", not "X
works".

## 2. Brand kit

`brands/<key>/` holds `brand.yaml` (palette, logo rules, typography, voice, languages, claim
safety), `styles/*.yaml` (style grammars), `calendar/seed.yaml` (ideas) and `references/`.

```bash
python packages/brandkit/brandkit.py --list-styles
python packages/brandkit/brandkit.py --list-ideas     # ! = needs approval
python packages/brandkit/brandkit.py --idea 1         # full request JSON
```

**A style grammar fixes the system and varies only the subject**: field colour,
composition, light, palette, finish and negatives are constant; the subject and copy change.
That is what makes a hundred posts look like one brand.

**Palette provenance matters.** Ongea Pesa's palette was measured from the live site, the
app screens and the logo master, not assumed. When opening a workspace, measure; do not
accept a palette from a document without checking it against the real product. The
scaffold's palette values are placeholders and say so.

## 3. References and rights

Every folder under `brands/<key>/references/` is a collection with a `collection.json`:
`use` (`inspiration` shapes prompts; `data` feeds a node port), `rights` (`owned`,
`licensed`, `unclear`; `data` needs owned or licensed), `consent` (`true` only with a
written release for a real person shown). A folder without the file is inspiration only.
A reference folder is also a batch (section 8).

```bash
python packages/engine/references.py possibilities
python packages/engine/references.py list --brand epalle
python packages/strategy/workspace.py check epalle       # validates every collection
```

## 4. Route the generation

Hosted and open-source are **peers**, not a hierarchy.

```bash
python packages/image-router/router.py --plan-all
python packages/image-router/router.py --idea 3 --backend auto
```

- **hosted** (OpenRouter: Nano Banana 2/Pro, GPT-Image-2): a single still with no edit,
  identity or motion requirement. No GPU, per-call cost.
- **comfy** (FLUX.2 Klein, Qwen-Image/Edit, Z-Image, WAN, LTX, SCAIL): anything needing an
  edit, character consistency across slides, faceswap, or motion. Hosted endpoints cannot do
  those reproducibly, so `auto` sends them here regardless of cost.

## 5. Run a ComfyUI graph

```bash
python packages/comfy-client/client.py probe --backend local
python packages/comfy-client/client.py validate <workflow> --backend local
python packages/comfy-client/client.py run <workflow> --prompt "..." --seed 123
```

Validation is three-state. `UNVERIFIED` means the backend was unreachable so nothing could
be checked; `--live` deliberately refuses in that state. Injection targets `CR Prompt List`;
if a graph has none, the tool says so rather than silently running the template's built-in
prompts.

## 6. Composite

```bash
python packages/compositor/compositor.py --base out/base.png --idea 1 --ratio 4:5 --slide 1/5
```

Applies headline, subhead, CTA, attribution, disclosure, slide number and the logo, checks
contrast, and writes a sha256 sidecar manifest. Masters: 1:1 3840 square, 4:5 3072 by 3840,
3:4 2880 by 3840, 9:16 2160 by 3840, 16:9 3840 by 2160. The copy block comes from the
workspace's `positioning` and `claim_safety.disclosure`.

## 7. Harvest references

```bash
python packages/ingest/ig_harvest.py <handle> --limit 12
python packages/ingest/pin_harvest.py --limit 10
python packages/ingest/yt_learn.py --channel kiubai --max-videos 6
```

All three write the same `posts.jsonl` shape. Instagram routes through agent-reach and
OpenCLI and **needs the OpenCLI browser extension connected**; when it is not, the harvester
reports `not_enumerable` with the reason. It refuses every write subcommand (follow, like,
comment, post): this is reference gathering, never engagement. Harvested material is
`inspiration`, `unclear`, and never reaches a port.

## 8. Batches: the `@each` contract

A reference folder is a batch, and any single-image step can run once per item. In a
pipeline, a brief or a describe sentence the step is spelled `<step>@each`; the node carries
`data.each: true`; `workflow_author.is_each` and `iterated_port` are the helpers every side
reads. Validation refuses `each` on inputs, the brand kit, human decisions and publishers,
and requires an image or video input to iterate. The worked case: fifty owned or fictional
reference images through `character-swap@each`, a `pick`, then `carousel@each` with
`slides: 10`, so fifty posts of ten slides. Cost multiplies GPU seconds by items and says
whether the figure is measured or assumed; the item count is known before the gate because
the folder is on disk. The runner loop is in progress (design spec, Part 2D).

## 9. Analyse references, then derive a grammar

```bash
python packages/vision/analyze.py --brand epalle --path <dir>
python packages/strategy/study.py --path brands/<key>/references/<handle>
```

`analyze.py` runs offline: palette, crushed blacks, warm ratio, subject quadrant, quiet
zones, edge density, symmetry; for video, duration, fps and pacing. No API key. A
measurement is checkable in a way a description is not, which is what lets a brand be
enforced rather than merely described. Violations against `brand.yaml` come back as numbers.

`study.py` is the "learn someone's approach" capability, and it takes the **grammar, never
the images**. Three refusals are enforced in code:

- no caption text is retained, only its structural shape (length, hook position, hashtag
  and emoji density)
- no subject, location or object is carried forward
- **it refuses below 12 samples**, because a pattern from four posts is noise

When reporting a derived grammar, say what it is: a set of constraints to compose original
work inside. Never present it as a template to refill.

## 10. Plan and treat

```bash
python packages/strategy/plan.py --brand ongea-pesa --days 30
python packages/strategy/treatment.py --brand epalle --audio "~/Downloads/Ancestral Pulse.wav" --title "Ancestral Pulse"
```

`plan.py` enforces the portfolio policy (60% proven / 25% adjacent / 15% exploratory) and
makes adjacent briefs vary exactly one dimension from a named proven parent. It blocks
`sensitive` and `pitch` items and flags format and ratio mismatches rather than shipping a
4:5 "reel".

`treatment.py` maps a workspace's narrative arc onto a real audio master. It locks the audio
and frame rate first, derives shot count per stage from that stage's length, and gives every
shot a generation route resolved to a real profile or workflow. Hero shots are held;
connective shots are cut short.

## 11. Direct a piece

```bash
python packages/engine/cli.py say --client epalle --session s1 --text "a lookbook of one persona across a city evening, neon noir"
python packages/engine/cli.py run --client epalle --workflow <id> --stage next
python packages/strategy/workflow_author.py --brief "Sheng WhatsApp status ad for a mama mboga" --client ongea-pesa
```

`--client` takes the workspace key. `say` grows a workflow from speech under a profile (the
kind of piece) and a preset (the look); `run` is dry-run by default and needs a run mode,
a budget above 0 and the control plane's approval to spend. `docs/engine/DIRECTOR-ENGINE.md`
has the modes and the prompt grammar; the `workflow-author` skill has the brief and combine
paths.

## 12. Gate the work

```bash
python packages/orchestrator/control.py init      # seed claude / codex / verifier
python packages/orchestrator/control.py queue
python packages/orchestrator/workers.py runtimes
python packages/orchestrator/workers.py flow --title "some change"
```

The control plane decides **what** may happen and who pays; `workers.py` decides **how**.
Keep them apart. Four things it enforces: risky kinds (`publish`, `skill_promote`,
`spend_increase`, `whatsapp_status`) always need a human; a worker cannot approve its own
task; budget is checked before work starts; and the audit log is hash-chained, so
`control.py verify` detects tampering.

**Local-first routing.** A task whose kind has a deterministic entrypoint runs the script,
not a model, even when assigned to an LLM worker, and says so.

## Gotchas that will bite you

- **`uv` is not on PATH.** `studio.py plan|test|graph|loop` and the studio UI's API routes
  still call it (`docs/BLOCKERS.md`, item 17). Use the `python` commands above.
- **Windows and MSYS paths**: inside a bash heredoc, `/c/Users/...` is not translated. Use
  `C:\Users\...` in Python literals, or pass paths as argv.
- **Console encoding**: set `PYTHONIOENCODING=utf-8`; several tools emit non-ASCII and
  cp1252 will throw.
- **PowerShell writes a BOM** with `Set-Content -Encoding utf8`; `json.loads` rejects it.
  Write JSON from Python or with `UTF8Encoding($false)`.
- **YouTube auto-subs use a rolling window**: each cue repeats the previous line. Always go
  through `yt_learn.vtt_to_cues`, which collapses it.
- **`yt-dlp` ignores `--playlist-end` on channel URLs** (it walks every tab). Cap locally.
- **Node packs have two ids**, `cnr_id` (lowercase registry) and `aux_id` (Owner/Repo).
  Normalise, or one pack becomes two nodes with half its true dependency count.
- **A fixed shots-per-stage truncates long songs.** A longer master needs more shots, not
  longer ones.
- **Format/ratio is a preference list, not one value.** Instagram accepts 1:1, 4:5 and 3:4
  for a feed post; only reels and stories are strictly 9:16.

## Current blockers

`docs/BLOCKERS.md` is the register. The ones that shape this skill's answers:

- **Credentials need rotating** before any live run.
- **`budget_usd` is 0**; nothing live runs until a human raises it.
- **RunPod serverless has never completed a generation** (only `IN_QUEUE`). Pod-side
  execution is proven. Prove serverless first: `python packages/comfy-client/client.py smoke --backend serverless --live`.
- **FLUX.2 Klein 9B KV is licence-gated on HuggingFace**, which blocks `carousel_pose` and
  the carousel step the batch pattern depends on. Accept the KV licence or use fp8.
- **LM Studio is not on the pod**, which blocks dataset captioning and the H3 route.
- **Postiz and OpenWA are not installed**; nothing publishes yet. Instagram publishing also
  needs the account converted to Professional and linked to a Meta Business Page.
- **Decisions still open**: credits versus per-deliverable pricing, the real-person face
  swap policy (never without a written release), and whether `adult: true` nodes appear
  behind the 18+ gate. The product name is settled: **Director** (BLOCKERS 16).
- **EPALLE's shipped cover art violates its own visual language** and its live footage is
  29.97fps while treatments default to 24. Both need a decision; see `brands/epalle/FINDINGS.md`.
