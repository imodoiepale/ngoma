# EPALLE Creative Studio — Project Summary

## Objective

EPALLE is a persistent creative-production environment for character datasets, localized UGC advertising, music videos, motion transfer, character replacement, face/body replacement, pose-controlled carousels, and long-form AI video. It combines a Weavy-style studio interface, native ComfyUI workflows, a searchable research library, a Notion knowledge base, and RunPod Pod/serverless execution.

## Current infrastructure

- RunPod network volume `epalle-studio` (`7y7jyghmua`), 200 GB in US-KS-2.
- Original development Pod `eeoldxyxnd0o1z`, currently stopped because its assigned host has no available GPU.
- Serverless endpoint `epalle-studio-api` (`ugtmfoidpnh8pd`), scale-to-zero, one admitted worker maximum.
- An automatic capacity check retries every 15 minutes. After a GPU becomes available it will sync, install, validate, stop the development Pod, and restore the normal daily source-watch schedule.
- All durable runtime data belongs under `/workspace/epalle` on the network volume.

## Interfaces

- EPALLE Studio canvas: `/` on port 3000.
- Workflow library: `/library` on port 3000.
- Job status: `/jobs` on port 3000.
- Vibe-Workflow node editor: `/workflow` on port 3000.
- ComfyUI: port 8188.
- JupyterLab: port 8888.

## Workflow inventory

The local library contains 32 workflow JSON files. Four came from `C:\Users\inkno\Documents\COMFY`; two of those are identical copies, leaving three distinct local graphs:

1. IcyMotion Free v3 — SCAIL-2 motion control.
2. Carousel Pose Changer — FLUX.2 Klein KV pose generation.
3. ICY SCAIL 2.0 + FLUX Klein — first-frame generation plus motion transfer.

The wider library also contains MATRIX Dataset V1, five official SCAIL-2 graphs, MiniMax H3 music/extension/keyframe workflows, AI Ninja long-video and face/body replacement graphs, and API smoke tests.

## Models and acceleration

- Twelve files totaling about 103.25 GB are verified by exact size and SHA-256.
- FLUX.2 Klein 9B FP8 access is accepted and token access is verified.
- FLUX.2 Klein 9B KV still requires manual license acceptance.
- The A100 runtime now uses the matched Torch 2.9.1+cu128 stack and SageAttention 2.2.0 compiled from the official source specifically for SM80 with CUDA 12.8 and GCC 13.
- SageAttention passed 12 ordered kernel tests across four representative attention shapes. ComfyUI starts with global Sage attention by default; `EPALLE_USE_SAGE=0` remains available for model-specific diagnosis. Saved workflow nodes remain in bypass mode because global acceleration covers them without duplicate patching.

## UGC production path

1. Ingest an authorized reference ad and extract its shot boundaries, spoken timing, on-screen text, camera movement, product handling, and retention pattern.
2. Rewrite the message for the new product and market. Preserve duration and information density while creating original dialogue and visuals.
3. Select English, Kenyan English, Kiswahili, Sheng, French, or a controlled blend.
4. Use the creator's supplied voice recording, or synthesize a Kenyan performance from the approved script.
5. Build or select the recurring character dataset.
6. Generate product and pose shots with Klein, motion transfer/replacement with SCAIL-2, and performance/long-video shots with MiniMax H3.
7. Assemble against the final voice track, add captions and product graphics, review hand/product consistency, and export platform variants.

## Kenyan voice specification

For a generated voice, scripts contain delivery markup separate from spoken text: speaker age range, Kenyan regional character, energy, pace, pause lengths, code-switch points, pronunciation notes, and emotional turns. Sheng is used selectively and reviewed for audience fit. Brand names, prices, URLs, and calls to action receive phonetic notes before synthesis. The approved audio becomes the timing master for video generation and editing.

## Inputs required for the first advertisement

- Reference video and permission to adapt it.
- Product name, offer, price, features, audience, and call to action.
- Product images or video from several angles.
- Character images or an existing EPALLE character identity.
- Preferred language mix and Kenyan voice direction.
- Target duration, aspect ratio, and publishing platforms.
- Brand logo, colors, typography, disclaimer text, and delivery deadline.

## Data durability

Models, workflows, generated outputs, caches, manifests, custom nodes, and logs are stored under the persistent volume. The same workflows and manifests also have local copies in this project. Model hashes and source repositories allow reconstruction. Production outputs should additionally be synchronized to independent object storage before publication.

## Current runtime

- Pod `rl4rktj2fpnphn` is running on an NVIDIA A100-SXM4-80GB in US-KS-2 with persistent network volume `7y7jyghmua` (300 GB).
- The reported KSampler failure was traced through ComfyUI history to KJNodes' SageAttention override. The exact failed 25-shot graph was replayed with the Sage nodes removed and completed successfully in 364.87 seconds, producing 45 images.
- A runtime compatibility guard also makes Sage patch nodes from already-open browser graphs pass the model through to PyTorch SDPA. A fresh guarded smoke test completed successfully in 91.0 seconds and saved `epalle/klein-t2i-test_00002_.png`.
- After the supported Sage runtime was installed, a complete FLUX.2 Klein text-to-image workflow successfully loaded the text encoder, diffusion model, and VAE; sampled 20 steps; decoded; and saved one image. ComfyUI reported `Using sage attention`.
- Klein KV remains gated until its license is accepted. Actual UGC generation still needs the first product brief, authorized media assets, and voice choice.
