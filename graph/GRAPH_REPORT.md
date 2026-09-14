# Graph Report — EPALLE Studio corpus (2026-09-14)

## Summary
- 1127 nodes · 3705 edges
- node kinds: node_type 300, video 216, model 160, model_file 146, workflow 72, node_pack 54, setting 49, style 35, creative 26, technique 24, collection 13, gpu 8, hardware 8, channel 7, version 7, brand 2
- edge kinds: uses 1834, requires 783, mentions 591, belongs_to 469, provided_by 28
- 591 edges carry transcript evidence (video id + timestamp + quote)

## Extraction provenance
- workflow structure: EXTRACTED from `workflows/manifest.json` (`class_type`,
  `properties.cnr_id`/`aux_id`, widget model filenames). No inference.
- transcript facts: EXTRACTED from subtitle cues; every one cites a video and
  timestamp. A creator saying something is evidence of a claim, not proof it works.
- node types with no declared pack are attributed to `comfy-core`; a type is only
  linked to a pack when its workflow declares exactly one, so attribution is never guessed.

## God nodes — node packs (what everything depends on)
- `comfy-core` — 100 connections
- `comfyui-kjnodes` — 53 connections
- `comfyui-videohelpersuite` — 36 connections
- `rgthree-comfy` — 16 connections
- `comfyui-impact-pack` — 13 connections
- `res4lyf` — 12 connections
- `comfyui_controlnet_aux` — 11 connections
- `comfyui-h3-motion-context` — 10 connections
- `comfyui-easy-use` — 9 connections
- `comfyui-solattn_triton` — 8 connections
- `comfyui-custom-scripts` — 8 connections
- `efficiency-nodes-comfyui` — 8 connections
- `comfyui_comfyroll_customnodes` — 7 connections
- `face-detailer` — 7 connections
- `comfyui-inspire-pack` — 6 connections

## God nodes — models
- `z-image-turbo` — 25 connections
- `nano-banana` — 14 connections
- `minimax-h3` — 8 connections
- `gpt-image-2` — 7 connections
- `nano-banana-pro` — 6 connections
- `flux-2-klein` — 5 connections
- `scail-2` — 4 connections
- `veo` — 4 connections
- `flux-2-klein-9b` — 3 connections
- `kling` — 3 connections
- `midjourney` — 3 connections
- `minimax-h3-video-vae` — 2 connections
- `minimax-h3-ref2va` — 2 connections
- `rife47` — 2 connections
- `qwen-image` — 2 connections

## Most-used node types
- `VAELoader` — 67 connections
- `CLIPLoader` — 65 connections
- `UNETLoader` — 64 connections
- `VAEDecode` — 62 connections
- `LoadImage` — 54 connections
- `CLIPTextEncode` — 49 connections
- `LoraLoaderModelOnly` — 48 connections
- `PathchSageAttentionKJ` — 40 connections
- `PreviewImage` — 38 connections
- `KSampler` — 34 connections
- `VHS_VideoCombine` — 31 connections
- `MarkdownNote` — 31 connections
- `ImageResizeKJv2` — 29 connections
- `VAEEncode` — 27 connections
- `KSamplerSelect` — 26 connections

## Corroboration
- 6 concepts appear BOTH as a workflow dependency and in a
  creator transcript: `comfyui-custom-scripts`, `comfyui-impact-pack`, `comfyui-kjnodes`, `comfyui-sam3`, `comfyui-videohelpersuite`, `comfyui_essentials`

## Queries
```bash
uv run packages/library/graph_query.py deps workflows/icekiub/Carousel_Pose_changer.json
uv run packages/library/graph_query.py dependents comfyui-kjnodes
uv run packages/library/graph_query.py evidence flux-2-klein
```