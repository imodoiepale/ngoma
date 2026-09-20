# Blockers

Open items that gate real use. Each says who owns it. Items 16 to 23 are the decisions and
gaps opened by the general creative studio design
(`docs/superpowers/specs/2026-09-20-general-creative-studio-design.md`); 17, 21 and 22
were closed in the consolidation pass after its five workstreams landed, and 16 when the
product was named **Director**.

## Local proof — cleared 2026-09-19, no spend

These were verified on this machine. They are not live GPU proof.

- Local gates: `python -m pytest -q` (592 passed on 2026-09-19; 837 on 2026-09-20 with the workspace, fan-out and describe tests, while the Stage 4 workstreams are still landing), `python packages/engine/cli.py ports-check`, `python packages/strategy/workflow_author.py --check` (60 workflows, including S03 after the unknown-handle fix), `python studio.py check`.
- Workspaces: `python packages/strategy/workspace.py check epalle` and `check ongea-pesa` both pass (warnings only). A scaffold into a temporary root passes `check` (`tests/test_workspace.py`).
- Director dry-run session `rp1` on client `epalle`, workflow `a-lookbook-of-one-persona-across-a-city-evening-neon-noir`: every stage wrote `status: dry-run` manifests under `brands/epalle/runs/` (gitignored). Nothing was submitted.
- Fixture wardrobe stills: `brands/epalle/references/red-dress/` and `wardrobe-red-dress/` (owned, fictional, geometric colour fields, no real-person likeness).
- `--stage next` now treats a dry-run result as finished, and skips a stage that is only waiting on an unmade pick, so the runbook loop can reach later scenes.

Still required before a paid pod run: items 1 and 3, plus 14 and 15 below. `python infra/runpod/set_secret.py --list` on 2026-09-19 showed RunPod and Hugging Face unset. `provision_pod.py --status` was not run (no key). `budget_usd` in `brands/_presets/engine.yaml` is still 0.

## 1. Leaked credentials — YOU, before any live run
Three valid secrets sit in plaintext in `Documents\Codex\2026-09-06\what-this-release-does-accepts-up-2\`:
- `outputs/course/.env.whop` — `WHOP_API_KEY` + `WHOP_EXPERIENCE_ID=exp_CCRZF9mdhrPeip`
- `outputs/studio-ui/client/.env.local` — `RUNPOD_API_KEY`
- `outputs/epalle_runpod_ed25519` and `work/ssh/epalle_runpod_ed25519` — unencrypted SSH private keys

They were NOT copied into this repo and `.gitignore` blocks their shapes. They are still
valid. Rotate, then store new values via `infra/runpod/set_secret.py` (Windows DPAPI).

## 2. RunPod serverless has never completed a generation — ME, Phase 4 follow-up
Endpoint `ugtmfoidpnh8pd`. Only recorded result: `{"status":"IN_QUEUE"}`. Pod-side
execution IS proven (364.87 s / 45 images). Prove serverless with
`infra/runpod/smoke-test.json` before any scheduled workload depends on it: `python packages/comfy-client/client.py smoke --backend serverless --live` passes only on COMPLETED with files.

## 3. FLUX.2 Klein 9B KV is licence-gated — YOU
Blocks `carousel_pose`, which the router selects for 12 of the 30 seeded ideas, and the
`carousel` step the batch pattern (character swap, then a carousel per result) and the
persona ideas depend on. Accept the licence on the HuggingFace model page, or switch that
profile to the fp8 variant.

The same licence gates `lora-train` (S01, X01; `packages/engine/lora_train.py`), which
trains against the Klein 9B base. Concrete prerequisites, in order:
1. Accept the FLUX.2 Klein licence on Hugging Face with the account whose `HF_TOKEN` the
   pod will carry; ai-toolkit pulls the text encoder and VAE from that repo at run time.
2. `infra/runpod/setup-pod.sh` now clones `ostris/ai-toolkit` into
   `/workspace/epalle/ai-toolkit` and installs its requirements into the ComfyUI venv
   (idempotent; a failure there is a warning). Re-run it on the pod once.
3. The base file on the volume: `download_planned.py` with `HF_TOKEN` set.
The engine never trains: the `lora-train` step writes `config.yaml` and `launch.sh` in
dry-run and records `blocked` in live mode; a person runs `launch.sh` on the pod
(`infra/runpod/README.md`, "Training").

## 4. Instagram enumeration needs the OpenCLI extension — YOU
`agent-reach doctor --json` currently reports instagram `active_backend: null`. Enable the
OpenCLI extension in Chrome/Edge and log in to instagram.com. Until then `ig_harvest`
reports `not_enumerable`, which is correct behaviour, not a bug.

## 5. Instagram publishing needs a Business account — YOU  ← the only thing between you and a live post
Everything else in the publishing path is built and dry-run verified. Postiz auto-publish
goes through the Meta Graph API, which requires ALL of:
  1. the Instagram account converted to Professional (Business or Creator)
  2. it linked to a Facebook Page
  3. a Meta app with instagram_content_publish, pages_show_list and instagram_basic,
     live rather than in development mode
Then: deploy `infra/postiz/` on the VPS, connect the channel in the UI, and
`python packages/publish/postiz.py channels` will show its integration id.
Prove the pipeline on a throwaway Business account first.
Postiz auto-publish goes through the Graph API, which requires an IG Professional account
linked to a Facebook Page via Meta Business Suite. Creating and linking accounts is yours.

## 6. Two YouTube channels unresolved — YOU
"Airbrust" resolved to AiorBust and "Hearmaman" to Hearmeman (HearmemanAI), but both
YouTube handles 404 via yt-dlp. Their non-YouTube presence is confirmed and recorded in
`packages/ingest/channels.yaml`. Give me working URLs and I will enable them.

Separately: Icekiub's original channel `UCQDpVBFF5TSu3B27JvTA_oQ` was REMOVED by YouTube
for a Community Guidelines violation. KiubAI (`UCxRwH7p6H8dmLTvkzz6jm_w`) is the live
route and is already enabled.

## 7. WhatsApp Status is unofficial — YOUR RISK TO ACCEPT
`infra/openwa/` is built and bound to localhost, with an 8/day cap, a 10-minute gap and
per-send confirmation. But WhatsApp supports Status through no API at all, including the
official Business Platform. Automating it can get a number restricted. Use a dedicated
number you can afford to lose — not your personal one, and not the number customers use.
Never run OpenWA and Evolution API against the same number.

## 8. Your Pinterest script — YOU
You mentioned having one. `pin_harvest.py` uses gallery-dl; share yours and I will fold in
whatever it does better rather than duplicating it.

## 9. Docker ComfyUI stack is pinned stale — ME, Phase 4 follow-up
`comfyui-scail-docker` pins ComfyUI 0.3.26. SCAIL-2, LTX 2.3 and FLUX.2 Klein all need
current. Fork, unpin, install the pack set the graph lists, keep the per-architecture
SageAttention guard.

## 10. Licence conflict blocks bundling — YOU decide, before any paid distribution
Three licences in one shipped system. `work/h3/` (37 nodes, 10 workflows depend on it) is
**GPL-3.0**; `matrix-power-nodes` is MIT; `studio-ui` is MIT; the Icekiub workflow packs
carry **no stated licence at all**, which means no distribution rights by default.

Running any of it to make content you sell is fine. Bundling it into a course download,
a Docker image or a RunPod template is distribution and triggers GPL-3.0 source
obligations — and, for the Icekiub graphs, has no permission at all.

This repo also has no LICENSE file yet. See `docs/LICENSING.md`.

## 11. Node pack source is outside this repo — ME, when infra lands
The workflow JSONs are inert without their node packs. Two are not installable from the
ComfyUI registry and live only in the old Codex tree: `work/h3` (GPL-3.0) and
`work/matrix-power-nodes` (MIT, compiler-generated). Recorded in
`packages/library/node_pack_sources.yaml` with the other 27 registry-installable packs.

## 12. Not yet built
Phases 0-8 are built: ingestion, knowledge graph, four generation backends, compositing,
vision, strategy, publishing, voice and memory.

Still genuinely absent:
- ~~Hermes and Paperclip orchestration~~ — BUILT, and both turned out to be real projects
  (`NousResearch/hermes-agent` and `paperclipai/paperclip`, both MIT; verified against the
  GitHub API, not the SEO pages that surround them).

  `packages/orchestrator/` runs locally with no dependency on either: goals, tasks,
  budgets, typed approvals and a hash-chained audit log in SQLite, dispatching to four
  runtimes (`local`, `claude-code`, `codex-cli`, `hermes`). Local-first routing means a
  deterministic task runs the script rather than burning an LLM call.

  Neither Hermes nor Paperclip is INSTALLED here, and neither needs to be. Adapters exist
  (`hermes.py`, `paperclip.py`) and degrade to a clear instruction. Install Hermes when you
  want a persistent agent with its own memory; deploy Paperclip when more than one person
  needs to supervise. See `infra/hermes/README.md` and `paperclip.py setup`.
- ~~Analytics ingestion~~ — BUILT. `packages/analytics/` pulls from the Instagram Graph
  API and Postiz, attributes posts to briefs, and derives learnings into memory. It still
  needs the Instagram connection from item 5 before it sees real numbers; until then run
  `collect.py fixture` (the source is positional, not a flag), which tags every
  record `source=fixture` so nothing can be mistaken
  for measurement.
- **Enough posts to learn from.** The analysis refuses per-grammar claims below 6 posts
  per grammar, and it is right to: at 3 posts it reported a deliberately under-performing
  grammar as +28%. Expect roughly 4-6 weeks of consistent posting, in a NARROW rotation of
  grammars, before the learning loop says anything trustworthy.
- **A VLM pass in `packages/vision`.** Measurements work offline; semantic tagging
  ("this is a hands-at-work shot") still needs a model.
- **`packages/nodes/epalle-nodes` is an empty, documented stub.** Four custom ComfyUI nodes
  are designed but unwritten; see its README for why they go in a new pack rather than into
  `matrix-power-nodes`.

## 13. Deferred by decision
Meta AI via OpenWA as an image provider. Region-gated, no job ids, ToS-fragile, and it
would be the only provider with no reproducibility guarantee. Revisit only once Phases
0-6 are stable.

## 14. Engine budget is still 0 — YOU, before any live GPU stage
`brands/_presets/engine.yaml` has `budget_usd: 0`. The engine never raises it. At 0 the
control plane refuses every live stage before anything is submitted, including every
fan-out stage (a 50-item batch is one approval with one total). Raise it to 10 (or
another figure you accept), then add or re-add the worker so the copy in the control
plane matches:

```
python packages/orchestrator/control.py workers
python packages/orchestrator/control.py add-worker --name engine --runtime local --role "director engine" --budget 10
```

## 15. LM Studio is not on the pod — YOU, before captioning or the H3 reference route
Two graphs call an LM Studio server the pod does not have: `H3_Icy_image.json` and
`workflows/icekiub/captioning_workflow.json`. The lookbook proof without a character
role uses Krea 2 and does not need this. Dataset captioning (`caption-dataset`, used by
P01, P06, S01 and X01) does. For H3 and captioning: LM Studio on this PC over Tailscale,
or an OpenAI-compatible server on the pod. See `infra/runpod/README.md` section 5.

## 16. ~~Product name~~ — RESOLVED 2026-09-20
You chose **Director**. The README leads with it, and every product string now says it: the
UI wordmark (`components/Shell.js`, `components/Canvas.js`), the page titles (`app/layout.js`
and the two workspace pages), `package.json` name `director-studio` (npm names are lowercase),
the UI route User-Agent `director-studio/1.0`, the ElevenLabs agent (`AGENT_NAME = "Director"`
in `packages/voice/elevenlabs_agent.py`, with `brands/_presets/voice-agent.json` carrying the
same name; `tests/test_voice_agent.py` pins the two together), the design spec, the skills and
the docs. The git folder is still `ngoma` (a drum; that word never covered music videos,
WhatsApp Status, LoRAs, or the 50 offers) and stays so with the GitHub remote and the
`graphify-out` paths: a path, not a name. "Director Engine" (`docs/engine/DIRECTOR-ENGINE.md`,
`packages/engine/director.py`) keeps its name as the engine subsystem. Still W1: the
`epalle-studio/1.0` User-Agent in the Python adapters and the `EPALLE_*` env names (read as
fallbacks once `STUDIO_*` lands).

Also resolved: you confirmed **Weavy.ai** (node-based workflow creation) as the second
reference product alongside Higgsfield. The spec's Part 1 reading of it stands.

## 17. ~~`uv` is not on PATH, and two things still assume it~~ — RESOLVED 2026-09-20
Every doc command is written for plain `python`, and the two places that shelled out to `uv`
now fall back:
- `studio.py` tasks `plan`, `test`, `graph` and `loop` prefer `uv run --with ...` when `uv`
  is on PATH and otherwise run the same scripts with the interpreter that launched
  `studio.py` (`sys.executable`), printing one line saying so and which deps that
  interpreter must already have; `tests/test_studio_runner.py` pins both branches.
- The studio UI's API routes spawn through `lib/python.js`, which honours `STUDIO_PYTHON`
  and defaults to `python` (`docs/engine/DESCRIBE.md`).
Installing `uv` is optional; it only saves the one-time `pip install pyyaml pillow pytest`.

## 18. Credits or per-deliverable pricing — YOU
Higgsfield sells credits that expire; the 50 ideas price per deliverable. Internally the
unit stays USD with a measured-or-assumed basis either way, and `budget_usd` stays a hard
cap. Decide whether credits are sold at all before the Jobs and Budget page shows a unit.

## 19. Real-person face swap — YOU, confirm the policy
Current answer: never without a written release recorded in `collection.json`
(`consent: true`, and a note saying where the release is kept). The step catalogue flags
`faceswap`, `klein-headswap` (`character-swap`), `refmod-create`, `dataset` and `lipsync`
as consent steps; the runner's run-time half of the gate (block a live submission whose
collection lacks `use: data`, `rights: owned|licensed` and `consent: true` for a real
person) is W3's. Confirm this is the policy, or define the release process it should check.
No exception for public figures, customers, staff or friends.

## 20. `adult: true` nodes in the general catalogue — YOU
`klein-i2i` and the other Icekiub nodes marked `adult: true` are the best fit for
"recreate each reference with the character as subject". Decide whether Explore offers
them behind the existing 18+ gate or hides them from the general catalogue. Either way they
never run on a client workspace's infrastructure.

## 21. ~~Two `collection.json` fixtures start with a UTF-8 BOM~~ — RESOLVED 2026-09-20
`brands/epalle/references/red-dress/collection.json` and `wardrobe-red-dress/collection.json`
are BOM-free (byte-checked) and `workspace.py check epalle` no longer warns. The root cause
is also gone: `packages/engine/references.py read_collection` reads `utf-8-sig`, so a
`collection.json` written by PowerShell's `Set-Content -Encoding utf8` cannot fail a run
again (`tests/test_engine_references.py::test_read_collection_tolerates_a_utf8_bom`, which
also asserts the two fixtures stay BOM-free).

## 22. ~~Skills are mirrored from `shared-skills/approved/`~~ — RESOLVED 2026-09-20
`studio.py skills-sync` copies `shared-skills/approved/*` over `.claude/skills/` and
`.agents/skills/`. The approved copies of `content-studio` and `workflow-author` now hold the
workspace and `python` wording, and a sync was run: all three trees are identical, so the
next sync is a no-op. Edit `shared-skills/approved/` first, then sync; never the mirrors.

## 23. `relight` for video is the last capability gap across the 50 ideas — ME
Every other step the 50 ideas name either runs, is port-mapped, or states its blocker on the
template and the proposal (`tests/test_ideas_gaps.py` pins the count per idea). `relight` on
footage (M01's relit VFX pass; the `vfx relight` utterance) has no backend: the catalogue node
is `backend.kind: gap`. Stills are covered: S02's `product-relight` runs on the Qwen
`image-edit` node by instruction. Closing it needs an IC-Light video graph
(`kijai/ComfyUI-IC-Light` with a per-frame light map) or a Beeble SwitchLight-style
relighting workflow in `workflows/`, registered in `workflows/manifest.json` with a
`.ports.json` exposing `video`, `light_direction` and `prompt` (`docs/engine/PORT-MAPS.md`),
then the node's backend switched from `gap` to that workflow. The WanAnimate relight LoRA in
the two ICY WAN ANIMATE V4 graphs is not it: it matches a swapped character to the driving
clip and cannot change the light on footage. Until then the step stays a declared gap and
M01 sells without the relight pass.
