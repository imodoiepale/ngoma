# Blockers

Open items that gate real use. Each says who owns it.

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
`infra/runpod/smoke-test.json` before any scheduled workload depends on it: `uv run packages/comfy-client/client.py smoke --backend serverless --live` passes only on COMPLETED with files.

## 3. FLUX.2 Klein 9B KV is licence-gated — YOU
Blocks `carousel_pose`, which the router selects for 12 of the 30 seeded ideas. Accept the
licence on the HuggingFace model page, or switch that profile to the fp8 variant.

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
`uv run packages/publish/postiz.py channels` will show its integration id.
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
