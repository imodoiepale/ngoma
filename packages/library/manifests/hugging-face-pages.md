# Hugging Face access pages

Open the two gated repositories while signed into the Hugging Face account associated with the configured token. Read and accept their terms before the Klein files can be downloaded.

## Manual acceptance required

- [FLUX.2 Klein 9B KV](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-kv) — **acceptance still required**; used by the carousel pose workflow.
- [FLUX.2 Klein 9B FP8](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8) — **accepted and token access verified**; used by the SCAIL + Klein workflow.

## Public model repositories used by the workflow library

- [Comfy-Org FLUX.2 Klein 9B support files](https://huggingface.co/Comfy-Org/flux2-klein-9B)
- [Kijai WanVideo FP8 scaled](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled)
- [Kijai WanVideo support models](https://huggingface.co/Kijai/WanVideo_comfy)
- [Comfy-Org Wan 2.1 ComfyUI repackaged](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged)
- [LightX2V Wan 2.1 I2V distillation LoRA](https://huggingface.co/lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v)
- [Wan-AI Wan 2.2 Animate 14B](https://huggingface.co/Wan-AI/Wan2.2-Animate-14B)
- [Kijai VitPose Comfy](https://huggingface.co/Kijai/vitpose_comfy)
- [Comfy-Org SCAIL-2](https://huggingface.co/Comfy-Org/SCAIL-2)
- [Comfy-Org SAM 3.1](https://huggingface.co/Comfy-Org/sam3.1)
- [Comfy-Org MiniMax H3](https://huggingface.co/Comfy-Org/MiniMax-H3)
- [Kijai MiniMax H3 experimental](https://huggingface.co/Kijai/MiniMax-H3-experimental)

## Workflow-local files without a verified public source

The following names appear in supplied graphs but do not identify a dependable public repository. They are treated as user or creator LoRAs and are never silently substituted:

- `my_first_lora_v1_000000600_low_noise.safetensors`
- `slop_twerk_LowNoise_merged3_7_v2.safetensors`
- `wan2.1_SCAIL_2_DPO_lora_bf16(1).safetensors`
- `Lora_lora_000000600.safetensors`

Access approval does not alter a model's license. Each model remains governed by the terms shown on its repository page.
