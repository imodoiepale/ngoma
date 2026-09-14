# ComfyUI-IcyQwen3 🧊

**Made by [IceKiub](https://patreon.com/IceKiub)**

A ComfyUI custom node pack for **NSFW image and video captioning** using **Qwen3-VL Abliterated** models from [huihui-ai](https://huggingface.co/huihui-ai).

These models have been "abliterated" (uncensored) and will no longer refuse to describe sensitive content.

## Features

- 🚀 **Fast loading and inference** with multiple optimization options
- 💾 **Memory efficient** - 4-bit, 8-bit, and FP8 quantization support
- 🎬 **Image & Video captioning** - Process single images, batches, or video frames
- 🧠 **Thinking mode** - Enhanced reasoning with Thinking model variants
- 🔄 **Model caching** - Avoids reloading when using the same model
- ⚡ **Flash Attention 2** support for maximum speed

## Supported Models

All models from [huihui-ai/Qwen3-VL-abliterated collection](https://huggingface.co/collections/huihui-ai/qwen3-vl-abliterated):

### Standard Instruct Models
| Model | VRAM (4-bit) | VRAM (8-bit) | VRAM (BF16) |
|-------|-------------|-------------|-------------|
| Qwen3-VL-2B-Instruct-abliterated | ~2GB | ~3GB | ~5GB |
| Qwen3-VL-4B-Instruct-abliterated | ~3GB | ~5GB | ~9GB |
| Qwen3-VL-4B-Instruct-abliterated-FP8 | ~4GB | - | - |
| Qwen3-VL-8B-Instruct-abliterated | ~6GB | ~10GB | ~18GB |
| Qwen3-VL-32B-Instruct-abliterated | ~20GB | ~35GB | ~65GB |
| Qwen3-VL-30B-A3B-Instruct-abliterated (MoE) | ~20GB | ~35GB | ~65GB |

### Thinking Models (Enhanced Reasoning)
- Qwen3-VL-2B-Thinking-abliterated
- Qwen3-VL-4B-Thinking-abliterated
- Qwen3-VL-8B-Thinking-abliterated
- Qwen3-VL-32B-Thinking-abliterated
- Qwen3-VL-30B-A3B-Thinking-abliterated

## Installation

### Option 1: ComfyUI Manager (Recommended)
Search for "IcyQwen3" in ComfyUI Manager and install.

### Option 2: Manual Installation
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/YOUR_USERNAME/ComfyUI-IcyQwen3
cd ComfyUI-IcyQwen3
pip install -r requirements.txt
```

### Requirements
- Python 3.10+
- PyTorch 2.0+ with CUDA
- transformers >= 4.57.0
- accelerate >= 0.26.0
- bitsandbytes >= 0.42.0 (for quantization)

## Nodes

### 🧊 Icy Qwen3 VL Loader
Load a Qwen3-VL model with optimization options.

**Inputs:**
- `model_name`: Select from available models
- `quantization`: none / 4bit / 8bit / fp8
- `device`: auto / cuda / cpu
- `attention`: sdpa / flash_attention_2 / eager
- `cpu_offload`: Enable for large models with limited VRAM
- `low_cpu_mem`: Reduce CPU memory during loading
- `max_pixels` / `min_pixels`: Control image resolution

### 🧊 Icy Qwen3 Image Caption
Generate captions for a single image.

**Inputs:**
- `model`: Connect from Loader node
- `image`: IMAGE input
- `seed`: Seed for generation (change to re-run)
- `prompt`: Your captioning prompt
- `max_tokens`: Maximum tokens to generate (16-512)
- `temperature`: Sampling temperature (0.0-2.0)
- `top_p` / `top_k`: Sampling parameters
- `do_sample`: Use sampling vs greedy decoding
- `enable_thinking`: Use thinking mode (for Thinking models)

### 🧊 Icy Qwen3 Video Caption
Generate captions for video frames.

**Inputs:**
- `model`: Connect from Loader node
- `frames`: Batch of images (IMAGE)
- `seed`: Seed for generation (change to re-run)
- `prompt`: Your captioning prompt
- `fps`: Frames per second info for the model
- `max_frames`: Maximum frames to process
- `max_tokens`: Maximum tokens to generate (16-512)
- `temperature`: Sampling temperature (0.0-2.0)
- `top_p`: Top-p sampling parameter
- `do_sample`: Use sampling vs greedy decoding

### 🧊 Icy Qwen3 Batch Image Caption
Caption multiple images in sequence.

**Inputs:**
- `model`: Connect from Loader node
- `images`: Batch of images (IMAGE)
- `seed`: Seed for generation (change to re-run)
- `prompt`: Prompt applied to each image
- `max_tokens`: Maximum tokens to generate (16-512)
- `temperature`: Sampling temperature (0.0-2.0)
- `top_p` / `top_k`: Sampling parameters
- `do_sample`: Use sampling vs greedy decoding
- `separator`: String between captions

### 🧊 Icy Qwen3 Unload Model
Free VRAM by unloading the model.

## Usage Tips

### For Low VRAM (8GB or less)
```
Model: Qwen3-VL-2B or 4B
Quantization: 4bit
Attention: sdpa
cpu_offload: True (if needed)
```

### For Medium VRAM (12-16GB)
```
Model: Qwen3-VL-4B or 8B
Quantization: 4bit or 8bit
Attention: flash_attention_2 (if available)
```

### For High VRAM (24GB+)
```
Model: Qwen3-VL-8B or larger
Quantization: none or 8bit
Attention: flash_attention_2
```

### Example Prompts

**Detailed Description:**
```
Describe this image in complete detail. Include all visible elements, 
their positions, colors, and any text. Be thorough and explicit.
```

**Character Focus:**
```
Describe the person(s) in this image in detail, including their 
appearance, clothing, pose, and expression.
```

**Scene Analysis:**
```
Analyze this scene. What is happening? Who is present? 
What is the setting and mood?
```

## Performance Tips

1. **Use 4-bit quantization** for the best VRAM/quality balance
2. **Enable Flash Attention 2** if your GPU supports it (RTX 3000+, Linux only)
3. **Reduce max_pixels** for faster processing with minor quality loss
4. **Use the Unload node** between different workflows to free memory
5. **Batch processing** uses less total time than processing one-by-one

## Troubleshooting

### "CUDA out of memory"
- Use a smaller model or enable 4-bit quantization
- Enable `cpu_offload`
- Reduce `max_pixels`
- Use the Unload node to free memory

### "KeyError: 'qwen3_vl'"
- Update transformers: `pip install --upgrade transformers`

### Flash Attention 2 not working
Flash Attention 2 provides significant speedups but has limited platform support:

**Linux**: Install with `pip install flash-attn --no-build-isolation`
- Requires Ampere GPU or newer (RTX 3000+)

**Windows**: Flash Attention 2 is **NOT officially supported** on Windows
- Prebuilt wheels are not available for most PyTorch/CUDA combinations
- Building from source fails due to CUTLASS compatibility issues
- **Workaround**: Use `attention: sdpa` instead (default, works well on all platforms)

If Flash Attention fails, the node will automatically fall back to SDPA (Scaled Dot Product Attention), which is efficient and works on all platforms.

## Credits

- **Creator**: [IceKiub](https://patreon.com/IceKiub) - Support on Patreon
- **Models**: [huihui-ai](https://huggingface.co/huihui-ai) for the abliterated Qwen3-VL models
- **Base Model**: [Qwen Team](https://huggingface.co/Qwen) for Qwen3-VL

## License

Apache 2.0 (same as the base Qwen3-VL models)

## Disclaimer

These models have reduced safety filtering. Use responsibly and in accordance with local laws and ethical standards. The developers are not responsible for any misuse.
