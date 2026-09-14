"""
ComfyUI-IcyQwen3 - NSFW Image/Video Captioning using Qwen3-VL Abliterated Models
Fast loading and inference with quantization, FP8, and offloading support

Supported models from huihui-ai:
- Huihui-Qwen3-VL-2B-Instruct-abliterated
- Huihui-Qwen3-VL-4B-Instruct-abliterated (+ FP8 variant)
- Huihui-Qwen3-VL-8B-Instruct-abliterated
- Huihui-Qwen3-VL-32B-Instruct-abliterated
- Huihui-Qwen3-VL-30B-A3B-Instruct-abliterated (MoE)
- Thinking variants available for all sizes
"""

from .nodes import (
    IcyQwen3AllInOne,
    IcyQwen3Unload,
)

NODE_CLASS_MAPPINGS = {
    "IcyQwen3AllInOne": IcyQwen3AllInOne,
    "IcyQwen3Unload": IcyQwen3Unload,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IcyQwen3AllInOne": "🧊 Icy Qwen3 All-In-One",
    "IcyQwen3Unload": "🧊 Icy Qwen3 Unload Model",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print("\033[34mComfyUI-IcyQwen3: \033[92mLoaded successfully - Qwen3-VL Abliterated Models\033[0m")
