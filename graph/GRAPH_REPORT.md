# Graph Report — EPALLE Studio corpus (2026-09-13)

## Summary
- 623 nodes · 2098 edges
- node kinds: node_type 257, model 87, model_file 81, workflow 48, node_pack 38, style 35, video 23, creative 18, collection 12, technique 8, version 6, channel 3, gpu 2, hardware 2, brand 2, setting 1
- edge kinds: uses 1312, requires 488, belongs_to 187, mentions 83, provided_by 28
- 83 edges carry transcript evidence (video id + timestamp + quote)

## Extraction provenance
- workflow structure: EXTRACTED from `workflows/manifest.json` (`class_type`,
  `properties.cnr_id`/`aux_id`, widget model filenames). No inference.
- transcript facts: EXTRACTED from subtitle cues; every one cites a video and
  timestamp. A creator saying something is evidence of a claim, not proof it works.
- node types with no declared pack are attributed to `comfy-core`; a type is only
  linked to a pack when its workflow declares exactly one, so attribution is never guessed.

## God nodes — node packs (what everything depends on)
- `comfy-core` — 76 connections
- `comfyui-kjnodes` — 32 connections
- `comfyui-videohelpersuite` — 29 connections
- `comfyui-h3-motion-context` — 10 connections
- `comfyui-solattn_triton` — 8 connections
- `rgthree-comfy` — 7 connections
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
- `veo` — 3 connections
- `minimax-h3-video-vae` — 2 connections
- `flux-2-klein-9b` — 2 connections
- `minimax-h3` — 2 connections
- `minimax-h3-audio-vae-fp32` — 1 connections
- `minimax-h3-fl2v-turbo-4step-v1.0-768p-comfyui` — 1 connections
- `minimax-h3-fl2va` — 1 connections
- `qwen3vl-32b-minimax-h3-nvfp4-awq` — 1 connections
- `minimax-h3-fl2v-lightx2v-turbo-4step-v0.1-comfy` — 1 connections
- `minimax-h3-ref2va` — 1 connections
- `minimax-h3-fl2va-int4q` — 1 connections
- `minimax-h3-ref2v-turbo-4step-v0.1-comfyui` — 1 connections
- `birefnet` — 1 connections
- `minimax-h3-fl2v-lightx2v-turbo-8step-v1.0-resized-avg-rank-24` — 1 connections
- `sam3.1-multiplex` — 1 connections

## Most-used node types
- `VAELoader` — 46 connections
- `CLIPLoader` — 45 connections
- `UNETLoader` — 45 connections
- `VAEDecode` — 44 connections
- `LoadImage` — 38 connections
- `LoraLoaderModelOnly` — 34 connections
- `CLIPTextEncode` — 30 connections
- `VHS_VideoCombine` — 26 connections
- `KSampler` — 23 connections
- `KSamplerSelect` — 22 connections
- `RandomNoise` — 22 connections
- `SamplerCustomAdvanced` — 22 connections
- `PathchSageAttentionKJ` — 22 connections
- `BasicGuider` — 20 connections
- `Note` — 20 connections

## Corroboration
- 2 concepts appear BOTH as a workflow dependency and in a
  creator transcript: `comfyui-kjnodes`, `comfyui_essentials`

## Queries
```bash
uv run packages/library/graph_query.py deps workflows/icekiub/Carousel_Pose_changer.json
uv run packages/library/graph_query.py dependents comfyui-kjnodes
uv run packages/library/graph_query.py evidence flux-2-klein
```