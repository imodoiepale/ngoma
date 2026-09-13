# MiniMax H3 RefMods: consistent characters without training a LoRA

**Source:** Dainamo, *How to Create a RefMod for MiniMax H3 – No Training Required*.
Published 2026-09-12, 6:31 long. Link: https://www.youtube.com/watch?v=2K6-OtV_Vbc

The subtitles and mined facts are in `packages/library/corpus/youtube/dainamo/`. To see
where creators discuss this, with timestamps:

```bash
uv run packages/library/graph_query.py evidence "minimax h3"
```

## What a RefMod is

A **LoRA** is trained. It learns small weight changes from a dataset, which takes hours.
A **RefMod** is not trained. The reference images, videos or audio pass once through
MiniMax H3's VAE, and the resulting latents are saved as a small `.safetensors` file.
In the video, 24 photos became a RefMod in about 5.5 seconds. The file is a few megabytes,
compared with tens to hundreds for a LoRA. At generation time it is loaded and applied like
a LoRA would be.

The presenter's result: identity came through well, but the voice did not, because they
made an image-only RefMod. An **audio RefMod** is the stated fix. That was not shown.

## The steps (chapter timestamps)

| When | Step |
|---|---|
| 0:00 | Clone two required node packs and one optional one into `ComfyUI/custom_nodes`. |
| 1:20 | On an empty canvas, add **Create H3 RefMod From Folder**. Feed it a video VAE (`minimax_h3_video_vae_fp16`) and the audio VAE (`minimax_h3_audio_vae_fp32`). Point it at a folder of images; no captions needed, and videos or audio also work. Tick subfolders if used. Name the RefMod. Choose the extraction preset: **identity** (video default), **style** or **motion**. Enable save, then run. |
| 3:21 | Open the generation workflow. It is the usual H3 stack: video and audio VAE, CLIP, and the H3 reference-to-video model (the int8 version in the video, and reported to work on other fine-tunes). Select the RefMod in the loader. Several RefMods can be combined, for example a second one in the `mod 2` slot. Write a normal H3 prompt. |
| 5:22 | Compare the RefMod output with a LoRA output. |

## What we downloaded

All three workflows are in `workflows/h3-refmods/` and registered in
`workflows/manifest.json` with their SHA-256 hash and source URL.

| File | From | Job |
|---|---|---|
| `dainamo-refmod-generate.json` | The video's linked workflow (malcolmrey/workflows on HuggingFace) | Generate video using a RefMod. 21 nodes. |
| `franckyb-refmod-create-from-folder.json` | ComfyUI-H3RefModPicker `example_workflows/` | Create a RefMod from a folder. 3 nodes. |
| `franckyb-refmod-picker-example.json` | ComfyUI-H3RefModPicker `example_workflows/` | Generate using the visual picker, with two example RefMods. 27 nodes. |

To see what each one needs:

```bash
uv run packages/comfy-client/client.py deps h3-refmods/dainamo-refmod-generate.json
```

### Node packs

None of these are installed or executed on this machine. The class names below were read
from each repo's source on 2026-09-13.

| Repo | Licence | Status | Nodes our workflows use |
|---|---|---|---|
| [Luisacaotica/ComfyUI-MiniMaxH3Mod](https://github.com/Luisacaotica/ComfyUI-MiniMaxH3Mod) | MIT | The author marks it "under construction" | `MiniMaxH3RefModsLoader`, `MiniMaxH3RefModApply` |
| [FranckyB/ComfyUI-H3RefModPicker](https://github.com/FranckyB/ComfyUI-H3RefModPicker) | MIT | Fork with a better UI and audio support. The video notes it changed after publishing. | `H3RefModCreateFromFolder`, `H3RefModApplySimple`, `H3RefModVisualPicker` |
| [xmarre/ComfyUI-Spectrum-MiniMax-H3](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3) | **GPL-3.0** | Optional speed-up | `SpectrumApplyMiniMaxH3` |

The generate workflow also needs `comfyui-kjnodes` (Patch Sage Attention) and
`rgthree-comfy` (Power Lora Loader). The picker example uses three node types whose pack
cannot be identified from the file (`LoadLoraPlus`, `ModelAttentionBackend`,
`ResolutionSelector`). The manifest lists them under `unattributed_node_types` rather than
guessing a pack.

### Models (sizes from HuggingFace, 2026-09-13)

| File | Size | Repo | Already in `infra/runpod/download-plan.json`? |
|---|---|---|---|
| `minimax_h3_ref2va_pruned_fp8_scaled.safetensors` | 20.96 GB | Comfy-Org/MiniMax-H3 | **No, new** |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15.69 GB | Comfy-Org/MiniMax-H3 | Yes |
| `minimax_h3_video_vae_fp16.safetensors` | 5.21 GB | Comfy-Org/MiniMax-H3 | Yes |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.61 GB | Comfy-Org/MiniMax-H3 | In the gap report |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (picker example) | — | — | In the gap report |
| `minimaxh3_adamdriver_v1_refmod`, `minimaxh3_aimeegarcia_v1_refmod` (picker example) | small | Not located | Example RefMods of other people. **Do not use.** |

## How this fits the studio

**1. It solves character consistency, our biggest gap for video.** Until now, a recurring
Ongea Pesa character or the EPALLE artist on screen needed LoRA training: hours of GPU time
per character. A RefMod takes seconds. You can remake it whenever the references change,
and store it alongside the brand kit.

**2. Rights come first, and code enforces them.** The presenter made a RefMod of themself
because they own that likeness. We follow the same rule. RefMods are built **only** from
people who have consented: our own characters, cast talent with a release, or the EPALLE
artist. They are never built from reference-profile creators. Our standing rule already
says *take the grammar, never the images*. A RefMod of a scraped creator would break it
outright. The two example RefMods in the picker workflow depict other real people and
should be deleted from any pod that downloads them.

**3. It needs a pod, not this PC or the current serverless setup.** Making a RefMod is only
a VAE encode, but that still needs the 5 GB video VAE on a GPU. Generation needs roughly
21 GB of model plus 16 GB of text encoder in VRAM, so an A100 80 GB pod.
*Unverified:* NVFP4 weights are designed for NVIDIA Blackwell cards. On an A100, ComfyUI
may dequantize or reject them. Run `client.py validate` against the pod before trusting
this workflow.

**4. The Sage node is in this workflow too.** Our guard bypasses it on torch 2.11 or newer
(see [SAGE-ATTENTION.md](SAGE-ATTENTION.md)). The workflow should still run, just slower.

**5. Spectrum is GPL-3.0.** That is fine for internal generation. It adds to licence
blocker #10 if these workflows are ever bundled or sold (for example, the Whop course).

## Next steps

1. **ME:** add the three packs, pinned to the commits reviewed here, to the pod install
   list. Spectrum stays optional.
2. **ME:** add `minimax_h3_ref2va_pruned_fp8_scaled` to the download plan, then run
   `infra/runpod/audit_models.py` for the refmod workflows on the pod.
3. **YOU:** choose the first RefMod subject and supply 20–30 owned, consented reference
   images. An Ongea Pesa character fits, as does the EPALLE artist with their consent.
4. **ME:** create the RefMod on the pod, generate one short clip, and compare it with a
   LoRA if one exists. Store the `.safetensors` file with the brand, never in git.
5. **ME:** after the serverless smoke test passes, bake the packs into the serverless image.
