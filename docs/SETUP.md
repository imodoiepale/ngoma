# A–Z setup

Everything below is either already done in this repo or is a step you run. Steps marked
**[you]** cannot be done for you — they need a login, a payment method, or an account
decision.

---

## 0. Prerequisites

Already present on this machine (verified 2026-09-12):

`docker 29.5.3` · `node` · `python 3.12` · `uv` · `ffmpeg` · `yt-dlp` · `agent-reach` ·
`opencli` · `mcporter` · `codex-cli 0.144.1`

Still to install, when you reach the phase that needs it:

```bash
uv tool install gallery-dl          # Pinterest harvesting
uv tool install faster-whisper      # transcripts with no subtitle track; voice control
```

---

## 1. Rotate the leaked credentials **[you]** — do this first

Three live secrets sit in plaintext in the old source tree
(`Documents\Codex\2026-09-06\what-this-release-does-accepts-up-2\`). They were
deliberately **not** copied into this repo, but they are still valid and still on disk.

| What | Where | Action |
|---|---|---|
| `WHOP_API_KEY` (+ `exp_CCRZF9mdhrPeip`) | `outputs/course/.env.whop` | revoke in Whop, issue a new Account API key |
| `RUNPOD_API_KEY` | `outputs/studio-ui/client/.env.local` | revoke in RunPod console, issue new |
| SSH private key `epalle_runpod_ed25519` | `outputs/` and `work/ssh/` | generate a new keypair, replace on the pod, delete the old |

Then store the new values in Windows DPAPI — never in a file:

```bash
uv run infra/runpod/set_secret.py runpod
uv run infra/runpod/set_secret.py openrouter
```

Verify nothing leaked into git:

```bash
git grep -inE "apik_|rpa_|BEGIN OPENSSH PRIVATE"
```

---

## 2. Generate your first post — no GPU, no infrastructure

```bash
export PYTHONIOENCODING=utf-8

uv run --with pyyaml packages/brandkit/brandkit.py --list-ideas
uv run --with pyyaml packages/image-router/router.py --plan-all
```

`--plan-all` costs nothing and tells you, for all 30 seeded ideas, which backend each
needs and what the hosted ones would cost (currently 19 comfy / 11 hosted / ~$1.08).

To actually generate you need an OpenRouter key **[you]** — https://openrouter.ai/keys —
then:

```bash
export OPENROUTER_API_KEY=...
uv run --with pyyaml packages/image-router/router.py --idea 6 --backend hosted --live
uv run --with pillow --with pyyaml packages/compositor/compositor.py \
    --base out/<result>.png --idea 6 --ratio 4:5
```

The compositor works today with no key at all — try it on any image to see the brand
system applied.

---

## 3. ComfyUI — pick your compute

### 3a. Local (free, fastest iteration)

Needs an NVIDIA GPU. 12 GB VRAM runs the Klein stills; 24 GB+ for video.

```bash
git clone https://github.com/comfyanonymous/ComfyUI && cd ComfyUI
uv venv && uv pip install -r requirements.txt
python main.py --listen 127.0.0.1 --port 8188
```

Install the packs the graph says you need — not a guess:

```bash
uv run packages/comfy-client/client.py deps workflows/icekiub/KleinDataset_-_Icekiub_freelo.json
uv run packages/comfy-client/client.py probe --backend local
uv run packages/comfy-client/client.py validate --all --backend local
```

`validate --all` lists exactly which node types and model files are missing.

### 3b. RunPod pod (existing infrastructure)

Volume `7y7jyghmua` (300 GB, US-KS-2) already holds 12 models / 103 GB.

```bash
uv run infra/runpod/provision_pod.py          # cheapest GPU meeting the VRAM floor
uv run infra/runpod/audit_models.py           # what's missing for a given workflow
uv run infra/runpod/download_planned.py       # runs ON the pod, resumable
export COMFY_POD_URL=https://<podid>-8188.proxy.runpod.net
uv run packages/comfy-client/client.py probe --backend pod
```

SageAttention is compiled per GPU architecture into a venv on a **shared** volume, so a
pod on a different card imports it fine and fails at runtime. `infra/runpod/install_sage_a100.sh`
and the guard scripts handle this — do not remove them.

### 3c. RunPod serverless — unproven, fix before relying on it

Endpoint `ugtmfoidpnh8pd` has **never completed a generation**; the only recorded result
is `{"status": "IN_QUEUE"}`. Prove it with the trivial graph first:

```bash
uv run packages/comfy-client/client.py smoke --backend serverless --live
```

Queued is not success. Do not mark this working until a history returns outputs.

---

## 4. Models — what to get first

`flux-2-klein-9b-fp8` + `flux2-vae` + `qwen_3_8b_fp8mixed` unlock the most: dataset
generation, carousel pose, the first frame for both video stacks, and faceswap.

**`flux-2-klein-9b-kv` is licence-gated on HuggingFace** and blocks `carousel_pose`
specifically. Accept the licence on the model page **[you]**, or use the fp8 variant.

---

## 5. References

```bash
uv run --with pyyaml packages/ingest/yt_learn.py --channel kiubai --channel dgikaos --max-videos 6
uv run --with pyyaml packages/ingest/pin_harvest.py --limit 10
uv run --with pyyaml packages/ingest/ig_harvest.py <handle> --limit 12
```

Instagram needs the **OpenCLI browser extension enabled in Chrome/Edge and logged in**
**[you]**. Check with `agent-reach doctor --json`; until then the harvester reports
`not_enumerable` rather than pretending.

Rebuild the graph after harvesting:

```bash
uv run packages/library/graph_build.py
```

---

## 6. Publishing — not yet built

Phase 6. When you reach it:

1. Self-host Postiz (Node + Postgres) in `infra/postiz/`.
2. **[you]** Convert the Ongea Pesa Instagram account to Professional and link it to a
   Facebook Page in Meta Business Suite. Auto-publishing carousels and Reels through the
   Graph API is impossible without this. Prove the pipeline on a throwaway Business
   account first.
3. OpenWA (pin v4.76.0 — v5 is alpha) for WhatsApp Status, one session, conservative
   limits, human approval per send.
4. Everything defaults to `draft`. Scheduling requires your explicit yes.

---

## Daily loop, once set up

```bash
export PYTHONIOENCODING=utf-8
uv run --with pyyaml packages/image-router/router.py --plan-all     # what's queued
uv run --with pyyaml packages/ingest/yt_learn.py --channel kiubai   # what's new
uv run packages/library/graph_build.py                              # refresh knowledge
```
