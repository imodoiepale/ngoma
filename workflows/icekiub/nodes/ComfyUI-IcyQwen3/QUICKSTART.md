# ComfyUI-IcyQwen3 🧊

**Made by [IceKiub](https://patreon.com/IceKiub)**

NSFW image and video captioning using Qwen3-VL Abliterated models.

## Quick Setup

1. Install: `pip install -r requirements.txt`
2. Load a model with **Icy Qwen3 VL Loader**
3. Connect to **Image Caption**, **Video Caption**, or **Batch Image Caption** nodes
4. Connect output to Show Text node

## Node Types

- **Loader**: Load model with quantization options (4bit, 8bit, FP8)
- **Image Caption**: Single image → caption
- **Video Caption**: Video frames → caption
- **Batch Caption**: Multiple images → captions
- **Unload**: Free VRAM

## Key Parameters

**Loader:**
- `quantization`: 4bit (fast, low VRAM) → 8bit → none (quality)
- `device`: auto / cuda / cpu
- `attention`: sdpa (default) / flash_attention_2

**Caption Nodes:**
- `seed`: Change to re-run (for caching control)
- `max_tokens`: 16-512 (more = longer captions)
- `temperature`: 0-2.0 (higher = more creative)
- `do_sample`: True (sampling) / False (greedy)

## Model Recommendations

**8GB VRAM**: 2B or 4B + 4bit quantization  
**12-16GB VRAM**: 4B or 8B + 4bit or 8bit  
**24GB+ VRAM**: 8B+ or 32B without quantization

## Models Available

All from [huihui-ai](https://huggingface.co/huihui-ai):
- Qwen3-VL-2B, 4B, 8B, 32B, 30B-A3B (Standard & Thinking variants)

## Troubleshooting

**Out of memory**: Use smaller model or 4bit quantization  
**transformers error**: `pip install --upgrade transformers>=4.57.0`  
**Flash Attention fails**: Normal on Windows, use default sdpa attention  

---

For full documentation, see README.md
