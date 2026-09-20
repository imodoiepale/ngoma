# A to Z setup

Everything below is either already done in this repo or is a step you run. Steps marked
**[you]** cannot be done for you: they need a login, a payment method, or an account
decision.

---

## 0. Prerequisites

Present on this machine (verified 2026-09-20):

`python 3.12` with `pyyaml`, `pillow` and `pytest`, `node`, `git`, `docker`, `ffmpeg`,
`yt-dlp`, `agent-reach`, `opencli`, `codex-cli`.

**`uv` is not on PATH here.** Every command in these docs is written for plain `python`.
If you install `uv`, `uv run --with pyyaml python <script>` runs the same scripts without a
global install. The `studio.py` tasks `plan`, `test`, `graph` and `loop` prefer `uv run`
when it is on PATH and otherwise run the same scripts with the interpreter that launched
`studio.py` (one printed line says so), so they work here once the three packages below are
installed. The studio
UI's API routes spawn Python through `lib/python.js`, which honours `STUDIO_PYTHON` and
falls back to `python` (`docs/BLOCKERS.md`, item 17).

```powershell
$env:PYTHONIOENCODING = 'utf-8'          # every session; several tools print non-ASCII
python -m pip install pyyaml pillow pytest
```

Still to install, when you reach the phase that needs it:

```bash
pip install gallery-dl            # Pinterest harvesting
pip install faster-whisper        # transcripts with no subtitle track; voice control
```

---

## 1. Rotate the leaked credentials **[you]**, first

Three live secrets sit in plaintext in the old source tree
(`Documents\Codex\2026-09-06\what-this-release-does-accepts-up-2\`). They were deliberately
not copied into this repo, but they are still valid and still on disk.

| What | Where | Action |
|---|---|---|
| `WHOP_API_KEY` (and `exp_CCRZF9mdhrPeip`) | `outputs/course/.env.whop` | revoke in Whop, issue a new Account API key |
| `RUNPOD_API_KEY` | `outputs/studio-ui/client/.env.local` | revoke in RunPod console, issue new |
| SSH private key `epalle_runpod_ed25519` | `outputs/` and `work/ssh/` | generate a new keypair, replace on the pod, delete the old |

Then store the new values in Windows DPAPI, never in a file:

```bash
python infra/runpod/set_secret.py runpod
python infra/runpod/set_secret.py openrouter
python infra/runpod/set_secret.py --list
```

Verify nothing leaked into git:

```bash
python studio.py check
git grep -inE "apik_|rpa_|BEGIN OPENSSH PRIVATE"
```

---

## 2. Open a workspace

EPALLE and Ongea Pesa are already there. For a new brand:

```bash
python packages/strategy/workspace.py new <key> --name "Display Name" --accent "#30E0A8" --kind fashion --dry-run
python packages/strategy/workspace.py new <key> --name "Display Name" --accent "#30E0A8" --kind fashion
python packages/strategy/workspace.py check <key>
```

Then, in `brands/<key>/`:

1. Put the logo master at the path under `logo.master` in `brand.yaml`. **[you]** It is
   composited, never generated, so there is no substitute for the real file.
2. Measure the palette from the real product and replace the placeholders. A palette taken
   from a document has been wrong twice in this repo (`docs/ABOUT.md`, "Measure, don't assume").
3. Write the copy under `positioning` (tagline, promise, CTA, attribution) and confirm the
   `claim_safety.disclosure` line.
4. Add references as folders under `references/`, each with a `collection.json` saying `use`,
   `rights` and `consent`. `references/README.md` in the workspace has the rules. A real
   person's face is data only with a written release. **[you]**
5. Add at least one style grammar under `styles/` before asking `brandkit` for a request;
   `check` warns until one exists.

`python packages/strategy/workspace.py list` shows every workspace with its kit status, and
`python packages/strategy/workflow_author.py --list` shows the same folders with their
workflows.

---

## 3. Generate your first post, no GPU, no infrastructure

```bash
python packages/brandkit/brandkit.py --list-ideas
python packages/image-router/router.py --plan-all
```

`--plan-all` costs nothing and tells you, for every seeded idea, which backend it needs and
what the hosted ones would cost.

To actually generate you need an OpenRouter key **[you]**, https://openrouter.ai/keys, then:

```bash
python infra/runpod/set_secret.py openrouter
python packages/image-router/router.py --idea 6 --backend hosted --live
python packages/compositor/compositor.py --base out/<result>.png --idea 6 --ratio 4:5
```

The compositor works today with no key at all. Try it on any image to see the brand system
applied.

---

## 4. Describe a piece and dry-run it

```bash
python packages/engine/cli.py say --client epalle --session s1 --text "a lookbook of one persona across a city evening, neon noir"
python packages/engine/cli.py say --client epalle --session s1 --text "add a scene at a market at dawn"
python packages/engine/cli.py run --client epalle --workflow <id> --stage next
python packages/strategy/workflow_author.py --brief "Sheng WhatsApp status ad for a mama mboga" --client ongea-pesa
```

`run` is dry-run by default: every stage writes a manifest under `brands/<ws>/runs/` saying
what it would do, and nothing is submitted. A live stage needs `--mode stage-approval` or
`auto`, a `budget_usd` above 0 in `brands/_presets/engine.yaml` **[you]**, and the control
plane's approval. `docs/engine/DIRECTOR-ENGINE.md` explains the modes.

---

## 5. ComfyUI: pick your compute

### 5a. Local (free, fastest iteration)

Needs an NVIDIA GPU. 12 GB VRAM runs the Klein stills; 24 GB or more for video.

```bash
git clone https://github.com/comfyanonymous/ComfyUI && cd ComfyUI
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
python main.py --listen 127.0.0.1 --port 8188
```

Install the packs the graph says you need, not a guess:

```bash
python packages/comfy-client/client.py deps workflows/icekiub/KleinDataset_-_Icekiub_freelo.json
python packages/comfy-client/client.py probe --backend local
python packages/comfy-client/client.py validate --all --backend local
```

`validate --all` lists exactly which node types and model files are missing.

### 5b. RunPod pod (existing infrastructure)

Volume `7y7jyghmua` (300 GB, US-KS-2) already holds models. `infra/runpod/README.md` is the
full runbook.

```bash
python infra/runpod/provision_pod.py          # cheapest GPU meeting the VRAM floor
python infra/runpod/audit_models.py           # what is missing for a given workflow
python infra/runpod/download_planned.py       # runs ON the pod, resumable
python packages/comfy-client/client.py probe --backend pod
python packages/engine/cli.py ports-check     # every engine step has a port map
```

Set `COMFY_POD_URL=https://<podid>-8188.proxy.runpod.net` in the environment first.
SageAttention is compiled per GPU architecture into a venv on a shared volume, so a pod on a
different card imports it fine and fails at runtime. `infra/runpod/install_sage_a100.sh` and
the guard scripts handle this; do not remove them.

### 5c. RunPod serverless: unproven, fix before relying on it

Endpoint `ugtmfoidpnh8pd` has never completed a generation; the only recorded result is
`{"status": "IN_QUEUE"}`. Prove it with the trivial graph first:

```bash
python packages/comfy-client/client.py smoke --backend serverless --live
```

Queued is not success. Do not mark this working until a history returns outputs.

---

## 6. Models: what to get first

`flux-2-klein-9b-fp8`, `flux2-vae` and `qwen_3_8b_fp8mixed` unlock the most: dataset
generation, carousel pose, the first frame for both video stacks, and faceswap.

**`flux-2-klein-9b-kv` is licence-gated on HuggingFace** and blocks `carousel_pose`, which
the batch pattern and four persona ideas depend on. Accept the licence on the model page
**[you]**, or use the fp8 variant. Two graphs also call an LM Studio server the pod does not
have (`docs/BLOCKERS.md`, item 15).

```bash
python infra/runpod/plan_models.py --online
```

---

## 7. References

```bash
python packages/ingest/yt_learn.py --channel kiubai --channel dgikaos --max-videos 6
python packages/ingest/pin_harvest.py --limit 10
python packages/ingest/ig_harvest.py <handle> --limit 12
python packages/engine/references.py list --brand epalle
python packages/engine/references.py possibilities
```

Instagram needs the OpenCLI browser extension enabled in Chrome or Edge and logged in
**[you]**. Check with `agent-reach doctor --json`; until then the harvester reports
`not_enumerable` rather than pretending.

Harvested material is `use: inspiration`, `rights: unclear`: it shapes prompts and never
reaches a node port. Rebuild the graph after harvesting:

```bash
python packages/library/graph_build.py
```

---

## 8. Voice

The microphone in the studio talks to the Director agent on ElevenLabs. The key stays in the
vault; the browser gets a short-lived signed URL.

```bash
python infra/runpod/set_secret.py elevenlabs
python packages/voice/elevenlabs_agent.py sync
python packages/voice/elevenlabs_agent.py signed-url
```

---

## 9. Publishing

1. Self-host Postiz (Node and Postgres) in `infra/postiz/`.
2. **[you]** Convert the brand's Instagram account to Professional and link it to a Facebook
   Page in Meta Business Suite. Auto-publishing carousels and Reels through the Graph API is
   impossible without this. Prove the pipeline on a throwaway Business account first.
3. OpenWA (pin v4.76.0; v5 is alpha) for WhatsApp Status, one session, conservative limits,
   human approval per send.
4. Everything defaults to `draft`. Scheduling requires your explicit yes.

```bash
python packages/publish/postiz.py channels
python packages/publish/postiz.py send --plan <plan.json> --limit 1
```

---

## Daily loop, once set up

```bash
python packages/image-router/router.py --plan-all         # what is queued
python packages/ingest/yt_learn.py --channel kiubai       # what is new
python packages/library/graph_build.py                    # refresh knowledge
python packages/strategy/workspace.py list                # every workspace still passes check
```
