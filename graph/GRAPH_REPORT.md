# Graph Report — EPALLE Studio corpus (2026-09-13)

## Summary
- 651 nodes · 2179 edges
- node kinds: node_type 266, model 89, model_file 84, workflow 51, node_pack 41, style 35, video 24, creative 18, collection 13, technique 13, version 6, channel 4, gpu 2, hardware 2, brand 2, setting 1
- edge kinds: uses 1358, requires 509, belongs_to 194, mentions 90, provided_by 28
- 90 edges carry transcript evidence (video id + timestamp + quote)

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
- `comfyui-videohelpersuite` — 29 connections
- `comfyui-h3-motion-context` — 10 connections
- `comfyui-solattn_triton` — 8 connections
- `rgthree-comfy` — 8 connections
- `comfyui_comfyroll_customnodes` — 7 connections
- `comfyui-easy-use` — 5 connections
- `res4lyf` — 5 connections
- `comfyui-impact-pack` — 5 connections
- `comfyui_controlnet_aux` — 5 connections
- `efficiency-nodes-comfyui` — 5 connections
- `maskvidexperiments` — 4 connections
- `comfyui_essentials` — 3 connections
- `sage-attention` — 3 connections

## God nodes — models
- `minimax-h3` — 3 connections
- `veo` — 3 connections
- `minimax-h3-video-vae` — 2 connections
- `minimax-h3-ref2va` — 2 connections
- `flux-2-klein-9b` — 2 connections
- `minimax-h3-audio-vae-fp32` — 1 connections
- `minimax-h3-fl2v-turbo-4step-v1.0-768p-comfyui` — 1 connections
- `minimax-h3-fl2va` — 1 connections
- `qwen3vl-32b-minimax-h3-nvfp4-awq` — 1 connections
- `minimax-h3-fl2v-lightx2v-turbo-4step-v0.1-comfy` — 1 connections
- `minimax-h3-fl2va-int4q` — 1 connections
- `minimax-h3-ref2v-turbo-4step-v0.1-comfyui` — 1 connections
- `birefnet` — 1 connections
- `minimax-h3-fl2v-lightx2v-turbo-8step-v1.0-resized-avg-rank-24` — 1 connections
- `sam3.1-multiplex` — 1 connections

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
- 2 concepts appear BOTH as a workflow dependency and in a
  creator transcript: `comfyui-kjnodes`, `comfyui_essentials`

## Queries
```bash
uv run packages/library/graph_query.py deps workflows/icekiub/Carousel_Pose_changer.json
uv run packages/library/graph_query.py dependents comfyui-kjnodes
uv run packages/library/graph_query.py evidence flux-2-klein
```