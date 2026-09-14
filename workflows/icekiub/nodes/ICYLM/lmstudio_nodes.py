import base64
import hashlib
import io
import json
import mimetypes
import os
import sys
import wave
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from PIL import Image


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


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


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


def _reset_batch_counter() -> None:
    global _BATCH_COUNTER
    _BATCH_COUNTER = 0


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


def _tensor_frames_to_data_urls(frames_tensor: Any, max_frames: int, frame_mode: str) -> List[str]:
    if frames_tensor is None:
        return []

    arr = frames_tensor.cpu().numpy()
    if arr.ndim != 4:
        return []

    total_frames = int(arr.shape[0])
    if total_frames <= 0:
        return []

    max_frames = max(1, int(max_frames))
    if total_frames <= max_frames:
        frame_indices = list(range(total_frames))
    elif frame_mode == "first_n":
        frame_indices = list(range(max_frames))
    else:
        frame_indices = np.linspace(0, total_frames - 1, max_frames, dtype=int).tolist()

    data_urls: List[str] = []
    for idx in frame_indices:
        frame = np.clip(arr[idx] * 255.0, 0, 255).astype(np.uint8)
        pil_image = Image.fromarray(frame)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90)
        data_urls.append(_to_data_url(buffer.getvalue(), "image/jpeg"))

    return data_urls


def _tensor_frames_signature(frames_tensor: Any, max_frames: int, frame_mode: str) -> str:
    if frames_tensor is None:
        return "none"

    arr = frames_tensor.cpu().numpy()
    if arr.ndim != 4 or arr.shape[0] <= 0:
        return "none"

    total_frames = int(arr.shape[0])
    max_frames = max(1, int(max_frames))
    if total_frames <= max_frames:
        frame_indices = list(range(total_frames))
    elif frame_mode == "first_n":
        frame_indices = list(range(max_frames))
    else:
        frame_indices = np.linspace(0, total_frames - 1, max_frames, dtype=int).tolist()

    hasher = hashlib.sha256()
    for idx in frame_indices:
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
    image_signature: str,
    frames_signature: str,
    video_path: str,
    video_frames_to_process: int,
    video_frame_mode: str,
    audio_input_signature: str,
    audio_path: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    seed: int,
    only_after_think_tag: bool,
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
        "image_signature": image_signature,
        "frames_signature": frames_signature,
        "video_signature": video_sig,
        "video_frames_to_process": int(video_frames_to_process),
        "video_frame_mode": video_frame_mode,
        "audio_input_signature": audio_input_signature,
        "audio_signature": audio_sig,
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_tokens": int(max_tokens),
        "seed": int(seed),
        "only_after_think_tag": bool(only_after_think_tag),
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


def _sample_video_frames_as_data_urls(video_path: str, max_frames: int, frame_mode: str) -> List[str]:
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

    max_frames = max(1, int(max_frames))
    if total_frames <= max_frames:
        frame_indices = list(range(total_frames))
    elif frame_mode == "first_n":
        frame_indices = list(range(max_frames))
    else:
        frame_indices = np.linspace(0, total_frames - 1, max_frames, dtype=int).tolist()

    data_urls: List[str] = []
    for idx in frame_indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = capture.read()
        if not ok or frame is None:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90)
        data_urls.append(_to_data_url(buffer.getvalue(), "image/jpeg"))

    capture.release()
    return data_urls


def _build_multimodal_content(
    prompt: str,
    image_data_url: Optional[str],
    video_frame_urls: List[str],
    audio_b64: Optional[Dict[str, str]],
) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]

    if image_data_url:
        content.append({"type": "image_url", "image_url": {"url": image_data_url}})

    for frame_url in video_frame_urls:
        content.append({"type": "image_url", "image_url": {"url": frame_url}})

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
                "base_url": ("STRING", {"default": DEFAULT_BASE_URL}),
                "model": (_get_model_dropdown_options(),),
                "model_override": ("STRING", {"default": ""}),
                "system_prompt": (
                    "STRING",
                    {"multiline": True, "default": "You are a helpful multimodal assistant."},
                ),
                "prompt": ("STRING", {"multiline": True, "default": "Describe what you see and hear."}),
                "auto_load_model": ("BOOLEAN", {"default": False}),
                "load_context_length": ("INT", {"default": 4096, "min": 512, "max": 262144, "step": 256}),
                "load_gpu_layers": ("INT", {"default": -1, "min": -1, "max": 9999, "step": 1}),
                "load_threads": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 2.0, "step": 0.01}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "max_tokens": ("INT", {"default": 512, "min": 1, "max": 8192, "step": 1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647, "step": 1}),
                "enable_cache": ("BOOLEAN", {"default": True}),
                "clear_cache": ("BOOLEAN", {"default": False}),
                "only_after_think_tag": ("BOOLEAN", {"default": True}),
                "timeout_seconds": ("INT", {"default": 120, "min": 1, "max": 600, "step": 1}),
                "video_path": ("STRING", {"default": ""}),
                "video_frames_to_process": ("INT", {"default": 8, "min": 1, "max": 256, "step": 1}),
                "video_frame_mode": (["evenly_spaced", "first_n"],),
                "audio_path": ("STRING", {"default": ""}),
            },
            "optional": {
                "image": ("IMAGE",),
                "frames": ("IMAGE",),
                "audio": ("AUDIO",),
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
        load_gpu_layers: int,
        load_threads: int,
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        if not auto_load_model:
            return {"status": "skipped"}

        load_url = _join_url(base_url, "/api/v0/models/load")
        body = {
            "model": model,
            "identifier": model,
            "config": {
                "contextLength": int(load_context_length),
                "gpuLayers": int(load_gpu_layers),
                "threads": int(load_threads),
            },
        }
        response = requests.post(load_url, json=body, timeout=timeout_seconds)
        response.raise_for_status()
        return _safe_json(response)

    def run(
        self,
        base_url: str,
        model: str,
        model_override: str,
        system_prompt: str,
        prompt: str,
        auto_load_model: bool,
        load_context_length: int,
        load_gpu_layers: int,
        load_threads: int,
        temperature: float,
        top_p: float,
        max_tokens: int,
        seed: int,
        enable_cache: bool,
        clear_cache: bool,
        only_after_think_tag: bool,
        timeout_seconds: int,
        video_path: str,
        video_frames_to_process: int,
        video_frame_mode: str,
        audio_path: str,
        image: Any = None,
        frames: Any = None,
        audio: Any = None,
    ):
        model = _resolve_model_value(model, model_override)
        if not model.strip():
            return ("Model is empty. Select from dropdown or set model_override.", "{}")

        if clear_cache:
            _RESPONSE_CACHE.clear()
            _reset_batch_counter()

        batch_idx = _next_batch_index()
        prompt_preview = _truncate_for_console(prompt)
        media_bits: List[str] = []
        if image is not None:
            media_bits.append("image")
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
        image_signature = _tensor_image_signature(image)
        frames_signature = _tensor_frames_signature(frames, video_frames_to_process, video_frame_mode)
        audio_sig = _audio_input_signature(audio)
        cache_key = _build_cache_key(
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            prompt=prompt,
            image_signature=image_signature,
            frames_signature=frames_signature,
            video_path=video_path,
            video_frames_to_process=video_frames_to_process,
            video_frame_mode=video_frame_mode,
            audio_input_signature=audio_sig,
            audio_path=audio_path,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            seed=seed,
            only_after_think_tag=only_after_think_tag,
        )

        if enable_cache and cache_key in _RESPONSE_CACHE:
            cached = _RESPONSE_CACHE[cache_key]
            _console(
                "cache",
                f"#{batch_idx} hit - reused cached response, skipped LM Studio call",
                color=_ANSI_YELLOW,
            )
            return (cached["response_text"], cached["debug_json"])

        image_data_url = _tensor_image_to_png_data_url(image)
        direct_frame_urls = _tensor_frames_to_data_urls(frames, video_frames_to_process, video_frame_mode)
        if direct_frame_urls:
            video_frame_urls = direct_frame_urls
        else:
            video_frame_urls = _sample_video_frames_as_data_urls(
                video_path,
                video_frames_to_process,
                video_frame_mode,
            )

        audio_b64 = _audio_input_to_base64(audio)
        if audio_b64 is None:
            audio_b64 = _load_file_base64(audio_path, "audio/wav")

        content = _build_multimodal_content(
            prompt=prompt,
            image_data_url=image_data_url,
            video_frame_urls=video_frame_urls,
            audio_b64=audio_b64,
        )

        debug_payload: Dict[str, Any] = {
            "model": model,
            "has_image": bool(image_data_url),
            "video_frame_mode": video_frame_mode,
            "video_frames_requested": int(video_frames_to_process),
            "video_frames_used": len(video_frame_urls),
            "used_direct_frames_input": bool(direct_frame_urls),
            "has_audio": bool(audio_b64),
            "used_direct_audio_input": bool(audio_b64 and audio is not None),
            "seed": int(seed),
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
                load_gpu_layers=load_gpu_layers,
                load_threads=load_threads,
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

            response = requests.post(chat_url, json=body, timeout=timeout_seconds)
            response.raise_for_status()
            payload = _safe_json(response)
            debug_payload["chat_response"] = payload

            choices = payload.get("choices", [])
            if not choices:
                return ("No choices returned from LM Studio.", json.dumps(debug_payload, indent=2))

            message = choices[0].get("message", {})
            content_text = message.get("content", "")
            normalized_text = _normalize_model_output_text(content_text, only_after_think_tag)

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
                "load_gpu_layers": ("INT", {"default": -1, "min": -1, "max": 9999, "step": 1}),
                "load_threads": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1}),
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
        load_gpu_layers: int,
        load_threads: int,
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        body = {
            "model": model,
            "identifier": model,
            "config": {
                "contextLength": int(load_context_length),
                "gpuLayers": int(load_gpu_layers),
                "threads": int(load_threads),
            },
        }
        response = requests.post(_join_url(base_url, "/api/v0/models/load"), json=body, timeout=timeout_seconds)
        response.raise_for_status()
        payload = _safe_json(response)
        return {
            "status": f"Requested load for: {model}",
            "payload": payload,
        }

    def _unload_model(self, base_url: str, model: str, timeout_seconds: int) -> Dict[str, Any]:
        body = {
            "model": model,
            "identifier": model,
        }
        response = requests.post(_join_url(base_url, "/api/v0/models/unload"), json=body, timeout=timeout_seconds)
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
        load_gpu_layers: int,
        load_threads: int,
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
                    load_gpu_layers,
                    load_threads,
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
    "ICYLMStudioModels": "ICY LM Studio Models",
    "ICYLMStudioMultimodalPrompt": "ICY LM Studio Multimodal Prompt",
    "ICYLMStudioModelControl": "ICY LM Studio Model Control",
    "ICYLMStudioSelectModel": "ICY LM Studio Select Model",
}
