import base64
import hashlib
import io
import json
import mimetypes
import os
import sys
import tempfile
import time
import wave
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from PIL import Image


# Optional: PromptServer is used to push live streaming chunks to the frontend.
# Guarded so the node still works if the server module is unavailable.
try:
    from server import PromptServer
except Exception:
    PromptServer = None


# Enable ANSI escape sequence processing on Windows consoles so colored
# status lines render in cmd.exe / Windows Terminal when running batches.
if sys.platform == "win32":
    try:
        os.system("")
    except Exception:
        pass


# ANSI color codes used for console status lines during batched runs.
_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"
_ANSI_DIM = "\033[2m"
_ANSI_CYAN = "\033[36m"
_ANSI_YELLOW = "\033[33m"
_ANSI_GREEN = "\033[32m"
_ANSI_RED = "\033[31m"
_ANSI_MAGENTA = "\033[35m"

DEFAULT_BASE_URL = "http://127.0.0.1:1234"
_RESPONSE_CACHE: Dict[str, Dict[str, str]] = {}
_MODEL_OPTIONS_CACHE: List[str] = []
_BATCH_COUNTER = 0
_BATCH_STATS: Dict[str, Any] = {"count": 0, "tokens": 0, "time_ms": 0.0}


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def _server_error_message(response: requests.Response) -> str:
    error = _safe_json(response).get("error")
    if isinstance(error, dict):
        error = error.get("message")
    return str(error or response.text or "no error details returned by server")[:300]


def _to_data_url(file_bytes: bytes, mime_type: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _truncate_for_console(text: Any, max_len: int = 120) -> str:
    """Collapse whitespace and truncate long text for one-line console display."""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def _console(stage: str, message: str, color: str = _ANSI_CYAN) -> None:
    """Print a colored, bracketed status line to stdout.

    This is the visibility hook for batched runs: each call to the multimodal
    prompt node emits queue / cache / done / error lines so users can see
    exactly which prompt is currently being processed in the ComfyUI console.
    """
    try:
        line = (
            f"{color}[ICYLM]{_ANSI_BOLD} {stage} {_ANSI_RESET}"
            f"{color}>{_ANSI_RESET} {message}"
        )
        print(line, flush=True)
    except Exception:
        pass


def _next_batch_index() -> int:
    global _BATCH_COUNTER
    _BATCH_COUNTER += 1
    return _BATCH_COUNTER


def _reset_batch_state() -> None:
    global _BATCH_COUNTER
    _BATCH_COUNTER = 0
    _BATCH_STATS["count"] = 0
    _BATCH_STATS["tokens"] = 0
    _BATCH_STATS["time_ms"] = 0.0


def _capture_metrics(payload: Dict[str, Any], elapsed_ms: float, context_limit: int) -> Dict[str, Any]:
    """Extract token/speed/context metrics from an LM Studio response and roll them into the running batch totals.

    LM Studio returns OpenAI `usage` plus a llama.cpp-style `timings` object on chat completions.
    """
    usage = payload.get("usage") or {}
    timings = payload.get("timings") or {}

    completion_tokens = usage.get("completion_tokens") or timings.get("predicted_n") or 0
    prompt_tokens = usage.get("prompt_tokens") or timings.get("prompt_n") or 0

    tps = 0.0
    if completion_tokens and elapsed_ms > 0:
        tps = (float(completion_tokens) / elapsed_ms) * 1000.0

    _BATCH_STATS["count"] += 1
    _BATCH_STATS["tokens"] += int(completion_tokens)
    _BATCH_STATS["time_ms"] += float(elapsed_ms)

    used = int(prompt_tokens) + int(completion_tokens)
    limit = int(context_limit) if context_limit else 0
    context_pct = round((used / limit) * 100.0, 1) if limit > 0 else 0.0

    return {
        "completion_tokens": int(completion_tokens),
        "prompt_tokens": int(prompt_tokens),
        "tokens_per_second": round(tps, 2),
        "elapsed_ms": round(float(elapsed_ms), 1),
        "context_limit": limit,
        "context_used": used,
        "context_pct": context_pct,
        "batch_count": int(_BATCH_STATS["count"]),
        "batch_total_tokens": int(_BATCH_STATS["tokens"]),
        "batch_total_time_ms": round(float(_BATCH_STATS["time_ms"]), 1),
    }


def _fetch_model_ids(base_url: str = DEFAULT_BASE_URL, timeout_seconds: int = 3) -> List[str]:
    try:
        response = requests.get(_join_url(base_url, "/v1/models"), timeout=timeout_seconds)
        response.raise_for_status()
        payload = _safe_json(response)
        models = payload.get("data", [])
        return [m.get("id", "") for m in models if m.get("id")]
    except Exception:
        return []


def _get_model_dropdown_options() -> List[str]:
    global _MODEL_OPTIONS_CACHE
    fetched = _fetch_model_ids(DEFAULT_BASE_URL, timeout_seconds=2)
    if fetched:
        _MODEL_OPTIONS_CACHE = fetched

    if _MODEL_OPTIONS_CACHE:
        return _MODEL_OPTIONS_CACHE

    return ["<no models found - start LM Studio server>"]


def _resolve_model_value(model_dropdown: str, model_override: str) -> str:
    override = (model_override or "").strip()
    if override:
        return override

    selected = (model_dropdown or "").strip()
    if selected.startswith("<no models found"):
        return ""

    return selected


def _tensor_image_to_png_data_url(image_tensor: Any) -> Optional[str]:
    if image_tensor is None:
        return None

    # ComfyUI IMAGE tensors are [B, H, W, C] in float range [0, 1].
    arr = image_tensor[0].cpu().numpy()
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    pil_image = Image.fromarray(arr)
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    return _to_data_url(buffer.getvalue(), "image/png")


def _tensor_image_signature(image_tensor: Any) -> str:
    if image_tensor is None:
        return "none"

    arr = image_tensor[0].cpu().numpy()
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    return hashlib.sha256(arr.tobytes()).hexdigest()


def _select_frame_indices(total_frames: int, max_frames: int, frame_mode: str) -> List[int]:
    max_frames = max(1, int(max_frames))
    if total_frames <= max_frames:
        return list(range(total_frames))
    if frame_mode == "first_n":
        return list(range(max_frames))
    return np.linspace(0, total_frames - 1, max_frames, dtype=int).tolist()


def _tensor_frames_to_images(frames_tensor: Any, max_frames: int, frame_mode: str) -> List[Image.Image]:
    if frames_tensor is None:
        return []

    arr = frames_tensor.cpu().numpy()
    if arr.ndim != 4:
        return []

    total_frames = int(arr.shape[0])
    if total_frames <= 0:
        return []

    images: List[Image.Image] = []
    for idx in _select_frame_indices(total_frames, max_frames, frame_mode):
        frame = np.clip(arr[idx] * 255.0, 0, 255).astype(np.uint8)
        images.append(Image.fromarray(frame))
    return images


def _tensor_frames_signature(frames_tensor: Any, max_frames: int, frame_mode: str) -> str:
    if frames_tensor is None:
        return "none"

    arr = frames_tensor.cpu().numpy()
    if arr.ndim != 4 or arr.shape[0] <= 0:
        return "none"

    hasher = hashlib.sha256()
    for idx in _select_frame_indices(int(arr.shape[0]), max_frames, frame_mode):
        frame = np.clip(arr[idx] * 255.0, 0, 255).astype(np.uint8)
        hasher.update(frame.tobytes())
    return hasher.hexdigest()


def _audio_input_to_base64(audio_input: Any) -> Optional[Dict[str, str]]:
    if not audio_input or not isinstance(audio_input, dict):
        return None

    waveform = audio_input.get("waveform")
    sample_rate = int(audio_input.get("sample_rate", 16000))
    if waveform is None:
        return None

    arr = waveform.cpu().numpy()
    if arr.ndim == 3:
        arr = arr[0]
    elif arr.ndim == 1:
        arr = np.expand_dims(arr, axis=0)

    if arr.ndim != 2:
        return None

    channels = int(arr.shape[0])
    samples = int(arr.shape[1])
    pcm = np.clip(arr, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    interleaved = np.transpose(pcm, (1, 0)).reshape(samples * channels)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(interleaved.tobytes())

    return {
        "mime_type": "audio/wav",
        "data": base64.b64encode(wav_buffer.getvalue()).decode("utf-8"),
    }


def _audio_input_signature(audio_input: Any) -> str:
    if not audio_input or not isinstance(audio_input, dict):
        return "none"

    waveform = audio_input.get("waveform")
    sample_rate = int(audio_input.get("sample_rate", 16000))
    if waveform is None:
        return "none"

    arr = waveform.cpu().numpy()
    return _sha256_text(f"{sample_rate}|{arr.shape}|{arr.dtype}|" + hashlib.sha256(arr.tobytes()).hexdigest())


def _normalize_model_output_text(content_text: Any, only_after_think_tag: bool) -> str:
    if isinstance(content_text, list):
        content_text = "\n".join(
            part.get("text", str(part)) if isinstance(part, dict) else str(part)
            for part in content_text
        )

    text = str(content_text)
    if not only_after_think_tag:
        return text

    tag = "</think>"
    if tag in text:
        return text.split(tag, 1)[1].strip()

    return text


def _build_cache_key(
    base_url: str,
    model: str,
    system_prompt: str,
    prompt: str,
    image_signatures: List[str],
    frames_signature: str,
    video_path: str,
    video_frames_to_process: int,
    video_frame_mode: str,
    frames_as: str,
    video_fps: int,
    audio_input_signature: str,
    audio_path: str,
    audio_as: str,
    audio_transcript_hash: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    seed: int,
    only_after_think_tag: bool,
    thinking: str,
) -> str:
    video_sig = "none"
    if video_path and os.path.isfile(video_path):
        stat = os.stat(video_path)
        video_sig = f"{video_path}|{stat.st_mtime_ns}|{stat.st_size}"

    audio_sig = "none"
    if audio_path and os.path.isfile(audio_path):
        stat = os.stat(audio_path)
        audio_sig = f"{audio_path}|{stat.st_mtime_ns}|{stat.st_size}"

    key_payload = {
        "base_url": base_url,
        "model": model,
        "system_prompt_hash": _sha256_text(system_prompt),
        "prompt_hash": _sha256_text(prompt),
        "image_signatures": image_signatures,
        "frames_signature": frames_signature,
        "video_signature": video_sig,
        "video_frames_to_process": int(video_frames_to_process),
        "video_frame_mode": video_frame_mode,
        "frames_as": frames_as,
        "video_fps": int(video_fps),
        "audio_input_signature": audio_input_signature,
        "audio_signature": audio_sig,
        "audio_as": audio_as,
        "audio_transcript_hash": audio_transcript_hash,
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_tokens": int(max_tokens),
        "seed": int(seed),
        "only_after_think_tag": bool(only_after_think_tag),
        "thinking": thinking,
    }
    return _sha256_text(json.dumps(key_payload, sort_keys=True))


def _load_file_base64(path: str, fallback_mime: str) -> Optional[Dict[str, str]]:
    if not path or not os.path.isfile(path):
        return None

    with open(path, "rb") as f:
        file_bytes = f.read()

    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = fallback_mime

    return {
        "mime_type": mime_type,
        "data": base64.b64encode(file_bytes).decode("utf-8"),
    }


def _video_path_frames(video_path: str, max_frames: int, frame_mode: str) -> List[Image.Image]:
    if not video_path or not os.path.isfile(video_path):
        return []

    try:
        import cv2
    except Exception:
        return []

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        return []

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        capture.release()
        return []

    images: List[Image.Image] = []
    for idx in _select_frame_indices(total_frames, max_frames, frame_mode):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))

    capture.release()
    return images


def _frames_to_jpeg_data_urls(frame_images: List[Image.Image]) -> List[str]:
    data_urls: List[str] = []
    for pil_image in frame_images:
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90)
        data_urls.append(_to_data_url(buffer.getvalue(), "image/jpeg"))
    return data_urls


def _frames_to_mp4_data_url(frame_images: List[Image.Image], fps: int) -> Optional[str]:
    if not frame_images:
        return None

    try:
        import cv2
    except Exception:
        raise RuntimeError("opencv-python is required to encode frames as a video")

    width, height = frame_images[0].size
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), max(1, int(fps)), (width, height))
        if not writer.isOpened():
            raise RuntimeError("OpenCV could not open an mp4v video writer - check your opencv build")
        try:
            for pil_image in frame_images:
                if pil_image.size != (width, height):
                    pil_image = pil_image.resize((width, height))
                rgb = np.asarray(pil_image.convert("RGB"))
                writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        finally:
            writer.release()
        with open(path, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if not data:
        raise RuntimeError("video encoding produced an empty file")
    return _to_data_url(data, "video/mp4")


def _build_multimodal_content(
    prompt: str,
    image_data_urls: List[str],
    video_frame_urls: List[str],
    video_data_url: Optional[str],
    audio_b64: Optional[Dict[str, str]],
) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]

    for image_data_url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": image_data_url}})

    for frame_url in video_frame_urls:
        content.append({"type": "image_url", "image_url": {"url": frame_url}})

    if video_data_url:
        content.append({"type": "video_url", "video_url": {"url": video_data_url}})

    if audio_b64:
        # OpenAI-compatible audio input structure. LM Studio support depends on model/backend.
        content.append(
            {
                "type": "input_audio",
                "input_audio": {
                    "data": audio_b64["data"],
                    "format": audio_b64["mime_type"].split("/")[-1],
                },
            }
        )

    return content


class ICYLMStudioModels:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_url": ("STRING", {"default": DEFAULT_BASE_URL}),
                "timeout_seconds": ("INT", {"default": 30, "min": 1, "max": 180, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("models_text", "models_json")
    FUNCTION = "get_models"
    CATEGORY = "ICYLM/LM Studio"

    def get_models(self, base_url: str, timeout_seconds: int):
        url = _join_url(base_url, "/v1/models")
        try:
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            payload = _safe_json(response)
            models = payload.get("data", [])
            model_ids = [m.get("id", "") for m in models if m.get("id")]
            return ("\n".join(model_ids), json.dumps(models, indent=2))
        except Exception as exc:
            return (f"Failed to fetch models from {url}: {exc}", "[]")


class ICYLMStudioMultimodalPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # --- Model + prompts (primary workflow) ---
                "model": (
                    _get_model_dropdown_options(),
                    {"tooltip": "Model currently loaded or available in LM Studio. Refreshed from the server each time the menu opens."},
                ),
                "model_override": (
                    "STRING",
                    {"default": "", "tooltip": "Overrides the dropdown. Use when the model you want is not listed (e.g. not yet loaded)."},
                ),
                "system_prompt": (
                    "STRING",
                    {"multiline": True, "default": "You are a helpful multimodal assistant.", "tooltip": "System message describing how the model should behave."},
                ),
                "prompt": (
                    "STRING",
                    {"multiline": True, "default": "Describe what you see and hear.", "tooltip": "User prompt. Sent together with any attached image, video frames, or audio."},
                ),

                # --- Sampling ---
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 2147483647, "control_after_generate": True, "tooltip": "Random seed for generation. Use the control widget to randomize/increment between batch runs."},
                ),
                "temperature": (
                    "FLOAT",
                    {"default": 0.2, "min": 0.0, "max": 2.0, "step": 0.01, "display": "slider", "tooltip": "Higher = more random. 0.0 is greedy/deterministic on most backends."},
                ),
                "top_p": (
                    "FLOAT",
                    {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider", "tooltip": "Nucleus sampling cutoff. 1.0 disables it."},
                ),
                "max_tokens": (
                    "INT",
                    {"default": 512, "min": 1, "max": 8192, "tooltip": "Maximum number of tokens to generate in the response."},
                ),

                # --- Output behavior ---
                "thinking": (
                    ["model_default", "off", "low", "medium", "xhigh"],
                    {"default": "model_default", "tooltip": "Qwen3.5/3.8 thinking control via the template variables enable_thinking and reasoning_effort (levels: xhigh injects think-carefully instructions - the model.yaml default, medium is normal behavior, low keeps thinking brief). Sent per request as reasoning_effort + chat_template_kwargs, honored by llama.cpp server and vLLM. LM Studio ignores these on /v1/chat/completions - set the Enable Thinking / Reasoning Effort custom fields per model in LM Studio instead."},
                ),
                "only_after_think_tag": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "Strip chain-of-thought. Returns only text after </think> when present; otherwise returns the full output."},
                ),
                "enable_cache": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "Reuse identical previous responses to skip redundant LM Studio calls during batch runs."},
                ),
                "clear_cache": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "Clear the in-memory cache and reset the batch counter on this run."},
                ),

                # --- Media fallback paths ---
                "video_path": (
                    "STRING",
                    {"default": "", "tooltip": "Fallback video file path. Only used when no `frames` input is connected."},
                ),
                "video_frames_to_process": (
                    "INT",
                    {"default": 8, "min": 1, "max": 256, "tooltip": "How many frames to sample from the connected `frames` tensor or `video_path`."},
                ),
                "video_frame_mode": (
                    ["evenly_spaced", "first_n"],
                    {"tooltip": "evenly_spaced: spread frames across the clip. first_n: take the first N frames."},
                ),
                "frames_as": (
                    ["video", "frames"],
                    {"tooltip": "How sampled frames are sent: video encodes them into a short MP4 sent as one video part (needs a llama-server build with video input and FFmpeg on the server). frames sends them as individual images with a treat-as-video note."},
                ),
                "video_fps": (
                    "INT",
                    {"default": 8, "min": 1, "max": 60, "tooltip": "FPS used when encoding sampled frames as a video (frames_as=video). Set close to the source clip's fps so the model reads motion timing correctly."},
                ),
                "audio_path": (
                    "STRING",
                    {"default": "", "tooltip": "Fallback audio file path. Only used when no `audio` input is connected."},
                ),
                "audio_as": (
                    ["audio", "transcript"],
                    {"tooltip": "audio: send the audio itself as an input_audio part (needs a model/server with an audio-capable mmproj). transcript: skip the audio part and send audio_transcript text instead - use when the backend cannot process audio."},
                ),
                "audio_transcript": (
                    "STRING",
                    {"multiline": True, "default": "", "tooltip": "Transcript of the audio, included as a labeled text block in the prompt when audio_as=transcript."},
                ),

                # --- Advanced: connection + model load (collapsed by default) ---
                "base_url": (
                    "STRING",
                    {"default": DEFAULT_BASE_URL, "advanced": True, "tooltip": "LM Studio OpenAI-compatible base URL."},
                ),
                "timeout_seconds": (
                    "INT",
                    {"default": 120, "min": 1, "max": 600, "advanced": True, "tooltip": "HTTP timeout in seconds for the chat completion request."},
                ),
                "auto_load_model": (
                    "BOOLEAN",
                    {"default": False, "advanced": True, "tooltip": "Request LM Studio to load the selected model before prompting. Leave off if the model is already loaded."},
                ),
                "load_context_length": (
                    "INT",
                    {"default": 4096, "min": 512, "max": 262144, "step": 256, "advanced": True, "tooltip": "Context length passed to the load request when auto_load_model is on."},
                ),
                "stream_response": (
                    "BOOLEAN",
                    {"default": False, "advanced": True, "tooltip": "Stream the response token-by-token. When on, the ICYLM panel shows tokens typing live via websocket. The panel's lightning button toggles this."},
                ),
                "unload_after": (
                    "BOOLEAN",
                    {"default": False, "advanced": True, "tooltip": "Unload the model from the server after the response completes (llama.cpp /models/unload, LM Studio /api/v1/models/unload fallback). Frees VRAM between runs; the next prompt pays a full model reload."},
                ),
            },
            "optional": {
                "image": ("IMAGE", {"tooltip": "Optional image tensor. Takes priority over path-based media."}),
                "image2": ("IMAGE", {"tooltip": "Optional second reference image, sent after `image`."}),
                "image3": ("IMAGE", {"tooltip": "Optional third reference image, sent after `image2`."}),
                "image4": ("IMAGE", {"tooltip": "Optional fourth reference image, sent after `image3`."}),
                "image5": ("IMAGE", {"tooltip": "Optional fifth reference image, sent after `image4`."}),
                "image6": ("IMAGE", {"tooltip": "Optional sixth reference image, sent after `image5`."}),
                "image7": ("IMAGE", {"tooltip": "Optional seventh reference image, sent after `image6`."}),
                "image8": ("IMAGE", {"tooltip": "Optional eighth reference image, sent after `image7`."}),
                "frames": ("IMAGE", {"tooltip": "Optional IMAGE batch (e.g. decoded video frames). Takes priority over video_path."}),
                "audio": ("AUDIO", {"tooltip": "Optional audio tensor. Takes priority over audio_path."}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("response_text", "debug_json")
    FUNCTION = "run"
    CATEGORY = "ICYLM/LM Studio"

    def _load_model_if_requested(
        self,
        base_url: str,
        model: str,
        auto_load_model: bool,
        load_context_length: int,
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        if not auto_load_model:
            return {"status": "skipped"}

        load_url = _join_url(base_url, "/api/v1/models/load")
        body = {
            "model": model,
            "context_length": int(load_context_length),
        }
        response = requests.post(load_url, json=body, timeout=timeout_seconds)
        response.raise_for_status()
        return _safe_json(response)

    def _unload_model_after_run(self, base_url: str, model_id: str, timeout_seconds: int) -> Dict[str, Any]:
        detail = "server has no unload endpoint"

        # llama.cpp router mode: unload by model path/name.
        try:
            response = requests.post(_join_url(base_url, "/models/unload"), json={"model": model_id}, timeout=timeout_seconds)
            payload = _safe_json(response)
            # LM Studio answers unknown endpoints with HTTP 200 + an error body, so check both.
            if response.status_code < 400 and not payload.get("error"):
                return {"status": "ok", "endpoint": "/models/unload"}
            detail = _server_error_message(response)
        except Exception as exc:
            detail = str(exc)

        # LM Studio v1 API: unload by instance id (equals the model key for single-instance setups).
        try:
            response = requests.post(_join_url(base_url, "/api/v1/models/unload"), json={"instance_id": model_id}, timeout=timeout_seconds)
            payload = _safe_json(response)
            if response.status_code < 400 and not payload.get("error"):
                return {"status": "ok", "endpoint": "/api/v1/models/unload"}
            detail = _server_error_message(response)
        except Exception as exc:
            detail = str(exc)

        return {"status": "error", "detail": detail}

    def _stream_chat(
        self,
        chat_url: str,
        body: Dict[str, Any],
        timeout_seconds: int,
        node_id: Any,
    ) -> Dict[str, Any]:
        """Stream a chat completion from LM Studio, pushing each token delta to the frontend over websocket.

        Returns a payload shaped like a non-streaming chat completion so the caller can treat both paths uniformly.
        """
        response = requests.post(chat_url, json=body, timeout=timeout_seconds, stream=True)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {_server_error_message(response)}")

        accumulated: List[str] = []
        usage: Optional[Dict[str, Any]] = None
        timings: Optional[Dict[str, Any]] = None
        payload_model: Optional[str] = None

        for raw in response.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                chunk = json.loads(data_str)
            except Exception:
                continue

            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                delta_text = delta.get("content")
                if delta_text:
                    accumulated.append(delta_text)
                    if PromptServer is not None and node_id is not None:
                        try:
                            PromptServer.instance.send_sync("icylm_stream", {
                                "node_id": str(node_id),
                                "delta": delta_text,
                                "accumulated": "".join(accumulated),
                            })
                        except Exception:
                            pass

            if chunk.get("usage"):
                usage = chunk["usage"]
            if chunk.get("timings"):
                timings = chunk["timings"]
            if chunk.get("model"):
                payload_model = chunk["model"]

        content_text = "".join(accumulated)
        payload: Dict[str, Any] = {
            "choices": [{"message": {"content": content_text}}],
            "usage": usage or {},
        }
        if timings:
            payload["timings"] = timings
        if payload_model:
            payload["model"] = payload_model
        return payload

    def run(
        self,
        base_url: str,
        model: str,
        model_override: str,
        system_prompt: str,
        prompt: str,
        auto_load_model: bool,
        load_context_length: int,
        temperature: float,
        top_p: float,
        max_tokens: int,
        seed: int,
        enable_cache: bool,
        clear_cache: bool,
        only_after_think_tag: bool,
        thinking: str,
        stream_response: bool,
        unload_after: bool,
        timeout_seconds: int,
        video_path: str,
        video_frames_to_process: int,
        video_frame_mode: str,
        frames_as: str,
        video_fps: int,
        audio_path: str,
        audio_as: str,
        audio_transcript: str,
        image: Any = None,
        image2: Any = None,
        image3: Any = None,
        image4: Any = None,
        image5: Any = None,
        image6: Any = None,
        image7: Any = None,
        image8: Any = None,
        frames: Any = None,
        audio: Any = None,
        unique_id: Any = None,
    ):
        model = _resolve_model_value(model, model_override)
        if not model.strip():
            return ("Model is empty. Select from dropdown or set model_override.", "{}")

        if clear_cache:
            _RESPONSE_CACHE.clear()
            _reset_batch_state()

        batch_idx = _next_batch_index()
        prompt_preview = _truncate_for_console(prompt)
        media_bits: List[str] = []
        images = (image, image2, image3, image4, image5, image6, image7, image8)
        image_count = sum(1 for img in images if img is not None)
        if image_count:
            media_bits.append(f"images={image_count}")
        if frames is not None:
            media_bits.append(f"frames")
        if video_path.strip():
            media_bits.append(f"video={os.path.basename(video_path.strip())}")
        if audio is not None:
            media_bits.append("audio")
        if audio_path.strip():
            media_bits.append(f"audio={os.path.basename(audio_path.strip())}")
        media_summary = f" media=[{','.join(media_bits)}]" if media_bits else ""
        _console(
            "queue",
            f"#{batch_idx} model={model}{media_summary} prompt=\"{prompt_preview}\"",
            color=_ANSI_CYAN,
        )

        video_path = video_path.strip()
        audio_path = audio_path.strip()
        image_signatures = [_tensor_image_signature(img) for img in images]
        frames_signature = _tensor_frames_signature(frames, video_frames_to_process, video_frame_mode)
        audio_sig = _audio_input_signature(audio)
        cache_key = _build_cache_key(
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            prompt=prompt,
            image_signatures=image_signatures,
            frames_signature=frames_signature,
            video_path=video_path,
            video_frames_to_process=video_frames_to_process,
            video_frame_mode=video_frame_mode,
            frames_as=frames_as,
            video_fps=video_fps,
            audio_input_signature=audio_sig,
            audio_path=audio_path,
            audio_as=audio_as,
            audio_transcript_hash=_sha256_text(audio_transcript or ""),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            seed=seed,
            only_after_think_tag=only_after_think_tag,
            thinking=thinking,
        )

        if enable_cache and cache_key in _RESPONSE_CACHE:
            cached = _RESPONSE_CACHE[cache_key]
            _console(
                "cache",
                f"#{batch_idx} hit - reused cached response, skipped LM Studio call",
                color=_ANSI_YELLOW,
            )
            return (cached["response_text"], cached["debug_json"])

        image_data_urls: List[str] = []
        for img in images:
            url = _tensor_image_to_png_data_url(img)
            if url:
                image_data_urls.append(url)
        frame_images = _tensor_frames_to_images(frames, video_frames_to_process, video_frame_mode)
        used_direct_frames_input = frames is not None and bool(frame_images)
        if not frame_images:
            frame_images = _video_path_frames(video_path, video_frames_to_process, video_frame_mode)

        video_frame_urls: List[str] = []
        video_data_url: Optional[str] = None
        content_prompt = prompt
        if frame_images:
            mode_desc = (
                "sampled evenly across the full clip"
                if video_frame_mode == "evenly_spaced"
                else "taken from the start of the clip"
            )
            if frames_as == "video":
                video_data_url = _frames_to_mp4_data_url(frame_images, video_fps)
                content_prompt = (
                    f"[The attached video contains {len(frame_images)} frames {mode_desc}, "
                    f"played at {int(video_fps)} fps.]\n{prompt}"
                )
            else:
                video_frame_urls = _frames_to_jpeg_data_urls(frame_images)
                content_prompt = (
                    f"[The following {len(frame_images)} images are frames {mode_desc} of one continuous video. "
                    "Interpret them as a single video: describe the motion, camera movement, and temporal "
                    f"changes across the frames, not separate stills.]\n{prompt}"
                )

        audio_b64 = None
        if audio_as == "audio":
            audio_b64 = _audio_input_to_base64(audio)
            if audio_b64 is None:
                audio_b64 = _load_file_base64(audio_path, "audio/wav")

        transcript = (audio_transcript or "").strip()
        if audio_as == "transcript" and transcript:
            content_prompt = (
                "[Transcript of the audio for this request - the audio itself could not be attached]:\n"
                + transcript
                + "\n"
                + content_prompt
            )

        content = _build_multimodal_content(
            prompt=content_prompt,
            image_data_urls=image_data_urls,
            video_frame_urls=video_frame_urls,
            video_data_url=video_data_url,
            audio_b64=audio_b64,
        )

        debug_payload: Dict[str, Any] = {
            "model": model,
            "batch_index": batch_idx,
            "has_image": bool(image_data_urls),
            "image_count": len(image_data_urls),
            "video_frame_mode": video_frame_mode,
            "frames_as": frames_as,
            "video_frames_requested": int(video_frames_to_process),
            "video_frames_used": len(frame_images),
            "used_direct_frames_input": used_direct_frames_input,
            "used_video_part": bool(video_data_url),
            "has_audio": bool(audio_b64),
            "used_direct_audio_input": bool(audio_b64 and audio is not None),
            "audio_as": audio_as,
            "transcript_used": bool(audio_as == "transcript" and transcript),
            "seed": int(seed),
            "thinking": thinking,
            "cache_enabled": bool(enable_cache),
            "cache_hit": False,
            "cache_key": cache_key,
            "cache_size": len(_RESPONSE_CACHE),
        }

        try:
            load_result = self._load_model_if_requested(
                base_url=base_url,
                model=model,
                auto_load_model=auto_load_model,
                load_context_length=load_context_length,
                timeout_seconds=timeout_seconds,
            )
            debug_payload["load_result"] = load_result

            chat_url = _join_url(base_url, "/v1/chat/completions")
            messages: List[Dict[str, Any]] = []
            if system_prompt.strip():
                messages.append({"role": "system", "content": system_prompt.strip()})
            messages.append({"role": "user", "content": content})

            body = {
                "model": model,
                "messages": messages,
                "temperature": float(temperature),
                "top_p": float(top_p),
                "max_tokens": int(max_tokens),
                "seed": int(seed),
            }
            if thinking == "off":
                body["chat_template_kwargs"] = {"enable_thinking": False}
            elif thinking != "model_default":
                body["reasoning_effort"] = thinking
                body["chat_template_kwargs"] = {"enable_thinking": True, "reasoning_effort": thinking}

            t0 = time.time()
            payload: Dict[str, Any]
            if stream_response:
                payload = self._stream_chat(
                    chat_url=chat_url,
                    body=dict(body, stream=True, stream_options={"include_usage": True}),
                    timeout_seconds=timeout_seconds,
                    node_id=unique_id,
                )
            else:
                response = requests.post(chat_url, json=body, timeout=timeout_seconds)
                if response.status_code >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}: {_server_error_message(response)}")
                payload = _safe_json(response)
            elapsed_ms = (time.time() - t0) * 1000.0

            debug_payload["chat_response"] = payload
            debug_payload["streamed"] = bool(stream_response)
            debug_payload.update(_capture_metrics(payload, elapsed_ms, load_context_length))

            choices = payload.get("choices", [])
            if not choices:
                return ("No choices returned from LM Studio.", json.dumps(debug_payload, indent=2))

            message = choices[0].get("message", {})
            content_text = message.get("content", "")
            normalized_text = _normalize_model_output_text(content_text, only_after_think_tag)

            if unload_after:
                debug_payload["unload_result"] = self._unload_model_after_run(
                    base_url,
                    str(payload.get("model") or model),
                    timeout_seconds,
                )
                _console(
                    "unload",
                    f"#{batch_idx} unload_after: {debug_payload['unload_result'].get('status')}",
                    color=_ANSI_YELLOW,
                )

            result_debug_json = json.dumps(debug_payload, indent=2)
            if enable_cache:
                _RESPONSE_CACHE[cache_key] = {
                    "response_text": str(normalized_text),
                    "debug_json": result_debug_json,
                }

            response_preview = _truncate_for_console(normalized_text, 80)
            _console(
                "done",
                f"#{batch_idx} {len(normalized_text)} chars: \"{response_preview}\"",
                color=_ANSI_GREEN,
            )
            return (str(normalized_text), result_debug_json)

        except Exception as exc:
            debug_payload["error"] = str(exc)
            _console("error", f"#{batch_idx} {exc}", color=_ANSI_RED)
            return (f"LM Studio request failed: {exc}", json.dumps(debug_payload, indent=2))


class ICYLMStudioModelControl:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_url": ("STRING", {"default": DEFAULT_BASE_URL}),
                "action": (["list", "load", "unload"],),
                "model": (_get_model_dropdown_options(),),
                "model_override": ("STRING", {"default": ""}),
                "load_context_length": ("INT", {"default": 4096, "min": 512, "max": 262144, "step": 256}),
                "timeout_seconds": ("INT", {"default": 60, "min": 1, "max": 300, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("status", "models_text", "debug_json")
    FUNCTION = "run"
    CATEGORY = "ICYLM/LM Studio"

    def _list_models(self, base_url: str, timeout_seconds: int) -> Dict[str, Any]:
        response = requests.get(_join_url(base_url, "/v1/models"), timeout=timeout_seconds)
        response.raise_for_status()
        payload = _safe_json(response)
        models = payload.get("data", [])
        model_ids = [m.get("id", "") for m in models if m.get("id")]
        return {
            "status": f"Found {len(model_ids)} model(s)",
            "models_text": "\n".join(model_ids),
            "payload": payload,
        }

    def _load_model(
        self,
        base_url: str,
        model: str,
        load_context_length: int,
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        body = {
            "model": model,
            "context_length": int(load_context_length),
        }
        response = requests.post(_join_url(base_url, "/api/v1/models/load"), json=body, timeout=timeout_seconds)
        response.raise_for_status()
        payload = _safe_json(response)
        return {
            "status": f"Requested load for: {model}",
            "payload": payload,
        }

    def _unload_model(self, base_url: str, model: str, timeout_seconds: int) -> Dict[str, Any]:
        response = requests.post(_join_url(base_url, "/api/v1/models/unload"), json={"instance_id": model}, timeout=timeout_seconds)
        response.raise_for_status()
        payload = _safe_json(response)
        return {
            "status": f"Requested unload for: {model}",
            "payload": payload,
        }

    def run(
        self,
        base_url: str,
        action: str,
        model: str,
        model_override: str,
        load_context_length: int,
        timeout_seconds: int,
    ):
        model = _resolve_model_value(model, model_override)
        debug_payload: Dict[str, Any] = {
            "base_url": base_url,
            "action": action,
            "model": model,
        }

        try:
            if action == "list":
                result = self._list_models(base_url, timeout_seconds)
                debug_payload["result"] = result["payload"]
                return (result["status"], result["models_text"], json.dumps(debug_payload, indent=2))

            if not model.strip():
                return ("Model is required for load/unload actions.", "", json.dumps(debug_payload, indent=2))

            if action == "load":
                result = self._load_model(
                    base_url,
                    model,
                    load_context_length,
                    timeout_seconds,
                )
                debug_payload["result"] = result["payload"]
                return (result["status"], "", json.dumps(debug_payload, indent=2))

            if action == "unload":
                result = self._unload_model(base_url, model, timeout_seconds)
                debug_payload["result"] = result["payload"]
                return (result["status"], "", json.dumps(debug_payload, indent=2))

            return (f"Unknown action: {action}", "", json.dumps(debug_payload, indent=2))

        except Exception as exc:
            debug_payload["error"] = str(exc)
            return (f"Model control request failed: {exc}", "", json.dumps(debug_payload, indent=2))


class ICYLMStudioSelectModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "models_text": ("STRING", {"multiline": True, "default": ""}),
                "model_index": ("INT", {"default": 0, "min": 0, "max": 1024, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("model", "models_json")
    FUNCTION = "select"
    CATEGORY = "ICYLM/LM Studio"

    def select(self, models_text: str, model_index: int):
        models = [line.strip() for line in models_text.splitlines() if line.strip()]
        if not models:
            return ("", "[]")

        safe_index = max(0, min(int(model_index), len(models) - 1))
        return (models[safe_index], json.dumps(models, indent=2))


NODE_CLASS_MAPPINGS = {
    "ICYLMStudioModels": ICYLMStudioModels,
    "ICYLMStudioMultimodalPrompt": ICYLMStudioMultimodalPrompt,
    "ICYLMStudioModelControl": ICYLMStudioModelControl,
    "ICYLMStudioSelectModel": ICYLMStudioSelectModel,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ICYLMStudioModels": "❄️ Icy LM Studio Models (icekiub)",
    "ICYLMStudioMultimodalPrompt": "❄️ Icy Multimodal Prompt (icekiub)",
    "ICYLMStudioModelControl": "❄️ Icy Model Control (icekiub)",
    "ICYLMStudioSelectModel": "❄️ Icy Select Model (icekiub)",
}
