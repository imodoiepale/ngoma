# EPALLE RunPod deployment

## One-click Director pod (current account)

Do not use the old EPALLE volume/pod IDs below. Current resources are network volume `t023496m3n` (600 GB, US-NC-2) and pod `u0rccyaj40w5no` (`runpod/comfyui:cuda12.8`, ComfyUI v0.33.4).

From the repo on your machine, this provisions the official ComfyUI template if needed, binds every model folder on the volume (including `upscale_models`) into Comfy, restarts it so loaders see the files, and can install node packs plus resume downloads:

```powershell
python infra/runpod/one_click.py
python infra/runpod/one_click.py --create --full
```

`director-template.json` is the RunPod image spec (official ComfyUI + ports). The models, custom nodes, and workflows live on the network volume; `one_click.py` is what makes a new pod actually use them. Comfy UI Refresh does not pick up a newly added model folder — bind + restart is required.

## Provisioned resources

- Persistent network volume: `epalle-studio` (`7y7jyghmua`), 200 GB, US-KS-2.
- Development Pod (current): `rl4rktj2fpnphn`, NVIDIA A100-SXM4-80GB at USD 1.39/h, created 2026-09-06 by `provision_pod.py` and attached to the volume (`active-pod.json`). It is stopped when idle.
- Development Pod (original): `eeoldxyxnd0o1z`, RTX A6000 48 GB. Its host has had no free GPU since 2026-09-06, so it cannot resume; it is kept only because the volume history references it.
- Serverless template: `epalle-comfy-serverless-v1` (`s7eg4zafj9`).
- Scale-to-zero endpoint: `epalle-studio-api` (`ugtmfoidpnh8pd`), minimum workers 0 and maximum workers 1.
- ComfyUI 0.34.0 and CUDA were validated on the development Pod.
- Twelve model files (103.25 GB) were verified by exact size and SHA-256 and remain on persistent storage.

The 200 GB network volume continues to cost about USD 14 per month at the configured USD 0.07/GB/month rate. A stopped Pod does not incur hourly GPU runtime charges.

## SSH access

The generated private key is `../epalle_runpod_ed25519`; the public key is `../epalle_runpod_ed25519.pub`. Keep the private key private.

After starting the Pod, obtain its current public IP and TCP mapping for port 22 from RunPod, then connect from this directory:

```powershell
ssh -i ..\epalle_runpod_ed25519 -p <PORT> root@<PUBLIC_IP>
```

RunPod may assign a new public address or mapped port each time the Pod starts, so fetch the current values before connecting.

## Runtime layout

- `/workspace/epalle/ComfyUI`: ComfyUI runtime; `custom_nodes/` holds every node pack
- `/workspace/epalle/models`: persistent model store (`extra_model_paths.yaml` points ComfyUI at it)
- `/workspace/epalle/workflows`: the repo's `workflows/` tree as shipped by `sync-workflows.ps1`; graphs are copied into `ComfyUI/user/default/workflows/EPALLE` for the UI
- `/workspace/epalle/node-packs`: the repo-shipped Icekiub packs (`icynodes`, `ComfyUI-IcyQwen3`, `ComfyUI-icyTikTokDownloader`) staged by `sync-workflows.ps1` and installed by `setup-pod.sh`
- `/workspace/epalle/workflow-api`: workflows admitted by the serverless handler
- `/workspace/epalle/state`: idempotency and job state

The serverless handler accepts only named workflows installed in `workflow-api`. Requests default to `dry_run=true`. MATRIX paid provider nodes are rejected by the serverless handler; the original MATRIX graph also starts with `live=false`.

## Node packs

`setup-pod.sh` clones two groups of packs, both derived from `node_packs` in `workflows/manifest.json`. Group 1 is what the 14 port-mapped engine workflows need (Comfyroll, Inspire, Impact Subpack, krea2-controlnet, PainterI2V, the three H3 refmod packs, the MiniMax latent upscaler, MAINodes, and the packs that were already there). Group 2 is the rest of the library (efficiency nodes, FaceAnalysis, essentials, Logic, Krea2T enhancer, MediaMixer, LTXVideo, WanAnimate preprocess and enhancer, the NVIDIA RTX nodes, MultiGPU, UltimateSDUpscale, StarNodes, mikey, WAS, SAM3, SolAttn). A requirements failure in group 2 is reported and skipped; in group 1 it stops the setup.

Three rules the scripts enforce:

- `comfyui-unsafe-torch` is never installed. It patches `torch.load` so any model file can run code.
- `icynodes` replaces `betterimage_loader`, `ICYLM`, `icymegapixelresize` and `ComfyUI-IcyHider-icekiub`. They register the same node class names, so the four standalone folders are removed wherever `icynodes` is installed.
- The seitanism H3 fork is installed instead of `NikoDemon80/ComfyUI-H3-Motion-Context`; both register the same H3 classes.

Still unresolved: the `comfyui_sam3` registry id (version 0.2.1, `SAM3Segmentation`, used by the two ICY WAN ANIMATE V4 graphs) has no verified repository, so those two graphs will not load until it is found. See the comment block in `setup-pod.sh`.

## Verification status

- ComfyUI startup and `/system_stats`: passed on the RTX A6000 Pod.
- Model integrity: passed for all twelve files.
- Next.js studio production build: passed.
- Serverless endpoint creation and persistent-volume attachment: passed.
- Scale-zero dry request: still queued because no compatible worker capacity was admitted during verification. Treat this as an unresolved capacity test, not a successful generation.
- Development Pod resume on 2026-09-06: RunPod reported no free GPU on the assigned host. Creating a replacement 48 GB Pod in US-KS-2 also reported no available instance. `provision_pod.py` then created the A100 pod above on the same volume.
- Pod-side execution is proven: 364.87 s for 45 images, and `klein-t2i-test.json` at 8.1 s per image (the one `measured` figure in `brands/_presets/engine.yaml`).

No paid WaveSpeed generation was started. The serverless endpoint has still never completed a generation (`docs/BLOCKERS.md`, item 2).

## Proving the Director Engine end to end

This is the sequence for the first paid proof of the engine on the pod: a lookbook of one persona, two scenes, three angles each, one 4 second clip per scene, cut and exported locally. Steps 0 to 2 cost nothing. Steps 7 and 8 are the only spend: six Krea 2 stills and two Wan 2.2 clips come to roughly 15 GPU minutes on the planning figures in `engine.yaml`, under USD 2 at USD 1.39/h, plus the minutes the pod takes to boot and load models. Every command below is checked by the docs-command test in `tests/`, so a flag that is not in a script's `--help` fails the suite.

Conventions: run from the repo root in PowerShell. `uv` is not on PATH on this machine, so every command uses `python` directly. Set `$env:PYTHONIOENCODING='utf-8'` first, or the console mangles the engine's output.

### 0. Before any spend

From `docs/BLOCKERS.md`:

1. Rotate the leaked RunPod API key in the RunPod console, then store the new one. The store is Windows DPAPI, outside the repo, and every adapter reads it through the vault:

   ```powershell
   python infra/runpod/set_secret.py runpod
   ```

2. Accept the FLUX.2 Klein licence on the Hugging Face model page with the account whose token you store, otherwise `download_planned.py` gets 403 on the Klein files:

   ```powershell
   python infra/runpod/set_secret.py hf
   python infra/runpod/set_secret.py --list
   ```

3. Raise `budget_usd` in `brands/_presets/engine.yaml` from 0 to 10. The engine never raises it itself, and at 0 every live stage is refused by the control plane before anything is submitted. The figure is copied into the control plane's `engine` worker the first time the engine proposes a task; if that worker already exists from an earlier run, its budget stays at the old value, so check and re-add it (re-adding keeps what it has spent):

   ```powershell
   python packages/orchestrator/control.py workers
   python packages/orchestrator/control.py add-worker --name engine --runtime local --role "director engine" --budget 10
   ```

### 1. Local gates

All four must pass before the pod is started:

```powershell
python -m pytest -q
python packages/engine/cli.py ports-check
python packages/strategy/workflow_author.py --check
python studio.py check
```

`ports-check` proves every engine step in the catalogue has a port map; `--check` validates every saved studio workflow; `studio.py check` fails if anything secret-shaped is tracked by git.

### 2. Dry run end to end, no GPU

Make a fixture reference collection so the wardrobe step attaches. Put two or three of your own images in `brands/epalle/references/red-dress/` and write `brands/epalle/references/red-dress/collection.json` by hand:

```json
{"name": "red-dress", "use": "data", "rights": "owned", "kind": "image", "consent": false, "source": "manual", "notes": ["fixture for the RunPod proof"]}
```

Start the session. The first utterance only sets the kind of piece and the look; scene count, angles and clip length are separate utterances, one intent each:

```powershell
python packages/engine/cli.py say --client epalle --session rp1 --text "a lookbook of one persona across a city evening, neon noir"
python packages/engine/cli.py say --client epalle --session rp1 --text "2 scenes"
python packages/engine/cli.py say --client epalle --session rp1 --text "3 angles"
python packages/engine/cli.py say --client epalle --session rp1 --text "clips 4 seconds long"
python packages/engine/cli.py say --client epalle --session rp1 --text "wardrobe from my red-dress"
```

The first reply reads `Started "<workflow-id>"`; that id is `--workflow` below. The workflow and its session file are under `brands/epalle/workflows/`. Now run every stage in dry-run mode. The stages the director builds for this brief are `refs`, `storyboard`, `scene1`, `scene1-dress`, `scene1-motion`, `scene2`, `scene2-dress`, `scene2-motion`, `edit` (cut and captions; the lookbook profile has no narration, so no voiceover) and `publish`, which holds only the `export` step unless you ask for a publishing step. `--stage next` picks the first stage with unfinished work, so repeat it until the output says every stage has completed:

```powershell
python packages/engine/cli.py run --client epalle --workflow <workflow-id> --stage next --mode dry-run
```

Every node writes `brands/epalle/runs/<workflow-id>/<node>/<run>/manifest.json` with `status: dry-run`, the workflow it would submit, the bindings that would go into the port map, the seeds and the cost estimate. Nothing is submitted. `brands/*/runs/` is gitignored.

### 3. Pod

Check what exists, then bring up the A100:

```powershell
python infra/runpod/provision_pod.py --status
```

Prefer resuming `rl4rktj2fpnphn` (A100 80 GB, USD 1.39/h): the venv on the volume has SageAttention compiled for that architecture, and a pod on a different GPU family would import it and fail at runtime (`install-sageattention.sh` detects that and rebuilds, which costs paid minutes). `provision_pod.py` has no resume flag; resume the existing pod from the RunPod console, or, if its host has no free A100, create a new pod on volume `7y7jyghmua` in the same family:

```powershell
python infra/runpod/provision_pod.py --plan --min-vram 80 --max-price 1.50
python infra/runpod/provision_pod.py --min-vram 80 --max-price 1.50
```

`--plan` prints the choice and creates nothing. Then, with the pod RUNNING and its public IP and mapped SSH port from the console, ship the repo's workflow tree and the Icekiub packs:

```powershell
.\infra\runpod\sync-workflows.ps1 -HostName <PUBLIC_IP> -Port <PORT>
```

This stages `workflows/` at `/workspace/epalle/workflows` and the three shipped packs at `/workspace/epalle/node-packs`, then installs the packs into `custom_nodes` if ComfyUI is already there. Copy the setup scripts up and run them. The working copy is CRLF on Windows (`core.autocrlf`), so strip the carriage returns on the pod before bash sees them:

```powershell
scp -i .\epalle_runpod_ed25519 -P <PORT> infra\runpod\setup-pod.sh infra\runpod\install-sageattention.sh infra\runpod\download_planned.py root@<PUBLIC_IP>:/workspace/epalle/
ssh -i .\epalle_runpod_ed25519 -p <PORT> root@<PUBLIC_IP> "sed -i 's/\r$//' /workspace/epalle/*.sh /workspace/epalle/*.py && bash /workspace/epalle/setup-pod.sh"
```

`setup-pod.sh` is idempotent: existing clones are skipped, the shipped packs are refreshed from `node-packs`, the four superseded Icekiub folders and `comfyui-unsafe-torch` are removed, and it ends with `SETUP_COMPLETE`. Start ComfyUI with `bash /workspace/epalle/start-comfy.sh` (in `tmux`, or with `nohup ... &`) and note the proxy URL `https://<pod-id>-8188.proxy.runpod.net`.

### 4. Models

Plan locally, download on the pod, audit the gap:

```powershell
python infra/runpod/plan_models.py --online
scp -i .\epalle_runpod_ed25519 -P <PORT> infra\runpod\download-plan.json root@<PUBLIC_IP>:/workspace/epalle/
```

On the pod, with the Hugging Face token in the environment (the one whose account accepted the Klein licence):

```bash
export HF_TOKEN=hf_...
/workspace/epalle/venv/bin/python /workspace/epalle/download_planned.py --plan /workspace/epalle/download-plan.json
find /workspace/epalle/models -type f -printf '%s\t%P\n' > /workspace/epalle/pod-inventory.txt
```

`download_planned.py` skips NVFP4 and INT4 weights on an A100 (sm80) because they only run on Blackwell; `--all` overrides that and is not wanted here. Copy `pod-inventory.txt` back and audit:

```powershell
scp -i .\epalle_runpod_ed25519 -P <PORT> root@<PUBLIC_IP>:/workspace/epalle/pod-inventory.txt infra\runpod\
python infra/runpod/audit_models.py --inventory infra/runpod/pod-inventory.txt --json infra/runpod/model-gap-report.json
```

Expected gaps that stay gaps by design: creator-private LoRAs (`Lora_lora_000000600.safetensors`, `RemyTurbov2`, `1GIRL_QWEN_V3` and the like) are not downloadable and the workflows that need them stay BLOCKED. `consistent-room` needs a LoRA trained on the lead (`roles[].lora`) and is out of scope for this proof.

#### Training

`setup-pod.sh` clones `ostris/ai-toolkit` into `/workspace/epalle/ai-toolkit` and installs its requirements into the ComfyUI venv (idempotent; a failure there is a warning, not a stop). That is the only training software on the pod. The `lora-train` step never trains from the engine: `python packages/engine/lora_train.py --client epalle --collection red-dress --trigger rdrss --dry-run` writes `config.yaml` and `launch.sh` under `brands/epalle/runs/training/red-dress/`, and a person runs `launch.sh` with the pod up. Two things gate it: `HF_TOKEN` in the pod environment from the account that accepted the FLUX.2 Klein licence (`docs/BLOCKERS.md` item 3; ai-toolkit pulls the text encoder and VAE from the Hugging Face repo), and the Klein 9B base file on the volume from `download_planned.py` above. The trained `.safetensors` comes back by scp and is named on the role as `roles[].lora`.

### 5. LM Studio

Two graphs call an LM Studio server that the pod does not have. `H3_Icy_image.json` (the `h3-reference-image` step) compiles the prompt through `ICYLMStudioMultimodalPrompt`, and `workflows/icekiub/captioning_workflow.json` ships pointed at Icekiub's LAN, `http://192.168.2.20:8080`, which must be re-pointed before it can run anywhere else. Neither is on the path of this proof: without a character role the director routes stills through Krea 2 (`Krea2Icy_-Subs_1.1.json`), whose port map binds the composed prompt straight into the prompt widget, no LLM in between.

Two options for later, when the H3 reference route is wanted:

- LM Studio on this PC, reachable from the pod over Tailscale. Install Tailscale on both, then set the `base_url` widget of the ICYLM nodes to `http://<tailscale-ip-of-this-pc>:1234` (LM Studio's default port; Icekiub's graphs use 8080 and 1234 in different lessons).
- An OpenAI-compatible server on the pod itself: vLLM or llama.cpp serving a Qwen3-VL model on a second port, with `base_url` set to `http://127.0.0.1:<port>`. This shares the A100's VRAM with ComfyUI, so pick a quantised model.

### 6. Validate against the running pod

Probe first, so validation is a real check and not an unreachable backend reading as a pass:

```powershell
python packages/comfy-client/client.py probe --backend pod --url https://<pod-id>-8188.proxy.runpod.net
python packages/comfy-client/client.py validate --all --backend pod --url https://<pod-id>-8188.proxy.runpod.net
```

Validation is three-state. `OK` means every node type and model file the graph needs is installed on the pod. `BLOCKED` lists what is missing. `UNVERIFIED` means the pod could not be reached, and `client.py run --live` refuses an unverified backend, so the gate for the next steps is `OK`, not `UNVERIFIED`. For the engine proof the graphs that must read `OK` are `klein-t2i-test.json`, `Krea2Icy_-Subs_1.1.json`, `Any_Clothes_9B_-_Subs_-_Icekiub_V1.3.json` and `I2V_Infinite_extender_-_SUBS_-_Icekiub_v1.json`.

Then validate the newer dataset graph on its own:

```powershell
python packages/comfy-client/client.py validate workflows/icekiub/Icy_-_Dataset_gen_-_Klein_-_subs.json --backend pod --url https://<pod-id>-8188.proxy.runpod.net
```

If it reads `OK`, switch the studio's `dataset` catalogue node to it. The catalogue is `packages/studio-ui/catalog/nodes.json`: the node with `"kind": "dataset"` has `backend.workflow` set to `icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-_Subs_-_Icekiub_v2.json`; change that value to `icekiub/Icy_-_Dataset_gen_-_Klein_-_subs.json`. The same filename also keys a description entry in `packages/strategy/workflow_catalog.py`; move that entry to the new filename so the catalogue tests still find it, then re-run `pytest`.

### 7. Cheapest paid proof

One Klein text-to-image on the pod, measured at 8.1 s earlier. Validation runs first and the client refuses to submit if it is not `OK`:

```powershell
python packages/comfy-client/client.py run workflows/api-tests/klein-t2i-test.json --backend pod --url https://<pod-id>-8188.proxy.runpod.net --live --seed 7
```

`client.py` injects `--prompt` only into a `CR Prompt List` node, the Comfyroll batch driver the Icekiub dataset and carousel graphs use. The Klein test graph has none, so it runs with its baked-in prompt and would print a warning if `--prompt` were passed; the engine in step 8 binds prompts through the port map instead. The client prints the submitted `prompt_id`; queued is not success, so check the pod's `/history/<prompt_id>` or the ComfyUI queue for `COMPLETED` with an output file before moving on.

### 8. Engine live, stage-approval mode

The engine's ComfyUI client reads the pod URL from the environment, so set it once:

```powershell
$env:COMFY_POD_URL = 'https://<pod-id>-8188.proxy.runpod.net'
```

Start a second session for the paid run, without the wardrobe. With a wardrobe attached the director puts the `wardrobe` step (Any Clothes 9B, on the licence-gated Klein 9B KV) between the pick and the motion step, and the motion step is blocked until it has run; leaving the wardrobe out keeps the proof at stills, pick and one clip. Session `rp1` above remains the dry-run record of the rights gate.

```powershell
python packages/engine/cli.py say --client epalle --session rp2 --text "a lookbook of one persona across a city evening, neon noir"
python packages/engine/cli.py say --client epalle --session rp2 --text "2 scenes"
python packages/engine/cli.py say --client epalle --session rp2 --text "3 angles"
python packages/engine/cli.py say --client epalle --session rp2 --text "clips 4 seconds long"
```

Run the first stills stage. In `stage-approval` mode the runner proposes an `engine_stage` task with the cost estimate and stops until a person approves it:

```powershell
python packages/engine/cli.py run --client epalle --workflow <workflow-id> --stage scene1 --mode stage-approval --backend pod
```

The output names the task and its estimate. The runner does not consume an approval recorded separately: each run proposes a fresh task, so the approval is given inline on the re-run with `--approve-as`, which must be your name and not the engine's worker name. Do that, and reject the first task so the queue does not keep it as awaiting:

```powershell
python packages/orchestrator/control.py queue --brand epalle
python packages/orchestrator/control.py reject --id <task-id> --why "superseded by the approved re-run"
python packages/engine/cli.py run --client epalle --workflow <workflow-id> --stage scene1 --mode stage-approval --backend pod --approve-as <your-name>
```

Each of the three angle nodes (`scene1.krea2-t2i.a1` to `a3`) must report `completed`, with files fetched under `brands/epalle/runs/<workflow-id>/scene1.krea2-t2i.a*/` and `gpu_seconds_actual` in every manifest. `python packages/orchestrator/control.py audit` shows the approval and the finish with the actual spend. Then pick:

```powershell
python packages/engine/cli.py say --client epalle --session rp2 --text "keep at scene1.pick.keep: 1, 2"
```

Motion is one 4 second Wan 2.2 clip from the kept still (the `I2V_Infinite_extender` graph). Same approve-inline pattern:

```powershell
python packages/engine/cli.py run --client epalle --workflow <workflow-id> --stage scene1-motion --mode stage-approval --backend pod --approve-as <your-name>
```

Repeat stills, pick and motion for `scene2` (`--stage scene2`, `keep at scene2.pick.keep: 1`, `--stage scene2-motion`). The runner holds back anything downstream of a pick nobody has made, however far down, so the cut waits until both scenes are picked. Cut and captions (stage `edit`) and export (stage `publish`) then run on this machine with ffmpeg and cost nothing, so they run without a gate:

```powershell
python packages/engine/cli.py run --client epalle --workflow <workflow-id> --stage edit --mode stage-approval --backend pod
python packages/engine/cli.py run --client epalle --workflow <workflow-id> --stage publish --mode stage-approval --backend pod
```

The export lands under `brands/epalle/runs/<workflow-id>/publish.export/<run>/export/`.

Optional, and the only way to close `docs/BLOCKERS.md` item 2: one serverless cold start with the allowlisted smoke template, which passes only on `COMPLETED` with files:

```powershell
python packages/comfy-client/client.py smoke --backend serverless --live
```

### 9. Write back and shut down

1. Copy `gpu_seconds_actual` from the manifests into `brands/_presets/engine.yaml`: `krea2-t2i` (per image) and `image-to-video` (divide by the clip's seconds) get `seconds` from the run and `basis: measured`, with `source` pointing at the run manifest.
2. Update `infra/runpod/verification-summary.md` with the date, the pod, what completed and the measured seconds, and `docs/BLOCKERS.md` items 1 to 3.
3. Stop the pod; GPU billing ends here:

   ```powershell
   python infra/runpod/provision_pod.py --stop rl4rktj2fpnphn
   python infra/runpod/provision_pod.py --status
   ```

4. Commit, then `graphify update .` so the knowledge graph matches the repo.
