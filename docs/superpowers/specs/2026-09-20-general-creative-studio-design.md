# Director Studio: a general creative studio, any brand, any capability

## Context

The studio today is EPALLE Studio: a voice-driven content company for two brands (EPALLE
and Ongea Pesa), a Next.js lobby of clients and 50 idea templates, a node canvas per client,
a Director Engine that grows a workflow from speech, and a runner that executes stages on
the RunPod pod through 14 port-mapped ComfyUI workflows. It works, and it reads as an
internal tool for two clients.

The ask is to make it the kind of product Higgsfield and Weavy are: a premium creative
studio where anyone with a brand opens a workspace, browses capabilities as large media
cards, describes what they want in one sentence and gets a runnable pipeline, drops fifty
reference images on a character changer and then asks for a carousel of five or ten slides
per result. All 50 ideas should finish. Nothing about the rights gate, the approval gate or
the budget gate changes.

This document is the design, the audit of what exists against that ask, and the split into
parallel workstreams with explicit file ownership. One shared contract (the fan-out
attribute) was implemented alongside it so the workstreams do not collide.

Standing rules, unchanged: queued is not success. Dry run by default. Composite the logo,
never regenerate it. Agents create, deterministic code validates, humans approve. No
person's name or likeness in a prompt. References feed a step only when they are owned,
licensed or fictional, and a real face only with a written release.

---

## Part 1. What Higgsfield and Weavy do, and what we take

### Identification

**Higgsfield AI** (higgsfield.ai) is confirmed: an AI video and image platform aggregating
30+ third-party models (Kling, Veo, Sora, Wan, Seedance, Nano Banana) with its own Soul
image model, Soul ID identity layer, Cinema Studio camera controls, and about 40 one-click
"apps" (face swap, character swap, outfit swap, relight, angles, transitions, ads).
Sources: https://higgsfield.ai/ , https://higgsfield.ai/apps ,
https://higgsfield.ai/ai-video , https://higgsfield.ai/apps/character-swap ,
https://higgsfield.ai/creator-hub/help-center/tools/how-do-i-use-cinema-studio ,
https://higgsfield.ai/blog/cinema-studio-3.5-full-tutorial ,
https://higgsfield.ai/creator-hub/help-center/ai-models/how-do-i-create-and-use-a-soul-id-character ,
https://higgsfield.ai/creator-hub/help-center/credits-and-usage/how-credits-work ,
https://www.scopeful.org/blog/higgsfield-pricing-2026 ,
https://creatify.ai/blog/higgsfield-ai-review-(2026)-is-it-worth-it .

**"Wavy AI" could not be identified as a creative studio.** Searches for "Wavy AI",
"wavy.ai" and "Wavy AI creative studio" return only a hairstyle try-on iPhone app
(https://apps.apple.com/us/app/wavy-ai/id6757876026), an Android photo filter app
(https://play.google.com/store/apps/details?id=com.wavy.photoeditor.aiart.artgenerator) and
an unrelated "Waver AI" video model site. None is in the Higgsfield class. The closest match,
and almost certainly what is meant, is **Weavy** (weavy.ai), the node-based creative studio
founded in Tel Aviv in 2024 and acquired by Figma; it is now **Figma Weave**
(https://weave.figma.com/ , https://www.figma.com/blog/welcome-weavy-to-figma/ ,
https://www.figma.com/solutions/figma-ai-tool-weave/ ,
https://www.figma.com/blog/connecting-figma-and-weave/ ,
https://help.figma.com/hc/en-us/articles/39582753756695-What-s-new-from-Config-2026).
This repo's README already describes its canvas as "Weavy-style". The rest of this document
treats Weavy as the second reference. **Decision for the user:** confirm that "Wavy AI"
means Weavy, or name the product meant.

### How they are organised

Higgsfield's home is a dark, media-first page. The top is a carousel of hero cards for the
newest capability; below it, a row of model chips (Seedance, Nano Banana Pro, Genjutsu,
Cinema Studio) and then rows of large looping video tiles grouped by theme, each with a
"Recreate" button. The Apps page groups about 40 one-click tools into Professional,
Enhance and Style, Face and Identity, Video Editing, Ads and Products, Games and Characters,
Trending Templates. Each app page is a three-step recipe (upload source, upload target,
generate) with a "Try it yourself" panel, a feature list and an FAQ. Cinema Studio is a
"Director's Panel": genre, era, tempo, camera body, lens, aperture, colour palette, lighting,
each a small list of named options rather than free numbers; a Claude chat writes prompts
into the prompt box but never presses Generate. References go up to 50 per generation.
Soul ID trains an identity once from 20 to 80 photos and is then selected by name; image
batch size is 1 to 4. Credits are the currency; the cost of a generation is shown on the
Generate button before confirmation; subscription credits expire monthly, packs in 90 days.

Weavy (Figma Weave) is a browser node canvas: every model is a node, every professional
edit (mask, composite, relight, grade, inpaint, depth) is a node, outputs branch and feed the
next node, and a finished graph can be "converted to a tool", a simplified one-panel UI with
only the inputs a colleague needs. Figma now exposes those tools as a curated list in the
design panel: swap the inputs, get consistent results, no prompting.

### Patterns we adopt (14)

1. **Media-first dark home.** Large looping tiles of real output, minimal chrome, one
   accent colour per workspace. Our tiles come from `brands/<ws>/runs/**` results; when
   a capability has never run, the tile shows its input and output types, never a stock
   image (Higgsfield home).
2. **Capabilities as cards, grouped.** The 52 catalogue kinds become cards in the
   catalogue's seven categories, with a "Pro" style badge replaced by our own three honest
   badges: Ready (port-mapped and models present), Needs setup (bound but no port map or a
   gated model), Gap (no backend). Never a fake tile (Higgsfield Apps).
3. **Three-step recipe per capability.** Each capability page reads: what you give, what
   you get, what it costs. The steps are the node's input ports, output ports and the
   `engine.yaml` estimate with its measured or assumed basis (Higgsfield app pages).
4. **A "Recreate" action on every result.** Any result tile opens the workflow that made it
   with the same inputs pre-filled, in a new run (Higgsfield home).
5. **Named options over free numbers.** Our presets (the look) and profiles (the craft)
   already are Cinema Studio's Director's Panel in our own words. The UI shows them as
   chips with a one-line description and a swatch, not a YAML key (Cinema Studio).
6. **A director that drafts, never fires.** Higgsfield's Claude chat updates the settings
   panels and puts prompts in the box for review. Our Director already does this
   (`session.say` rebuilds the workflow; a run needs the Run button and the gate). Keep
   it and make it visible: the describe bar shows the plan it produced before anything runs.
7. **Cost on the button.** Every Run button shows the stage estimate and its basis
   (measured or assumed) and the remaining budget, before confirmation (Higgsfield credits).
8. **Identity as a named asset.** Soul ID trains once and is picked by name. Our
   equivalent is a reference collection with `collection.json` and, when built, a RefMod or
   character sheet. The workspace shows them as named Characters with their rights status
   (Soul ID, Weavy elements).
9. **Batch as a first-class input.** Higgsfield takes up to 50 references; Weavy runs a
   graph over many inputs. Ours: a reference folder is a batch, and any single-image step
   can run once per item (the `each` contract below).
10. **Graph to tool.** Weavy's "convert to tool" is our template: a saved workflow whose
    input nodes are the only things a user fills. The 50 idea templates already are tools;
    the UI should present them as such, with a simple form (inputs only) and an "open the
    canvas" link for people who want the nodes (Weavy, Figma Weave tools).
11. **Every output feeds the next.** Weavy's core idea and our `combine`. The UI offers a
    "Continue with" strip under any completed stage: the catalogue nodes that accept this
    output type, with the fan-out toggle (Weavy).
12. **Side-by-side model choice.** Higgsfield lets you switch model without leaving the
    page. Where we have two routes to the same result (hosted image versus Krea 2 versus
    Klein on the pod), the capability card offers them as variants with cost and quality
    notes, not as separate cards (Higgsfield ai-video).
13. **Public inside of every project.** Higgsfield shows the prompts and assets behind each
    community project. Our run manifests already hold the bindings, seeds and prompts; the
    result view shows them (Higgsfield home, "Explore the inside of every project").
14. **Curated tool list inside another product.** Figma exposes Weave tools as a curated
    list. Our equivalent is the ElevenLabs voice agent's ten client tools and, later, an
    MCP surface; the catalogue is the single source for both (Figma Weave tools).

### Patterns we do not copy (5)

1. **Face swap on arbitrary real people.** Higgsfield's Face Swap, Video Face Swap and
   Recast accept any face. Our rule stays: a real face runs only with a written release
   recorded in `collection.json` (`consent: true`); otherwise the step is a declared gap.
2. **Soul ID style identity training on uploaded photos of real people by default.**
   Identity assets are built from owned or fictional references; a real person needs the
   release first, and the asset records it.
3. **Trending meme templates built on other people's IP** (Skibidi, K-pop idol, game
   styles). Grammar, never the original footage or a protected character.
4. **Expiring credits and daily free generations as engagement pressure.** Our budget is
   a hard cap a human raises in `engine.yaml`; estimates are honest about measured versus
   assumed. Whether to sell credits at all is a user decision (see Decisions).
5. **"Unlimited" tiers and marketing throughput claims.** We show measured seconds per
   unit and say when a figure is assumed. No "4.5M generations a day" copy.

---

## Part 2. Audit: what exists against what is asked

### A. Multi-brand

A brand is a folder `brands/<key>/` with `brand.yaml`; `workflow_author.clients()` and
`lib/studio.js listClients()` both discover any such folder, and `workflows/`,
`references/<name>/collection.json`, `runs/`, `styles/`, `assets/`, `calendar/` hang off it.
So adding a brand already works by creating a folder. What is missing is a scaffold, a
documented minimum `brand.yaml`, and a UI that does not say EPALLE.

Hardcoded today in `packages/studio-ui`: wordmark "EPALLE Studio" in `app/page.js`,
`app/c/[client]/page.js`, `app/layout.js` title, small captions in `app/library/page.js` and
`app/jobs/page.js`, the `isEpalle` volume flag in `api/runpod-status/route.js`, the
User-Agent `epalle-studio/1.0` (also in `packages/engine/runner.py`), env names
`EPALLE_LIBRARY_DB` and `EPALLE_WORKFLOW_DIR` in `api/library/route.js`, the adult notice in
`components/Canvas.js` ("never on Ongea Pesa or EPALLE work"), the agent name in
`components/VoiceDirector.js` and `packages/voice/elevenlabs_agent.py`, `package.json`
name `epalle-studio`, and `EPALLE-README.md`. Outside the UI: `SEED` and `SEED_COMBINED` in
`workflow_author.py` name the two brands; `ideas.yaml` evidence lines mention Ongea Pesa;
X01 compliance text names both brands.

A generic workspace needs: key, display name, accent, kind (music, fintech, fashion, agency),
logo master path, palette, voice, claim rules, languages; `references/` with rights;
`workflows/`; `runs/`; optional `styles/` and `calendar/`.

Also found: every UI API route shells to `uv run --with pyyaml python ...`. `uv` is not on
PATH on this machine, so Describe, Direct and Run fail from the browser today. The routes
need one spawn helper that honours `STUDIO_PYTHON` and falls back to `python`.

### B. The 50 ideas

`workflow_author.py --check` passes on all 50 templates because declared gaps are not
problems. The audit below counts three classes of "cannot run yet":

- **Declared gap**: the catalogue node has `backend.kind = gap`, or the pipeline names a
  step no node runs (`unmapped`). 16 gaps across 15 ideas.
- **Bound but not port-mapped**: the node names a ComfyUI workflow but there is no
  `.ports.json`, so the runner cannot bind inputs. 14 of 28 comfy kinds; 5 of them appear in
  templates (`caption-dataset`, `dataset`, `text-to-video`, `long-video`, `faceswap`).
- **Python step the engine does not run**: `backend.kind = python` but the kind is not in
  `runner.LOCAL_STEPS` (`voiceover`, `cut`, `captions`, `export`), so the runner writes a
  dry-run manifest and moves on. Affects `compositor` (14 ideas), `claim-check`, `hooks`,
  `transcribe`, `analytics`.

| Idea | Title | Steps | Gaps | What each gap needs |
|---|---|---|---|---|
| A01 | Brand engine for SMEs | 6 | 0 | compositor not run by engine |
| A02 | M-Pesa pay-per-post credits | 5 | 1 | `ongea-pesa` unmapped: a payment step (hosted API, Daraja) or drop from pipeline; compositor |
| A03 | Image API for agencies | 5 | 1 | `comfy-client` unmapped: register a python node on `packages/comfy-client/client.py`; compositor |
| E01 | AI creator lab community | 2 | 0 | course publisher is human-gated (by design) |
| E02 | Course on Whop | 2 | 0 | same |
| E03 | Original workflow packs | 1 | 1 | `register-workflow` unmapped: python node on `packages/library/tools/register_workflow.py` |
| E04 | Live cohort bootcamp | 2 | 0 | none |
| E05 | Agency incubator | 1 | 1 | `studio` unmapped: a handoff or docs step; rewrite pipeline |
| M01 | Full-length music video | 9 | 1 | `relight` video: a workflow; `long-video` needs ports.json |
| M02 | Artist visual retainer | 7 | 1 | `motion-graphics`: HyperFrames or Remotion renderer module; compositor |
| M03 | Spotify Canvas and loops | 5 | 0 | none |
| M04 | Release rollout kit | 6 | 0 | compositor; WhatsApp publish is human-gated |
| M05 | Artist digital double | 7 | 0 | consent release per artist |
| M06 | Event VJ loops | 4 | 0 | `text-to-video` needs ports.json |
| M07 | Label visual package | 8 | 1 | `motion-graphics`; compositor |
| M08 | Stock B-roll subscription | 4 | 0 | `text-to-video` needs ports.json |
| P01 | Own AI influencer | 8 | 0 | `dataset`, `caption-dataset`, `long-video` need ports.json; captioning needs LM Studio on pod |
| P02 | Merch with the AI model | 4 | 0 | compositor; print-on-demand is export only |
| P03 | Character licensing | 6 | 0 | none |
| P04 | Persona as a service | 5 | 0 | `dataset` ports.json; analytics not run by engine |
| P05 | Realism fix setup | 6 | 0 | none |
| P06 | Character boards and datasets | 5 | 0 | `dataset`, `caption-dataset` ports.json |
| P07 | Virtual try-on for fashion | 5 | 0 | none |
| P08 | Brand ambassador for local brands | 8 | 0 | compositor |
| P09 | Personalised persona greetings | 7 | 0 | none |
| S01 | RefMod or LoRA as a service | 5 | 1 | `lora-train`: ai-toolkit job outside ComfyUI (python module) or keep RefMod; `caption-dataset` ports.json |
| S02 | Product photography replacement | 7 | 1 | `relight` on images: remap pipeline to the existing `product-relight` step (image-edit) |
| S03 | Interior and architecture visuals | 5 | 0 | none |
| S04 | Archive restore and upscale | 5 | 1 | `restore`: a restoration workflow, or interim image-edit instruction |
| S05 | Training avatar videos | 8 | 1 | `motion-graphics` |
| S06 | Explainer videos | 4 | 1 | `motion-graphics` |
| S07 | Short-form dubbing | 7 | 1 | `translate`: hosted text adapter (OpenRouter) as a python module; transcribe not run by engine |
| S08 | Podcast to shorts | 6 | 0 | transcribe not run by engine |
| U01 | UGC ad pack | 7 | 0 | none |
| U02 | TikTok Shop product videos | 7 | 0 | none |
| U03 | Hook testing retainer | 6 | 0 | hooks not run by engine |
| U04 | Sheng and Swahili fintech ads | 8 | 0 | claim-check, compositor not run by engine |
| U05 | App install demo ads | 4 | 1 | `motion-graphics` |
| U06 | Multilingual spokesperson | 7 | 0 | consent release |
| U07 | Viral format remakes | 6 | 0 | hooks not run by engine |
| V01 | 1,000 images a day | 5 | 0 | compositor |
| V02 | Carousel from one photo | 5 | 0 | compositor; Klein 9B KV licence (BLOCKERS 3) |
| V03 | Listing to cinematic reel | 6 | 0 | `text-to-video` ports.json |
| V04 | Restaurant content retainer | 6 | 0 | compositor |
| V05 | E-commerce model photos | 4 | 0 | `faceswap` ports.json; fictional models only |
| V06 | WhatsApp Status daily | 4 | 0 | compositor; publish human-gated |
| V07 | Faceless shorts channel | 7 | 1 | `motion-graphics` |
| V08 | Thumbnail and cover retainer | 5 | 0 | compositor |
| X01 | Fictional 18+ persona subscription | 6 | 1 | `lora-train`; `dataset`, `caption-dataset` ports.json; hard gates |
| X02 | Compliance-first persona operations | 4 | 0 | analytics not run by engine |

Grouped for bulk closure:

| Group | Count | Closes with |
|---|---|---|
| G1 `motion-graphics` (M02, M07, S05, S06, U05, V07) | 6 | One python renderer module (HyperFrames or Remotion) registered as the node backend; until then an honest gap |
| G2 `relight` (M01 video, S02 image) | 2 | S02: pipeline to `product-relight`. M01: a video relight workflow, else gap |
| G3 `lora-train` (S01, X01) | 2 | A python job module for ai-toolkit on the pod, or keep the RefMod substitute and say so in the proposal |
| G4 unmapped business steps (A02, A03, E03, E05) | 4 | Two python nodes on existing modules (`comfy-client`, `register-workflow`); rewrite A02 and E05 pipelines |
| G5 `restore` (S04) | 1 | A restoration workflow, or interim `image-edit` with a restore instruction |
| G6 `translate` (S07) | 1 | A hosted text adapter module |
| G7 port maps missing (`dataset`, `caption-dataset`, `text-to-video`, `long-video`, `faceswap`) | 5 kinds, 9 ideas | Five `.ports.json` files, checked by `cli.py ports-check` |
| G8 python steps not run by the engine (`compositor`, `claim-check`, `hooks`, `transcribe`, `analytics`) | 5 kinds, 20 ideas | Extend `runner.LOCAL_STEPS` and `_run_local` (owned by W3) |
| G9 gated models | carousel, dataset | Klein 9B KV licence or fp8 profile (BLOCKERS 3), LM Studio for captioning (BLOCKERS 15); user actions |

### C. Describe to workflow

Two paths exist. `POST /api/author {mode: "brief"}` shells to
`workflow_author.py --brief`, which matches `BRIEF_RULES` (keyword regexes) to steps, then
`author()` wires them by port type, inserting input nodes and gaps. `POST /api/director`
shells to `cli.py say`, which starts a `Session`, applies `profiles.find` and preset
detection, then routes each later utterance through `session.intent` (keyword regexes for
scenes, angles, takes, seconds, look, kind, wardrobe, location, vfx, role, pick, mode, run,
undo; anything else is a `note`). Combination is `workflow_author.combine`, which prefixes
ids, merges the brand kit and matching briefs, and marries the previous part's final media
into the next part's first empty placeholder input; the UI exposes it as "Combine workflows"
with a pick list.

Tested against the user's example. `steps_from_brief("change the character in my 50
reference images to our persona, then make a carousel of 10 slides for each")` gives
`[refmod, carousel, compositor]`: "persona" matched the RefMod rule (a character is
created, not swapped), the 50 is dropped, "10 slides" does not reach `carousel.slides`,
"for each" means nothing, and "then" imposes no order beyond rule order. As session
utterances, "make carousels of 10 slides for each image", "use my 50 reference images from
persona-nadia" and "swap the character to nadia across all of them" all parse as `note`.

Exact intent gaps to close:

1. A **quantity and collection** rule: "my 50 reference images", "the folder persona-nadia",
   "these 50 photos" attaches a `reference-images` node pointing at
   `brands/<ws>/references/<name>/` and records the expected count.
2. A **swap** rule: "change the character", "character changer", "swap the face/character to
   X", "put our persona in" maps to the `character-swap` step (catalogue alias added on
   `klein-headswap`), and "change the outfit/clothes" to `wardrobe`, never to `refmod`.
3. A **per-item** rule: "for each", "per image", "per post", "each of them", "across all of
   them" appends `@each` to the step it modifies.
4. A **parameter** rule: "N slides" sets `carousel.slides`; "N seconds" already works for
   video; "N variants/takes" already works.
5. **Sequencing**: "then", "after that", "and next" keeps the user's order over rule order.
6. **Follow-on as an option**: "we have an option of generating carousels for each" should
   produce the first stage now and the second stage as a proposed continuation the UI
   offers after stage one completes, not as an immediate step. Contract: the describe
   response carries `continuations: [{step, each, params, estimate}]`.
7. **Questions back**: when a required input is unknown (which collection, how many slides,
   which persona), the response carries `questions: [{key, prompt, options}]` and the UI
   asks before creating the workflow.

Contract for the new endpoint, owned by W2:

```
POST /api/describe
{ "workspace": "epalle", "text": "...", "mode": "plan" | "create" | "direct",
  "answers": {"collection": "persona-nadia", "slides": 10}, "workflow": "<id, when extending>" }

200
{ "id": "<workflow id or null in plan mode>",
  "workflow": { ...studio.json... },
  "plan": { "steps": [{"kind", "each", "params", "backend", "status": "ready|needs-setup|gap"}],
            "gaps": [...], "estimate": {"usd", "basis", "items"}, "consent_required": bool },
  "continuations": [{"step": "carousel", "each": true, "params": {"slides": 10}, "estimate": {...}}],
  "questions": [{"key": "collection", "prompt": "Which reference collection?", "options": ["red-dress", ...]}],
  "route": "author" | "director",
  "reply": "one sentence in plain words" }
```

The route calls `python packages/engine/cli.py describe --client <ws> --text ... --json
[--mode ...] [--answer k=v ...] [--workflow <id>]` through `lib/python.js` (`STUDIO_PYTHON`
env, default `python`, `uv run --with pyyaml python` when `uv` resolves). `describe` decides
the route: if `profiles.find(text)` or a preset matches, it is a director piece and goes to
`session.say`; otherwise it is an author brief. Existing `/api/author` and `/api/director`
stay for the canvas and voice agent.

### D. The custom flow: batch in, per-item transform, per-item fan-out

**Goal.** A user drops N owned or fictional reference images of one character on a
character changer; every image is transformed; then, per output image, a carousel of 5 or
10 slides is generated, so N posts of 5 to 10 slides each.

**What runs step one.** Candidates in the catalogue, all consent-flagged:

| Node | ComfyUI workflow | Port map | Batch folder | Fit |
|---|---|---|---|---|
| `klein-headswap` (alias `character-swap`) | `icekiub/I2I_no_lora_faceswap_subs.json` | none yet | one image at a time | Best fit: swap the head to the persona from one face reference, no LoRA |
| `wardrobe` | `icekiub/Any_Clothes_9B_-_Subs_-_Icekiub_V1.3.json` | yes | one image, up to four clothing refs | Outfit change; output is a PreviewImage (temp), noted in the map |
| `klein-i2i` | `icekiub/Image_to_image_Klein_edit_-_Icekiub_v1.5.json` | none yet | native `mode: batch` folder | Recreate each reference with the character as subject; the node carries `adult: true` from the Icekiub pack, so it needs review before it is offered generally |
| `faceswap` | `icekiub/QWEN_ICY_Faceswap_-_SUBS_-_Icekiub_v1.json` | none yet | one image | Qwen face swap |
| `image-edit` | `icekiub/QWEN_IMAGE_UNLEASHED_ICEKIUB_SUBS_-_v1_.json` | yes | one image | Instruction edit, weaker identity |

None of the port-mapped workflows accepts a folder, and the runner today binds a list of
files to a single-image port as a list (`bindings[port] = files` when more than one image
arrives), which a `LoadImage` widget cannot take. So the loop belongs in the runner, and
a folder-native workflow (`klein-i2i` batch mode) is an optimisation for later.

**What runs step two.** `carousel` (`Carousel_Pose_changer_-_Icekiub_V1.7`, port-mapped):
one `LoadImage`, one pose per line in a `CR Prompt List`, one output image per line, so
`slides` becomes the number of pose lines the runner writes. It takes one image, so it too
runs once per item. The compositor then places exact copy and logo on every slide.

**The contract (implemented in this change).** A node fans out when `data.each` is true.
The author writes it from a step spelled `<step>@each` (pipelines in `ideas.yaml`, brief
rules, the describe parser and the UI all use the same spelling). `data.each_port` names the
iterated input when it is not the first required image or video port.
`workflow_author.iterated_port(node, cat)` and `is_each(node)` are the helpers every side
uses. Validation refuses `each` on inputs, brand kit, human decisions and publishers,
requires an image or video input to iterate, requires something feeding it, and relaxes the
pick "keep k of offered" check when a fan-out feeds the pick (the item count is a run-time
fact). `combine` preserves the flag. Tests: `tests/test_fan_out_contract.py`.

**Runner semantics (W3).** For a node with `each`:

1. Items are the files on the iterated port after `upstream_files` (a pick passes only its
   picks; a fan-out upstream passes its flattened outputs).
2. One ComfyUI submission per item per variant; other ports bind as today (the persona's
   face reference binds once to every item). Seed for item i, variant v is
   `base_seed + i * variants + v`, so a rerun of one item reproduces it.
3. Results record `items: [{index, group, input, files, sha256, prompt_ids, status,
   gpu_seconds_actual}]` and a flattened `files` for downstream. `group` is the upstream
   item index, carried through so a carousel slide knows which post it belongs to.
   Node status is `completed` only when every item completed; `partial` when some failed
   (downstream receives the completed items and the manifest names the failed ones).
4. Manifest layout: `brands/<ws>/runs/<workflow>/<node>/<run>/manifest.json` plus
   `items/<index>/<files>`. Export lays out `posts/<group>/slide-<n>.<ext>` so one folder is
   one post.
5. `engine.yaml` gains `max_items` (default 100) per node; a folder above it blocks with a
   clear note instead of submitting.

**Cost and approval.** `cost.estimate(kind, variants, seconds, items)` multiplies GPU
seconds by items; `carousel` is per output image, so items times `slides`. With the current
assumed figures (12 s wardrobe, 10 s carousel per image, A100 80GB rate), 50 images through
`wardrobe@each` then `carousel@each` with 10 slides is 50 x 12 + 500 x 10 = 5,600 GPU
seconds, about 1.6 GPU hours, and the estimate says "assumed" until a run replaces it. In
stage-approval mode each fan-out stage is one `engine_stage` task with that total; in auto
mode the single `engine_run` approval covers it; both stop at `budget_usd`. The item count
is known before the gate because the reference folder is on disk, so the approval shows
"50 items, est $X" and never a per-item surprise.

**The UI moment (W1).** When the first fan-out stage completes, the workflow page shows the
50 results as a grid and a "Continue with" strip: catalogue nodes that accept an image and
produce a set, each with a toggle "for each of the 50" (on by default), its parameter
(slides 5 or 10), and the estimate. Confirming calls `/api/describe` with
`mode: "create", workflow: <id>, text: "carousel@each slides=10"` (or `/api/author` mode
`extend`, W2's choice, one of the two), which appends the stage and returns to the canvas.
Nothing runs until Run.

**Rights gate.** Step one and step two both carry `consent: true` in the catalogue, so
`consent_required` is true on the workflow and the canvas shows the consent notice. The
runner (W3) adds the run-time half: before a live submission of a consent node, the
`reference-images` collection feeding the iterated port must have a `collection.json` with
`use: data`, `rights: owned | licensed`, and `consent: true` when the collection is a real
person; otherwise the node blocks with the reason. The fixture `brands/epalle/references/
red-dress/collection.json` (owned, fictional) satisfies it for dry runs.

**A template.** `brands/_templates/workflows/batch-character-to-carousels.studio.json`
(W3): `reference-images` (the batch), `reference-images` (the persona face, one file),
`character-swap@each`, `pick` (keep the good swaps), `carousel@each` with `slides: 10`,
`brand-kit`, `compositor`, `export`. The describe parser produces the same graph from the
user's sentence.

---

## Part 3. Design

### Goal

A general premium creative studio in the Higgsfield and Weavy class, for any brand and any
capability the catalogue can run, that keeps this repo's gates: rights, approval, budget,
honesty about what is measured. EPALLE and Ongea Pesa become the first two workspaces of
many. Describing what you want produces a runnable, costed workflow; batches of references
are first-class; every idea template is either runnable or says exactly what it is waiting
for.

### Information architecture

- **Home.** The describe bar at the top ("Describe what you want to make"), the workspace
  switcher, then media-first rows: Recent results (from runs), Capabilities (cards by
  category with Ready, Needs setup, Gap badges), Templates (the 50, as tools, filter by
  family and readiness), Characters (reference collections with rights status).
- **Explore.** All capabilities and templates, searchable, each with its three-step page:
  give, get, cost; variants where two routes exist; "Open on canvas".
- **Workspace** (`/w/<key>`, replaces `/c/<client>`): the workspace's results, workflows,
  characters, kit (palette, logo, voice) and a describe bar scoped to it.
- **Create.** The describe bar; the answer is a plan card (steps, gaps, estimate, consent)
  with Create, Adjust (opens the director chat) and Open on canvas.
- **Batches** (`/batches`): every fan-out run across workspaces, item progress, partials,
  cost actual versus estimate, "Continue with".
- **Library.** As today.
- **Jobs and Budget** (`/jobs`): control-plane tasks awaiting approval with estimates, the
  budget cap from `engine.yaml`, spend to date from manifests, and pod status. "Credits" as
  a sold unit is a user decision; internally the unit stays USD with a basis.

Premium means: one dark theme with a per-workspace accent, large media tiles with hover
playback, one typographic scale, chrome that disappears around media, empty states that
say what to do next, and every number on screen honest about its basis.

### Brand-agnostic rename plan

Proposed product name: **Director Studio** (the repo is `Director`). EPALLE stays the first
workspace, Ongea Pesa the second. **This is a decision for the user.** Mechanics, once
decided, in W1 and W5: wordmark and `layout.js` title; `package.json` name; User-Agent
`Director-studio/1.0` in the UI route and `runner.py`; env names `STUDIO_LIBRARY_DB` and
`STUDIO_WORKFLOW_DIR` with the `EPALLE_*` names still read as fallbacks; the adult notice
becomes "never on a client workspace's infrastructure"; the ElevenLabs agent display name;
`EPALLE-README.md` folded into `packages/studio-ui/README.md`; `SEED` stays as it is (it
seeds the two existing workspaces and tests depend on it).

---

## Part 4. Workstreams

Five independent workstreams. Each lists what it owns, what it must not touch, and the
commands that prove it. Shared contracts already in place: `data.each`, `data.each_port`,
the `@each` step suffix, `workflow_author.is_each`, `iterated_port`, `split_each`,
`EACH_BACKENDS`, and the `character-swap` step alias on `klein-headswap`.

### W1. Premium studio UI and brand-agnostic shell

Goal: the Home, Explore, Workspace, Batches, Jobs and Budget surfaces above; the dark
media-first theme; capability cards with honest badges; the plan card for the describe bar;
the results grid and "Continue with" strip after a fan-out stage; the `each` badge and item
progress on canvas nodes; the JS validator mirroring the Python `each` rules; no EPALLE
literal outside workspace data.

Owns: `packages/studio-ui/**` except the files W2 owns below. Includes `lib/studio.js`,
`globals.css`, all pages, all components, `api/{catalog,clients,generate,library,media,
pick,plan,run,runpod-status,runs,transcribe,voice,workflows}/**`, `package.json`,
`packages/studio-ui/README.md` (may absorb `EPALLE-README.md`).

Must not touch: `app/api/describe/**`, `app/api/author/route.js`, `app/api/director/
route.js`, `lib/python.js` (W2); `packages/studio-ui/catalog/nodes.json` (W4); anything in
`packages/engine`, `packages/strategy`, `brands/`, `tests/`.

JS mirror of the contract, in `validateWorkflow`: `data.each` must be boolean; a node with
`each` must have a backend of kind comfy, router, python or gap; it must have a non-optional
image, video or media input (or a valid `each_port`); that port must have an incoming edge;
the decide "keep k of offered" check is skipped when a feeder has `each`.

Acceptance:
```
npm run build --prefix packages/studio-ui
npm run lint --prefix packages/studio-ui
rg -n "EPALLE Studio|isEpalle" packages/studio-ui/client --glob '!**/node_modules/**'   # empty, or only in workspace data
```
And in a browser at http://localhost:3000: Home, /explore, /w/epalle, /batches, /jobs
render; a workflow with `each` nodes shows the badge; the describe bar posts to
`/api/describe` and renders the plan card from the contract shape (mock the response until
W2 lands).

### W2. Describe to workflow: endpoint, intents, combination

Goal: the `describe` CLI subcommand and `/api/describe` route implementing the contract in
Part 2C; the seven intent gaps closed; `steps_from_brief` producing `@each` steps, slide
counts and collections; `extend()` that appends a stage to an existing workflow (the
"Continue with" action); the `uv`-free spawn helper.

Owns: `packages/engine/session.py`, `packages/engine/intents.py` (new, the rule tables
moved out of `session.intent` and `workflow_author.BRIEF_RULES`), `packages/engine/cli.py`
(the `describe` subcommand only; do not change `run`), `packages/strategy/
workflow_author.py` (all of it from here on; keep `validate`, `is_each`, `iterated_port`,
`split_each` and `EACH_BACKENDS` behaviour stable, tests pin them), `packages/studio-ui/
client/app/api/describe/route.js`, `app/api/author/route.js`, `app/api/director/route.js`,
`packages/studio-ui/client/lib/python.js`, `tests/test_workflow_author.py`,
`tests/test_describe.py` (new), `tests/test_engine.py` where it tests intents.

Must not touch: `packages/engine/runner.py`, `cost.py`, `ports.py`, `director.py`,
`brands/**`, `packages/studio-ui/catalog/nodes.json`, any other studio-ui file,
`tests/test_fan_out_contract.py` (may add a test file, not edit this one).

Acceptance:
```
python -m pytest -q
python packages/strategy/workflow_author.py --check
python packages/engine/cli.py describe --client epalle --text "change the character in my 50 reference images from red-dress to our persona, then make a carousel of 10 slides for each" --json
```
The last must return steps `[reference-images, character-swap@each, carousel@each,
compositor, export]` (or `wardrobe@each` when the text says outfit), `carousel.params.slides
== 10`, `continuations` empty because "then" made it a step, and a `questions` entry when
the collection is not named. `tests/test_fan_out_contract.py` must still pass unchanged.

### W3. Batch fan-out runtime: runner loop, cost, manifests, port maps, template

Goal: the runner semantics in Part 2D (items, seeds, `group`, `partial`, `items/<index>/`
layout, `posts/<group>/` export, `max_items`); cost with items; the run-time rights gate on
consent nodes; `LOCAL_STEPS` extended so `compositor`, `claim-check`, `hooks`,
`transcribe` run locally (closes G8); port maps for `klein-headswap`, `klein-i2i` and
`faceswap`; the `batch-character-to-carousels` template; docs for batches.

Owns: `packages/engine/runner.py`, `packages/engine/cost.py`, `packages/engine/ports.py`,
`packages/engine/edit.py`, `brands/_presets/engine.yaml`, `workflows/icekiub/
I2I_no_lora_faceswap_subs.ports.json`, `workflows/icekiub/Image_to_image_Klein_edit_-_
Icekiub_v1.5.ports.json`, `workflows/icekiub/QWEN_ICY_Faceswap_-_SUBS_-_Icekiub_v1.ports.
json`, `brands/_templates/workflows/batch-character-to-carousels.studio.json` (new; the
only template file W3 touches), `tests/test_engine_runner.py`, `tests/test_engine_ports.py`,
`tests/test_fan_out_runtime.py` (new), `docs/engine/BATCHES.md` (new), `docs/engine/
PORT-MAPS.md`.

Must not touch: `packages/strategy/workflow_author.py` (use `wa.is_each` and
`wa.iterated_port`), `packages/engine/session.py`, `cli.py`, `director.py`,
`packages/studio-ui/**`, `brands/_business/ideas.yaml`, the other 50 templates, any other
`.ports.json`.

Acceptance:
```
python -m pytest -q
python packages/engine/cli.py ports-check
python packages/strategy/workflow_author.py --check
python packages/engine/cli.py run --client epalle --workflow <copy of the template pointed at brands/epalle/references/red-dress> --stage next
```
The dry run writes one manifest per fan-out node with `items[]` of length 3 (the fixture
has three images), `cost_estimate.items == 3`, and the export step's dry-run note names
`posts/<group>/`. A live-mode run against `FakeComfy` in tests proves per-item seeds, the
`partial` status and the rights block on a folder without `collection.json`.

### W4. The 50 ideas: close the gaps in bulk

Goal: every group in Part 2B either runs or states its exact blocker in the template and
the proposal. G1 renderer module or honest gap with a dated plan; G2 S02 remapped to
`product-relight`; G3 decision recorded per idea; G4 two python nodes and two pipeline
rewrites; G5 and G6 modules or interim mappings; G7 five port maps; G9 recorded as user
actions in BLOCKERS. Regenerate the templates, proposals, diagrams and WORKFLOWS.md.

Owns: `brands/_business/ideas.yaml`, `brands/_templates/workflows/**` (the existing 50,
regenerated with `--all-ideas`; never `batch-character-to-carousels.studio.json`),
`packages/studio-ui/catalog/nodes.json` (backends, new nodes, step aliases; keep the
`character-swap` alias), `workflows/**/*.ports.json` for `INFLUENCER_Dataset_AIO`, `AIO_-_
Uncensored_captioning_workflow`, `LTX2-T2V_-_ICY`, `3-Image-To-Long-Video`, and no others,
new backend modules under `packages/video/` and `packages/voice/translate.py`,
`packages/strategy/{workflow_catalog,proposals,idea_diagrams,business_os}.py`,
`packages/library/tools/register_workflow.py`, `docs/workflows/**`, `docs/proposals/**`,
`docs/diagrams/**`, `docs/business/**`, `tests/test_docs_generated.py`,
`tests/test_idea_diagrams.py`, `tests/test_business_os.py`, `tests/test_model_plan.py`,
`tests/test_ideas_gaps.py` (new: asserts the gap count per idea against a table in the
test, so a regression reopens a gap loudly).

Must not touch: `packages/engine/**`, `packages/strategy/workflow_author.py`,
`packages/studio-ui/client/**`, `brands/epalle/**`, `brands/ongea-pesa/**`, the three
`.ports.json` files W3 owns.

Acceptance:
```
python packages/strategy/workflow_author.py --all-ideas && python packages/strategy/workflow_author.py --check
python packages/strategy/workflow_catalog.py --check
python packages/engine/cli.py ports-check
python -m pytest -q
```
Plus a table in the PR description: idea, gaps before, gaps after, what closed each.

### W5. Multi-brand generalisation and docs

Goal: a scaffold that creates a workspace in one command; a documented minimum
`brand.yaml` and `collection.json`; docs that describe Director Studio (pending the name
decision) with EPALLE and Ongea Pesa as workspaces; BLOCKERS and ROADMAP updated with this
spec's items; skills updated to speak of workspaces.

Owns: `packages/strategy/workspace.py` (new: `new <key> --name --accent --kind`, `list`,
`check <key>`), `brands/_kit/**` (new: `brand.yaml.example`, `collection.json.example`,
`README.md`), `README.md`, `docs/ABOUT.md`, `docs/WHAT-THIS-DOES.md`, `docs/SETUP.md`,
`docs/ROADMAP.md`, `docs/BLOCKERS.md`, `docs/engine/DIRECTOR-ENGINE.md`,
`docs/engine/POSSIBILITIES.md`, `docs/LICENSING.md`, `.claude/skills/content-studio/
SKILL.md`, `.claude/skills/workflow-author/SKILL.md`, `packages/voice/elevenlabs_agent.py`
(display strings only), `tests/test_workspace.py` (new), `tests/test_docs_commands.py`.

Must not touch: `packages/studio-ui/**`, `packages/engine/**` except nothing,
`packages/strategy/workflow_author.py`, `brands/_business/**`, `brands/_templates/**`,
`brands/epalle/**`, `brands/ongea-pesa/**` (a scaffold test uses `tmp_path`).

Acceptance:
```
python packages/strategy/workspace.py new demo-brand --name "Demo Brand" --accent "#30E0A8" --kind fashion --dry-run
python -m pytest -q tests/test_workspace.py tests/test_docs_commands.py
python studio.py check
python packages/strategy/workflow_author.py --list      # shows the scaffolded workspace when created for real
```

### Order and merge

W1 to W5 run in parallel. W1 mocks `/api/describe` until W2 lands; W1's "Continue with"
strip calls the contract shape and works once W2 is in. W3 and W4 share no file. W4's
`nodes.json` edits and W3's runner do not overlap; W3 reads the catalogue through
`wa.load_catalog()`. The integration gate after all five merge:

```
python -m pytest -q
python packages/strategy/workflow_author.py --check
python packages/engine/cli.py ports-check
python studio.py check
npm run build --prefix packages/studio-ui
graphify update .
```

---

## Decisions only the user can make

1. **Product name.** Director Studio is proposed; EPALLE stays the first workspace.
2. **"Wavy AI".** Confirm it means Weavy (now Figma Weave), or name the product.
3. **Credits.** Whether to sell credits at all, or price per deliverable as the ideas do.
   Internally the unit stays USD with a measured or assumed basis either way.
4. **Real-person face swap.** Current answer: never without a written release recorded in
   `collection.json`; the runner will block it. Confirm, or define the release process.
5. **Klein 9B KV licence and LM Studio on the pod** (BLOCKERS 3 and 15) gate the carousel
   and captioning capabilities that the batch pattern and four persona ideas depend on.
6. **`klein-i2i` and the other `adult: true` Icekiub nodes**: offer them in Explore behind
   the existing 18+ gate, or hide them from the general catalogue.
7. **Budget.** `budget_usd` is 0; nothing live runs until it is raised (BLOCKERS 14).
