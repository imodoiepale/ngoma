# ICYLM - LM Studio Nodes for ComfyUI

This custom node pack adds LM Studio integration to ComfyUI with:

- Model discovery (`/v1/models`)
- Optional model auto-load with load settings (`/api/v0/models/load`)
- Model control actions: list, load, unload
- Multimodal prompt input for image, video, and audio

## Nodes

1. **ICY LM Studio Models**
- Inputs: `base_url`, `timeout_seconds`
- Outputs:
  - `models_text`: newline-separated model IDs
  - `models_json`: raw JSON model list

2. **ICY LM Studio Multimodal Prompt**
- Inputs:
  - `base_url`, `model` (dropdown), `model_override`, `system_prompt`, `prompt`
  - Load settings: `auto_load_model`, `load_context_length`, `load_gpu_layers`, `load_threads`
  - Generation settings: `temperature`, `top_p`, `max_tokens`, `seed`, `timeout_seconds`
  - Cache controls: `enable_cache`, `clear_cache`
  - Output control: `only_after_think_tag` (if model includes chain-of-thought blocks)
  - Media:
    - Optional direct `image` input
    - Optional direct `frames` input (IMAGE batch from video decode nodes)
    - Optional direct `audio` input (AUDIO)
    - Fallback path fields: `video_path`, `audio_path`
    - `video_frames_to_process`, `video_frame_mode` control how many video frames are used
- Outputs:
  - `response_text`
  - `debug_json`

3. **ICY LM Studio Model Control**
- Inputs:
  - `action`: `list`, `load`, `unload`
  - `model` dropdown plus optional `model_override` (used by `load`/`unload`)
  - Load settings: `load_context_length`, `load_gpu_layers`, `load_threads`
- Outputs:
  - `status`
  - `models_text` (filled for `list` action)
  - `debug_json`

4. **ICY LM Studio Select Model**
- Inputs:
  - `models_text` from model listing
  - `model_index` to choose a model
- Outputs:
  - `model`
  - `models_json`

## Install

From your ComfyUI folder (or active Python environment):

```powershell
pip install -r custom_nodes/ICYLM/requirements.txt
```

## Usage

1. Start LM Studio local server (OpenAI-compatible API) on `http://127.0.0.1:1234`.
2. Add **ICY LM Studio Models** and run it to see available model IDs.
3. Pick a model from dropdown in **ICY LM Studio Multimodal Prompt**.
  - If dropdown is empty/unavailable, use `model_override`.
  - Or use **ICY LM Studio Select Model** with `model_index`.
4. Turn on `auto_load_model` if you want the node to try loading the model with your load settings.
  - Or use **ICY LM Studio Model Control** and choose `load` / `unload` manually.
5. Connect:
  - An `IMAGE` tensor input for image prompting.
  - Preferred: connect decoded video frames directly to `frames`.
  - Preferred: connect audio directly to `audio`.
  - Optional fallback: use filesystem paths in `video_path` / `audio_path`.
  - Set `video_frames_to_process` for exact frame count.
  - Choose `video_frame_mode`:
    - `evenly_spaced`: spread selected frames across the clip.
    - `first_n`: process the first N frames.

## Cache and seed behavior

- `seed` is sent to LM Studio request body to stabilize output behavior for compatible models.
- If `enable_cache` is true, identical runs reuse cached text and skip a new LM Studio call.
- Cache key includes model, prompt, image content signature, video/audio file signatures, video frame settings, generation settings, and seed.
- Set `clear_cache` to true for one run to reset memory cache.

## Think tag filtering

- If `only_after_think_tag` is true and the model output contains `</think>`, node output returns only text after that tag.
- If no `</think>` tag exists, full output is returned unchanged.

## Notes

- Video support requires `opencv-python`.
- Audio format support depends on LM Studio/model compatibility.
- If your LM Studio build uses a different model-load endpoint, set `auto_load_model` off and pre-load model manually.
