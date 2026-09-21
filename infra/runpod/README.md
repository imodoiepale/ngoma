# RunPod — Director Studio GPU

ComfyUI for Director Studio runs on the official RunPod image `runpod/comfyui:cuda12.8`, bound to a network volume. Models, custom nodes, and workflows live on the volume. `one_click.py` is what makes a new pod actually use them.

Secrets: Windows DPAPI via `set_secret.py`, or gitignored `.env.local`. Not in this file.

## Current (this account)

Defaults in `runpod_api.py` / `active-pod.json`. Override with `RUNPOD_VOLUME_ID` / `RUNPOD_POD_ID` if a create replaces the pod.

| Resource | Id | Notes |
|---|---|---|
| Network volume | `t023496m3n` | 600 GB, US-NC-2 |
| Pod | `u0rccyaj40w5no` (`director-comfyui`) | `runpod/comfyui:cuda12.8` |
| ComfyUI | https://u0rccyaj40w5no-8188.proxy.runpod.net | 8188 proxy |
| Last GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition | USD 1.69/h while RUNNING |

```powershell
python infra/runpod/one_click.py
python infra/runpod/one_click.py --create --full
python infra/runpod/provision_pod.py --status
python infra/runpod/provision_pod.py --stop u0rccyaj40w5no
python infra/runpod/runpod_api.py whoami
python infra/runpod/runpod_api.py pods
python infra/runpod/runpod_api.py volumes
```

`--create` provisions the official template if no director pod is RUNNING. `--full` installs node packs, H3 extras, and priority downloads. `director-template.json` is the image spec (ports 8188/8080/8888/22). Comfy UI Refresh does not pick up a newly added model folder — bind + restart is required.

SSH keys tried in order: `~/.ssh/director_runpod`, then `infra/epalle_runpod_ed25519`. RunPod remaps public IP and port 22 on each start.

## Volume layout

`extra_model_paths.yaml` points the template at the persistent store:

| Path | Role |
|---|---|
| `/workspace/epalle/models` | Weights (`is_default: true`, including `upscale_models`) |
| `/workspace/epalle/ComfyUI` | Template runtime; `custom_nodes/` on the volume |
| `/workspace/epalle/workflows` | Repo `workflows/` as shipped by `sync-workflows.ps1` |
| `/workspace/epalle/node-packs` | Shipped Icekiub packs staged for install |
| `/workspace/epalle/workflow-api` | Graphs admitted by the serverless handler |
| `/workspace/epalle/state` | Idempotency / job state |

Serverless (if used) accepts only named graphs in `workflow-api`. Requests default to `dry_run=true`. MATRIX paid provider nodes are rejected; the original MATRIX graph starts with `live=false`. `RUNPOD_ENDPOINT_ID` is empty unless you set it — do not fall back to the old EPALLE endpoint.

## Node packs

`setup-pod.sh` / `install-template-nodes.py` clone packs from `node_packs` in `workflows/manifest.json`. Group 1 is required for the port-mapped engine workflows; a requirements failure there stops setup. Group 2 is the rest of the library; a failure there is reported and skipped.

Scripts enforce:

- `comfyui-unsafe-torch` is never installed (it patches `torch.load`).
- `icynodes` replaces `betterimage_loader`, `ICYLM`, `icymegapixelresize`, and `ComfyUI-IcyHider-icekiub` (same class names).
- The seitanism H3 fork is installed instead of `NikoDemon80/ComfyUI-H3-Motion-Context`.

`comfyui_sam3` (SAM3Segmentation, ICY WAN ANIMATE V4) still has no verified repository. Those two graphs will not load until it does.

## Models

```powershell
python infra/runpod/plan_models.py --online
python infra/runpod/set_secret.py hf
python infra/runpod/set_secret.py --list
```

`download_planned.py` runs on the pod (invoked by `--full`). It skips NVFP4 / INT4 on non-Blackwell GPUs unless `--all`. Creator-private LoRAs stay BLOCKED by design. FLUX.2 Klein 9B KV is licence-gated on Hugging Face for the token you store.

`setup-pod.sh` clones `ostris/ai-toolkit`. The `lora-train` step writes `config.yaml` and `launch.sh` under `brands/<key>/runs/training/`; a person runs `launch.sh` with the pod up.

## Verification

- Pod-side execution is proven: 364.87 s for 45 Klein stills; `klein-t2i-test.json` at 8.1 s/image (`brands/_presets/engine.yaml`, `basis: measured`).
- Model integrity was verified for the original twelve files on persistent storage; the current volume is 600 GB and still accumulating the download plan.
- Next.js studio production build: passed.
- Scale-to-zero serverless: never `COMPLETED` with files. Treat as unproven. See `docs/BLOCKERS.md` item 2.
- Probe before treating a graph as OK:

```powershell
python packages/comfy-client/client.py probe --backend pod --url https://u0rccyaj40w5no-8188.proxy.runpod.net
python packages/comfy-client/client.py validate --all --backend pod --url https://u0rccyaj40w5no-8188.proxy.runpod.net
```

`OK` = node types and model files present. `BLOCKED` = missing. `UNVERIFIED` = unreachable. `client.py run --live` refuses `UNVERIFIED`.

Engine dry-run and live stage-approval sequences: [`docs/SETUP.md`](../../docs/SETUP.md), [`docs/BLOCKERS.md`](../../docs/BLOCKERS.md). Local gates before GPU: `python -m pytest -q`, `python packages/engine/cli.py ports-check`, `python packages/strategy/workflow_author.py --check`, `python studio.py check`.

## Legacy (old EPALLE account — do not use)

These IDs are another RunPod user. `runpod_api.py` does not fall back to them.

| Resource | Id | Was |
|---|---|---|
| Network volume | `7y7jyghmua` (`epalle-studio`) | 200 GB, US-KS-2 |
| Pod | `rl4rktj2fpnphn` | A100-SXM4-80GB, USD 1.39/h, 2026-09-06 |
| Pod | `eeoldxyxnd0o1z` | RTX A6000 48 GB; host had no free GPU after 2026-09-06 |
| Serverless template | `s7eg4zafj9` (`epalle-comfy-serverless-v1`) | — |
| Endpoint | `ugtmfoidpnh8pd` (`epalle-studio-api`) | min 0 / max 1 workers; only recorded result `IN_QUEUE` |

`runpod-endpoint.json` still carries `7y7jyghmua` from that account. Leave it; do not point current scripts at it.
