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
  - Load settings: `auto_load_model`, `load_context_length` (LM Studio v1 API)
  - Generation settings: `temperature`, `top_p`, `max_tokens`, `seed`, `timeout_seconds`
  - Cache controls: `enable_cache`, `clear_cache`
  - Output control: `only_after_think_tag` (if model includes chain-of-thought blocks)
  - `unload_after` (advanced): unload the model from the server after the response — llama.cpp router mode (`/models/unload`) or LM Studio (`/api/v1/models/unload` by instance id). Frees VRAM between runs; the next prompt triggers a full reload
  - Thinking toggle: `thinking` (`model_default` / `off` / `low` / `medium` / `xhigh`) — Qwen3.5/3.8 levels matching the model's chat template (`enable_thinking` + `reasoning_effort`). xhigh (the model.yaml default) injects think-carefully instructions, medium is normal, low keeps thinking brief. Sent per request as `reasoning_effort` + `chat_template_kwargs` (honored by llama.cpp server and vLLM). LM Studio ignores these on `/v1/chat/completions` — set the per-model **Enable Thinking** / **Reasoning Effort** custom fields in LM Studio instead.
  - Media:
    - Optional direct image inputs: `image` through `image8` (multi-reference prompting)
    - Optional direct `frames` input (IMAGE batch from video decode nodes)
    - Optional direct `audio` input (AUDIO)
    - Fallback path fields: `video_path`, `audio_path`
    - `audio_as`: `audio` sends the audio itself as an `input_audio` part (needs a model/server with an audio-capable mmproj); `transcript` skips the audio part and sends `audio_transcript` text as a labeled block instead - use when the backend cannot process audio
    - `video_frames_to_process`, `video_frame_mode` control how many video frames are used
    - `frames_as`: `video` (default) encodes sampled frames into a short MP4 sent as one `video_url` part — requires a llama-server build with video input and FFmpeg on the server; set `video_fps` near the source clip's fps. `frames` sends them as images with a treat-as-one-video note
- Outputs:
  - `response_text`
  - `debug_json`

3. **ICY LM Studio Model Control**
- Inputs:
  - `action`: `list`, `load`, `unload`
  - `model` dropdown plus optional `model_override` (used by `load`/`unload`)
  - Load settings: `load_context_length` (LM Studio v1 API: `/api/v1/models/load`; unload uses `/api/v1/models/unload` by instance id)
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
  - Up to eight `IMAGE` tensor inputs (`image` through `image8`) for multi-reference image prompting.
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
