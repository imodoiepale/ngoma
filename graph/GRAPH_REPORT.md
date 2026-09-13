# Graph Report — EPALLE Studio corpus (2026-09-13)

## Summary
- 940 nodes · 2872 edges
- node kinds: node_type 266, video 216, model 100, model_file 84, workflow 51, setting 49, node_pack 44, style 35, creative 26, technique 24, collection 13, gpu 8, hardware 8, channel 7, version 7, brand 2
- edge kinds: uses 1358, mentions 591, requires 509, belongs_to 386, provided_by 28
- 591 edges carry transcript evidence (video id + timestamp + quote)

## Extraction provenance
- workflow structure: EXTRACTED from `workflows/manifest.json` (`class_type`,
  `properties.cnr_id`/`aux_id`, widget model filenames). No inference.
- transcript facts: EXTRACTED from subtitle cues; every one cites a video and
  timestamp. A creator saying something is evidence of a claim, not proof it works.
- node types with no declared pack are attributed to `comfy-core`; a type is only
  linked to a pack when its workflow declares exactly one, so attribution is never guessed.

## God nodes — node packs (what everything depends on)
- `comfy-core` — 79 connections
- `comfyui-kjnodes` — 33 connections
- `comfyui-videohelpersuite` — 30 connections
- `comfyui-h3-motion-context` — 10 connections
- `comfyui-solattn_triton` — 8 connections
- `rgthree-comfy` — 8 connections
- `comfyui_comfyroll_customnodes` — 7 connections
- `face-detailer` — 7 connections
- `comfyui-impact-pack` — 6 connections
- `comfyui-easy-use` — 5 connections
- `res4lyf` — 5 connections
- `comfyui_controlnet_aux` — 5 connections
- `efficiency-nodes-comfyui` — 5 connections
- `sage-attention` — 5 connections
- `maskvidexperiments` — 4 connections

## God nodes — models
- `z-image-turbo` — 25 connections
- `nano-banana` — 14 connections
- `minimax-h3` — 8 connections
- `gpt-image-2` — 7 connections
- `nano-banana-pro` — 6 connections
- `flux-2-klein` — 5 connections
- `scail-2` — 4 connections
- `veo` — 4 connections
- `kling` — 3 connections
- `midjourney` — 3 connections
- `minimax-h3-video-vae` — 2 connections
- `minimax-h3-ref2va` — 2 connections
- `flux-2-klein-9b` — 2 connections
- `qwen-image` — 2 connections
- `ideogram` — 2 connections

## Most-used node types
- `VAELoader` — 49 connections
- `CLIPLoader` — 47 connections
- `UNETLoader` — 47 connections
- `VAEDecode` — 46 connections
- `LoadImage` — 38 connections
- `LoraLoaderModelOnly` — 34 connections
- `CLIPTextEncode` — 30 connections
- `VHS_VideoCombine` — 26 connections
- `KSamplerSelect` — 24 connections
- `RandomNoise` — 24 connections
- `SamplerCustomAdvanced` — 24 connections
- `PathchSageAttentionKJ` — 23 connections
- `KSampler` — 23 connections
- `BasicGuider` — 22 connections
- `BasicScheduler` — 20 connections

## Corroboration
- 6 concepts appear BOTH as a workflow dependency and in a
  creator transcript: `comfyui-custom-scripts`, `comfyui-impact-pack`, `comfyui-kjnodes`, `comfyui-sam3`, `comfyui-videohelpersuite`, `comfyui_essentials`

## Queries
```bash
uv run packages/library/graph_query.py deps workflows/icekiub/Carousel_Pose_changer.json
uv run packages/library/graph_query.py dependents comfyui-kjnodes
uv run packages/library/graph_query.py evidence flux-2-klein
```