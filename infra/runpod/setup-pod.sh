#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/epalle/{models,projects,cache,manifests,logs,libraries,workflows,workflow-api,node-packs,src,outputs}
ROOT=/workspace/epalle
if [ ! -d "$ROOT/ComfyUI" ]; then git clone https://github.com/Comfy-Org/ComfyUI.git "$ROOT/ComfyUI"; fi
cd "$ROOT/ComfyUI"
if [ ! -d "$ROOT/venv" ]; then python3 -m venv --system-site-packages "$ROOT/venv"; fi
PY="$ROOT/venv/bin/python"
$PY -m pip install -r requirements.txt
$PY -m pip install huggingface_hub runpod

# ---------------------------------------------------------------------------------------------
# Node packs. Every entry is <github owner>/<repo>; the folder name is the repo name. Idempotent:
# an existing folder is left alone. The list is derived from workflows/manifest.json (node_packs
# per workflow). Group 1 is what the 14 port-mapped engine workflows (workflows/**/*.ports.json,
# the steps in packages/studio-ui/catalog/nodes.json) need. Group 2 is the rest of the library.
# ---------------------------------------------------------------------------------------------

# Group 1: required by the engine's port-mapped workflows. A failed requirements install aborts
# the setup, on purpose: the engine cannot run without these.
ENGINE_PACKS=(
  'Comfy-Org/ComfyUI-Manager'
  'rgthree/rgthree-comfy'
  'Kosinkadink/ComfyUI-VideoHelperSuite'
  'kijai/ComfyUI-KJNodes'
  'kijai/ComfyUI-WanVideoWrapper'
  'kijai/ComfyUI-SCAIL-Pose'
  'ltdrdata/ComfyUI-Impact-Pack'
  'ltdrdata/ComfyUI-Impact-Subpack'                 # Consistent Room (UltralyticsDetectorProvider)
  'ltdrdata/ComfyUI-Inspire-Pack'                   # QWEN IMAGE UNLEASHED v1 (LoadImageListFromDir //Inspire)
  'Suzie1/ComfyUI_Comfyroll_CustomNodes'            # Carousel Pose changer: `CR Prompt List`, the batch driver
  'Fannovel16/comfyui_controlnet_aux'
  'Fannovel16/ComfyUI-Frame-Interpolation'
  'yolain/ComfyUI-Easy-Use'
  'ClownsharkBatwing/RES4LYF'
  'pythongosssss/ComfyUI-Custom-Scripts'
  'facok/comfyui-krea2-controlnet'                  # Krea2Icy (the Krea 2 route)
  'princepainter/ComfyUI-PainterI2V'                # I2V Infinite extender
  'FranckyB/ComfyUI-H3RefModPicker'                 # refmod-create-from-folder
  'Luisacaotica/ComfyUI-MiniMaxH3Mod'               # dainamo-refmod-generate
  'xmarre/ComfyUI-Spectrum-MiniMax-H3'              # dainamo-refmod-generate
  'seitanism/ComfyUI-H3-Motion-Context-MultiRef'    # H3 (supersedes NikoDemon80/ComfyUI-H3-Motion-Context; same classes, never both)
  'LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler'   # h3 V2V Latent Motion Transfer
  'matlowai/ComfyUI-MAINodes'                       # h3 V2V Latent Motion Transfer (registry id comfyui-mainodes)
  'drozbay/MaskVidExperiments'
  'Nekodificador/ComfyUI-NKD-Basic-Tools'
  'Nekodificador/ComfyUI-NKD-Sigmas-Curve'
)
for item in "${ENGINE_PACKS[@]}"; do
 name="${item##*/}"
 if [ ! -d "custom_nodes/$name" ]; then git clone --recursive "https://github.com/$item.git" "custom_nodes/$name"; fi
 if [ -f "custom_nodes/$name/requirements.txt" ]; then $PY -m pip install -r "custom_nodes/$name/requirements.txt"; fi
done

# Group 2: the rest of the workflow library (not on the engine's path). A requirements failure
# here is reported and skipped so it cannot take the engine down with it.
LIBRARY_PACKS=(
  'jags111/efficiency-nodes-comfyui'
  'cubiq/ComfyUI_FaceAnalysis'                      # needs dlib or insightface; may fail to build
  'cubiq/ComfyUI_essentials'
  'theUpsider/ComfyUI-Logic'
  'capitan01R/ComfyUI-Krea2T-Enhancer'              # registry id comfyui-krea2t-enhancer (pyproject name matches)
  'DoctorDiffusion/ComfyUI-MediaMixer'              # registry id ComfyUI-MediaMixer (matched by name)
  'Lightricks/ComfyUI-LTXVideo'
  'kijai/ComfyUI-WanAnimatePreprocess'
  'wallen0322/ComfyUI-WanAnimate-Enhancer'          # aux_id recorded in the WAN ANIMATE V4 graphs
  'Comfy-Org/Nvidia_RTX_Nodes_ComfyUI'              # aux_id in LTX2.3 KlingKiller; also `pip install nvidia-vfx`
  'pollockjj/ComfyUI-MultiGPU'
  'ssitu/ComfyUI_UltimateSDUpscale'                 # has a git submodule, hence --recursive
  'Starnodes2024/ComfyUI_StarNodes'
  'bash-j/mikey_nodes'
  'WASasquatch/was-node-suite-comfyui'
  'PozzettiAndrea/ComfyUI-SAM3'                     # registry id comfyui-sam3 (INFLUENCER Dataset v1.1)
  'kijai/ComfyUI-SolAttn_triton'                    # aininja MiniMax graphs; triton build may fail
)
for item in "${LIBRARY_PACKS[@]}"; do
 name="${item##*/}"
 if [ ! -d "custom_nodes/$name" ]; then git clone --recursive "https://github.com/$item.git" "custom_nodes/$name" || { echo "WARN: could not clone $item" >&2; continue; }; fi
 if [ -f "custom_nodes/$name/requirements.txt" ]; then $PY -m pip install -r "custom_nodes/$name/requirements.txt" || echo "WARN: requirements failed for $name; its workflows will not load" >&2; fi
done

# Unresolved packs (in workflows/manifest.json, no verified repository; do not guess):
#   comfyui_sam3         registry id with version 0.2.1 and node SAM3Segmentation, used by the two
#                        ICY WAN ANIMATE V4 graphs. It is a different pack from comfyui-sam3 above
#                        (which has LoadSAM3Model and SAM3Grounding). Repository not identified.
#   NikoDemon80/ComfyUI-H3-Motion-Context   the fork seitanism/ComfyUI-H3-Motion-Context-MultiRef is
#                        installed instead; both register the same H3 classes, so never install both.
#   comfyui-unsafe-torch NEVER. It patches torch.load so any model file can run code. See NEVER_IMPORT
#                        in packages/library/tools/import_skool_pack.py. Removed below if present.
rm -rf custom_nodes/comfyui-unsafe-torch

# MATRIX has no pip dependencies. Never overwrite it.
if [ ! -e custom_nodes/matrix-power-nodes ]; then
 git clone https://github.com/imodoiepale/matrix-power-nodes.git custom_nodes/matrix-power-nodes
fi

# Repo-shipped Icekiub packs, staged at $ROOT/node-packs by infra/runpod/sync-workflows.ps1.
# icynodes registers the same node class names as the four standalone folders it replaces
# (betterimage_loader, ICYLM, icymegapixelresize, ComfyUI-IcyHider-icekiub); installing both breaks
# ComfyUI, so those are removed here. ComfyUI-IcyQwen3 and ComfyUI-icyTikTokDownloader were not
# merged and ship as themselves. Re-run after every sync: the copy is refreshed each time.
rm -rf custom_nodes/betterimage_loader custom_nodes/ICYLM custom_nodes/icymegapixelresize custom_nodes/ComfyUI-IcyHider-icekiub
for pack in icynodes ComfyUI-IcyQwen3 ComfyUI-icyTikTokDownloader; do
 if [ -d "$ROOT/node-packs/$pack" ]; then
  rm -rf "custom_nodes/$pack"
  cp -r "$ROOT/node-packs/$pack" "custom_nodes/$pack"
  if [ -f "custom_nodes/$pack/requirements.txt" ]; then $PY -m pip install -r "custom_nodes/$pack/requirements.txt"; fi
 else
  echo "WARN: $ROOT/node-packs/$pack is not staged; run infra/runpod/sync-workflows.ps1 from the workstation first" >&2
 fi
done

# LoRA training (packages/engine/lora_train.py, the `lora-train` step). ostris/ai-toolkit is not a
# node pack: it lives beside ComfyUI and its `run.py` is started by launch.sh, by a person, in the
# ComfyUI venv (torch is already there). Idempotent like the packs above; a requirements failure
# is a warning, since the engine's ComfyUI path does not depend on it. The Klein 9B base model it
# trains against is licence-gated (docs/BLOCKERS.md item 3): HF_TOKEN from the account that
# accepted the licence must be in the pod environment before download_planned.py and run.py.
if [ ! -d "$ROOT/ai-toolkit" ]; then git clone https://github.com/ostris/ai-toolkit.git "$ROOT/ai-toolkit" || echo "WARN: could not clone ostris/ai-toolkit; lora-train launch.sh will not run" >&2; fi
if [ -f "$ROOT/ai-toolkit/requirements.txt" ]; then $PY -m pip install -r "$ROOT/ai-toolkit/requirements.txt" || echo "WARN: ai-toolkit requirements failed; lora-train launch.sh will not run" >&2; fi
mkdir -p "$ROOT/training"
cd "$ROOT/ComfyUI"

# Workflow graphs for the ComfyUI UI. Port maps (*.ports.json) and manifest.json are studio files,
# not graphs, so they stay out of the UI folder.
mkdir -p user/default/workflows/EPALLE
find /workspace/epalle/workflows -type f -name '*.json' ! -name '*.ports.json' ! -name manifest.json -exec cp -n '{}' user/default/workflows/EPALLE/ \; 2>/dev/null || true
cat > extra_model_paths.yaml <<'PATHS'
epalle_persistent:
  base_path: /workspace/epalle/models
  checkpoints: checkpoints
  clip: clip
  clip_vision: clip_vision
  controlnet: controlnet
  diffusion_models: diffusion_models
  embeddings: embeddings
  loras: loras
  text_encoders: text_encoders
  vae: vae
PATHS
$PY -m pip install -U ninja packaging
bash /workspace/epalle/install-sageattention.sh
if [ -n "${HF_TOKEN:-}" ] && [ -f /workspace/epalle/download-workflow-models.py ]; then
  $PY /workspace/epalle/download-workflow-models.py || true
fi
$PY -m pip freeze > "$ROOT/manifests/runtime-freeze.txt"
git rev-parse HEAD > "$ROOT/manifests/comfy-commit.txt"
for d in custom_nodes/*; do if [ -d "$d/.git" ]; then printf '%s ' "$d"; git -C "$d" rev-parse HEAD; fi; done > "$ROOT/manifests/node-commits.txt"
cat > "$ROOT/start-comfy.sh" <<'START'
#!/usr/bin/env bash
set -euo pipefail
cd /workspace/epalle/ComfyUI
ARGS=(--listen 0.0.0.0 --port 8188 --user-directory /workspace/epalle/ComfyUI/user --highvram)
if /workspace/epalle/venv/bin/python -c 'import sageattention' >/dev/null 2>&1; then ARGS+=(--use-sage-attention); fi
exec /workspace/epalle/venv/bin/python main.py "${ARGS[@]}"
START
chmod +x "$ROOT/start-comfy.sh"
printf 'SETUP_COMPLETE\n'
