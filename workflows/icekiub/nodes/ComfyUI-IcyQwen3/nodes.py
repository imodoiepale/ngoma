"""
ComfyUI-IcyQwen3 Nodes
Qwen3-VL Abliterated model nodes for uncensored image/video captioning
"""

import gc
import os
import platform
import torch
import numpy as np
from PIL import Image
from typing import Optional, Tuple, Dict, Any

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Model manager singleton
_model_manager = None


def get_autocast_context():
    """
    Get the appropriate autocast context manager for the current platform.
    Windows requires torch.cuda.amp.autocast, Linux can use torch.amp.autocast.
    """
    if IS_WINDOWS:
        return torch.cuda.amp.autocast(enabled=True, dtype=torch.bfloat16)
    else:
        return torch.amp.autocast('cuda', enabled=True, dtype=torch.bfloat16)


def apply_windows_optimizations():
    """Apply Windows-specific performance optimizations"""
    if not IS_WINDOWS:
        return
    
    # Set environment variables for better Windows CUDA performance
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CLOBBERING", "1")
    
    # Windows has slower file I/O, so we want to minimize file operations
    # Disable HuggingFace telemetry to reduce network/file overhead
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    
    if torch.cuda.is_available():
        # Enable TF32 for faster matmuls on Ampere+ GPUs
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        # Enable cudnn benchmark for optimized kernels
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        print("[IcyQwen3] Applied Windows CUDA optimizations")


# Apply Windows optimizations at module load
apply_windows_optimizations()


def get_model_manager():
    """Get or create the model manager singleton"""
    global _model_manager
    if _model_manager is None:
        _model_manager = Qwen3VLModelManager()
    return _model_manager


# Available models from huihui-ai
AVAILABLE_MODELS = {
    # Standard Instruct models
    "Qwen3-VL-2B-Instruct-abliterated": "huihui-ai/Huihui-Qwen3-VL-2B-Instruct-abliterated",
    "Qwen3-VL-4B-Instruct-abliterated": "huihui-ai/Huihui-Qwen3-VL-4B-Instruct-abliterated",
    "Qwen3-VL-4B-Instruct-abliterated-FP8": "huihui-ai/Huihui-Qwen3-VL-4B-Instruct-abliterated-FP8",
    "Qwen3-VL-8B-Instruct-abliterated": "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated",
    "Qwen3-VL-32B-Instruct-abliterated": "huihui-ai/Huihui-Qwen3-VL-32B-Instruct-abliterated",
    "Qwen3-VL-30B-A3B-Instruct-abliterated": "huihui-ai/Huihui-Qwen3-VL-30B-A3B-Instruct-abliterated",
    # Thinking variants (enhanced reasoning)
    "Qwen3-VL-2B-Thinking-abliterated": "huihui-ai/Huihui-Qwen3-VL-2B-Thinking-abliterated",
    "Qwen3-VL-4B-Thinking-abliterated": "huihui-ai/Huihui-Qwen3-VL-4B-Thinking-abliterated",
    "Qwen3-VL-8B-Thinking-abliterated": "huihui-ai/Huihui-Qwen3-VL-8B-Thinking-abliterated",
    "Qwen3-VL-32B-Thinking-abliterated": "huihui-ai/Huihui-Qwen3-VL-32B-Thinking-abliterated",
    "Qwen3-VL-30B-A3B-Thinking-abliterated": "huihui-ai/Huihui-Qwen3-VL-30B-A3B-Thinking-abliterated",
}

# Quantization options
QUANTIZATION_OPTIONS = [
    "none",
    "4bit",           # BitsAndBytes 4-bit quantization
    "8bit",           # BitsAndBytes 8-bit quantization
    "fp8",            # FP8 (for models that support it natively)
]

# Device mapping options  
DEVICE_OPTIONS = [
    "auto",           # Automatic device mapping
    "cuda",           # Force CUDA (uses first GPU)
    "cpu",            # Force CPU (slow but works)
]

# Attention implementation options
ATTENTION_OPTIONS = [
    "sdpa",           # Scaled Dot Product Attention (default, good balance)
    "flash_attention_2",  # Flash Attention 2 (fastest, requires compatible GPU)
    "eager",          # Eager attention (most compatible)
]


class Qwen3VLModelManager:
    """
    Singleton manager for Qwen3-VL models with caching and memory optimization.
    Handles model loading, unloading, and memory management.
    """
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.current_model_id: Optional[str] = None
        self.current_config: Optional[Dict[str, Any]] = None
        
    def load_model(
        self,
        model_name: str,
        quantization: str = "none",
        device: str = "auto",
        attention: str = "sdpa",
        cpu_offload: bool = False,
        low_cpu_mem: bool = True,
        trust_remote_code: bool = True,
        max_pixels: int = 1280 * 28 * 28,
        min_pixels: int = 256 * 28 * 28,
    ) -> Tuple[Any, Any]:
        """
        Load or return cached Qwen3-VL model and processor.
        
        Args:
            model_name: Key from AVAILABLE_MODELS
            quantization: Quantization method
            device: Device mapping
            attention: Attention implementation
            cpu_offload: Enable CPU offloading for large models
            low_cpu_mem: Use low CPU memory mode during loading
            trust_remote_code: Trust remote code from HuggingFace
            max_pixels: Maximum pixels for image processing
            min_pixels: Minimum pixels for image processing
        
        Returns:
            Tuple of (model, processor)
        """
        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        
        model_id = AVAILABLE_MODELS.get(model_name, model_name)
        
        # Create config dict for cache comparison
        config = {
            "model_id": model_id,
            "quantization": quantization,
            "device": device,
            "attention": attention,
            "cpu_offload": cpu_offload,
        }
        
        # Check if we already have this exact model loaded
        if (self.model is not None and 
            self.current_model_id == model_id and 
            self.current_config == config):
            print(f"[IcyQwen3] Using cached model: {model_name}")
            return self.model, self.processor
        
        # Unload existing model if different
        if self.model is not None:
            self.unload()
        
        print(f"[IcyQwen3] Loading model: {model_name} ({model_id})")
        print(f"[IcyQwen3] Config: quantization={quantization}, device={device}, attention={attention}")
        print(f"[IcyQwen3] Platform: {platform.system()} ({platform.machine()})")
        
        # Windows-specific optimizations for faster file I/O
        if IS_WINDOWS:
            # Disable symlink warnings on Windows (HuggingFace hub)
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            # Use memory-efficient loading on Windows
            os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")  # hf_transfer has issues on Windows
            # Enable faster CUDA operations
            if torch.cuda.is_available():
                # These settings help with Windows CUDA performance
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
        
        # Prepare loading kwargs
        load_kwargs = {
            "trust_remote_code": trust_remote_code,
        }
        
        # On Windows, low_cpu_mem_usage can actually be SLOWER due to different memory mapping
        # Only use it on Linux or when explicitly requested
        if low_cpu_mem:
            if IS_LINUX:
                load_kwargs["low_cpu_mem_usage"] = True
            elif IS_WINDOWS:
                # On Windows, prefer faster loading over memory efficiency
                print("[IcyQwen3] Windows detected: using faster loading (may use more RAM)")
                load_kwargs["low_cpu_mem_usage"] = False
            else:
                load_kwargs["low_cpu_mem_usage"] = low_cpu_mem
        
        # Handle device mapping
        if device == "auto":
            load_kwargs["device_map"] = "auto"
        elif device == "cpu":
            load_kwargs["device_map"] = "cpu"
        else:
            load_kwargs["device_map"] = device
        
        # Handle attention implementation
        # IMPORTANT: Flash Attention 2 is NOT supported on Windows!
        # It will silently fail and fall back to eager (very slow)
        if attention == "flash_attention_2":
            if IS_WINDOWS:
                print("[IcyQwen3] WARNING: Flash Attention 2 is not supported on Windows. Using sdpa instead.")
                # sdpa is well optimized on Windows with PyTorch 2.0+
                load_kwargs["attn_implementation"] = "sdpa"
            else:
                load_kwargs["attn_implementation"] = "flash_attention_2"
        elif attention == "eager":
            load_kwargs["attn_implementation"] = "eager"
        elif attention == "sdpa":
            # Explicitly use sdpa - this is well optimized on Windows
            load_kwargs["attn_implementation"] = "sdpa"
        
        # Handle quantization
        if quantization == "4bit":
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        elif quantization == "8bit":
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=True,
            )
        elif quantization == "fp8" or "FP8" in model_name:
            # FP8 models load with bfloat16 dtype, the weights are already FP8
            load_kwargs["torch_dtype"] = torch.bfloat16
        elif quantization == "none":
            load_kwargs["torch_dtype"] = torch.bfloat16
        
        # Load processor with pixel settings
        print("[IcyQwen3] Loading processor...")
        self.processor = AutoProcessor.from_pretrained(
            model_id,
            trust_remote_code=trust_remote_code,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
        )
        
        # Load model
        print("[IcyQwen3] Loading model weights... (this may take a while)")
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_id,
            **load_kwargs
        )
        
        # Enable CPU offloading if requested (for large models)
        if cpu_offload and hasattr(self.model, 'enable_model_cpu_offload'):
            print("[IcyQwen3] Enabling CPU offload...")
            self.model.enable_model_cpu_offload()
        
        # Set to eval mode
        self.model.eval()
        
        # Enable CUDA optimizations for faster generation
        if torch.cuda.is_available():
            # Enable TF32 for faster matmuls on Ampere+ GPUs
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            # Enable cudnn benchmark for optimized kernels
            torch.backends.cudnn.benchmark = True
            # Windows-specific: reduce CUDA synchronization overhead
            if IS_WINDOWS:
                # Disable CUDA caching allocator garbage collection
                # This reduces synchronization overhead on Windows
                os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CLOBBERING", "1")
        
        # Store config for cache comparison
        self.current_model_id = model_id
        self.current_config = config
        
        print("[IcyQwen3] Model loaded successfully!")
        return self.model, self.processor
    
    def unload(self):
        """Unload the current model and free memory"""
        if self.model is not None:
            print(f"[IcyQwen3] Unloading model: {self.current_model_id}")
            del self.model
            self.model = None
        
        if self.processor is not None:
            del self.processor
            self.processor = None
        
        self.current_model_id = None
        self.current_config = None
        
        # Force garbage collection and clear CUDA cache
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        print("[IcyQwen3] Model unloaded and memory freed")
    
    def is_loaded(self) -> bool:
        """Check if a model is currently loaded"""
        return self.model is not None


class IcyQwen3ModelLoader:
    """
    Load Qwen3-VL abliterated models with various optimization options.
    Supports quantization (4bit, 8bit, FP8), CPU offloading, and attention optimizations.
    """
    
    CATEGORY = "IcyQwen3"
    FUNCTION = "load_model"
    RETURN_TYPES = ("ICYQWEN3_MODEL",)
    RETURN_NAMES = ("model",)
    DESCRIPTION = "Load Qwen3-VL abliterated models for uncensored image/video captioning"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (list(AVAILABLE_MODELS.keys()), {
                    "default": "Qwen3-VL-4B-Instruct-abliterated",
                    "tooltip": "Select the Qwen3-VL model to load. Larger models (8B, 32B) produce better quality but require more VRAM. 'Thinking' variants have enhanced reasoning."
                }),
                "quantization": (QUANTIZATION_OPTIONS, {
                    "default": "4bit",
                    "tooltip": "Quantization method for VRAM reduction. 4bit = lowest VRAM, good quality. 8bit = moderate VRAM, better quality. None/FP8 = full quality, highest VRAM."
                }),
                "device": (DEVICE_OPTIONS, {
                    "default": "auto",
                    "tooltip": "Device to load model on. 'auto' automatically detects and uses GPU if available. 'cuda' forces GPU. 'cpu' forces CPU (slow but works without GPU)."
                }),
                "attention": (ATTENTION_OPTIONS, {
                    "default": "sdpa",
                    "tooltip": "Attention implementation. 'sdpa' (default) works on all platforms. 'flash_attention_2' is fastest but requires Ampere+ GPU on Linux. 'eager' is most compatible but slowest."
                }),
            },
            "optional": {
                "cpu_offload": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable CPU offloading for large models. Offloads model layers to CPU when not in use. Useful when VRAM is limited but increases processing time."
                }),
                "low_cpu_mem": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Reduce CPU memory usage during model loading. Recommended for systems with limited RAM. May slightly increase load time."
                }),
                "max_pixels": ("INT", {
                    "default": 1003520,  # 1280 * 28 * 28
                    "min": 200704,       # 256 * 28 * 28
                    "max": 12845056,     # 16384 * 28 * 28
                    "step": 784,         # 28 * 28
                    "tooltip": "Maximum pixels for image processing. Higher values preserve more detail but require more VRAM and are slower. Default is good balance."
                }),
                "min_pixels": ("INT", {
                    "default": 200704,   # 256 * 28 * 28
                    "min": 784,          # 1 * 28 * 28
                    "max": 1003520,      # 1280 * 28 * 28
                    "step": 784,
                    "tooltip": "Minimum pixels for image processing. Ensures images are scaled up if too small. Lower values may lose detail but save VRAM."
                }),
            }
        }
    
    def load_model(
        self,
        model_name: str,
        quantization: str,
        device: str,
        attention: str,
        cpu_offload: bool = False,
        low_cpu_mem: bool = True,
        max_pixels: int = 1003520,
        min_pixels: int = 200704,
    ):
        manager = get_model_manager()
        model, processor = manager.load_model(
            model_name=model_name,
            quantization=quantization,
            device=device,
            attention=attention,
            cpu_offload=cpu_offload,
            low_cpu_mem=low_cpu_mem,
            max_pixels=max_pixels,
            min_pixels=min_pixels,
        )
        
        # Return a reference dict that nodes can use
        model_ref = {
            "model": model,
            "processor": processor,
            "model_name": model_name,
        }
        
        return (model_ref,)


class IcyQwen3ImageCaption:
    """
    Generate captions for images using Qwen3-VL abliterated models.
    Supports custom prompts for detailed, uncensored image descriptions.
    """
    
    CATEGORY = "IcyQwen3"
    FUNCTION = "caption_image"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("caption",)
    OUTPUT_NODE = False
    DESCRIPTION = "Generate uncensored captions for images using Qwen3-VL"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("ICYQWEN3_MODEL",),
                "image": ("IMAGE",),
                "prompt": ("STRING", {
                    "default": "Describe this image in detail.",
                    "multiline": True,
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
            },
            "optional": {
                "max_tokens": ("INT", {
                    "default": 512,
                    "min": 16,
                    "max": 4096,
                    "step": 16,
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.05,
                }),
                "top_p": ("FLOAT", {
                    "default": 0.8,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "top_k": ("INT", {
                    "default": 20,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                }),
                "do_sample": ("BOOLEAN", {"default": True}),
                "enable_thinking": ("BOOLEAN", {"default": False}),
            }
        }
    
    @classmethod
    def IS_CHANGED(cls, seed, **kwargs):
        # Return seed so node re-runs when seed changes
        return seed
    
    def caption_image(
        self,
        model: Dict[str, Any],
        image: torch.Tensor,
        prompt: str,
        seed: int = 0,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 20,
        do_sample: bool = True,
        enable_thinking: bool = False,
    ):
        # Set seed for reproducibility
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
        
        qwen_model = model["model"]
        processor = model["processor"]
        
        # Convert ComfyUI image tensor to PIL Image
        # ComfyUI images are [B, H, W, C] in 0-1 range
        if len(image.shape) == 4:
            image = image[0]  # Take first image from batch
        
        # Convert to numpy, scale to 0-255, convert to PIL
        img_np = (image.cpu().numpy() * 255).astype(np.uint8)
        pil_image = Image.fromarray(img_np, mode='RGB')
        
        # Build messages with thinking mode if enabled
        text_prompt = prompt
        if enable_thinking and "Thinking" in model.get("model_name", ""):
            text_prompt = f"/think\n{prompt}"
        
        # Build the conversation with image
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {"type": "text", "text": text_prompt},
                ],
            }
        ]
        
        # Process inputs using the Qwen3-VL processor
        # The processor's apply_chat_template handles images directly
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )
        
        # Move all tensors to the model's device
        inputs = {k: v.to(qwen_model.device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample,
            "use_cache": True,  # Enable KV cache for faster generation
            "pad_token_id": processor.tokenizer.pad_token_id,
        }
        
        if do_sample:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
            gen_kwargs["top_k"] = top_k
        
        # Generate with CUDA graph optimization when possible
        with torch.inference_mode(), get_autocast_context():
            generated_ids = qwen_model.generate(**inputs, **gen_kwargs)
        
        # Decode output - trim the input tokens from the output
        input_len = inputs['input_ids'].shape[1]
        generated_ids_trimmed = generated_ids[:, input_len:]
        
        output_text = processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )[0]
        
        # Ensure it's a proper string
        if output_text is None:
            output_text = ""
        output_text = str(output_text).strip()
        
        return (output_text,)


class IcyQwen3VideoCaption:
    """
    Generate captions for videos using Qwen3-VL abliterated models.
    Supports frame extraction and temporal understanding.
    """
    
    CATEGORY = "IcyQwen3"
    FUNCTION = "caption_video"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("caption",)
    OUTPUT_NODE = False
    DESCRIPTION = "Generate uncensored captions for videos using Qwen3-VL"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("ICYQWEN3_MODEL",),
                "frames": ("IMAGE",),  # Batch of frames [B, H, W, C]
                "prompt": ("STRING", {
                    "default": "Describe what is happening in this video in detail.",
                    "multiline": True,
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
            },
            "optional": {
                "fps": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.1,
                    "max": 30.0,
                    "step": 0.1,
                }),
                "max_frames": ("INT", {
                    "default": 32,
                    "min": 1,
                    "max": 128,
                    "step": 1,
                }),
                "max_tokens": ("INT", {
                    "default": 1024,
                    "min": 16,
                    "max": 8192,
                    "step": 16,
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.05,
                }),
                "top_p": ("FLOAT", {
                    "default": 0.8,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "do_sample": ("BOOLEAN", {"default": True}),
            }
        }
    
    @classmethod
    def IS_CHANGED(cls, seed, **kwargs):
        return seed
    
    def caption_video(
        self,
        model: Dict[str, Any],
        frames: torch.Tensor,
        prompt: str,
        seed: int = 0,
        fps: float = 1.0,
        max_frames: int = 32,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.8,
        do_sample: bool = True,
    ):
        # Set seed for reproducibility
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
        
        qwen_model = model["model"]
        processor = model["processor"]
        
        # frames is [B, H, W, C] in 0-1 range
        batch_size = frames.shape[0]
        
        # Sample frames if we have more than max_frames
        if batch_size > max_frames:
            indices = np.linspace(0, batch_size - 1, max_frames, dtype=int)
            frames = frames[indices]
            batch_size = max_frames
        
        # Convert frames to list of PIL Images
        frame_list = []
        for i in range(batch_size):
            frame_np = (frames[i].cpu().numpy() * 255).astype(np.uint8)
            pil_frame = Image.fromarray(frame_np, mode='RGB')
            frame_list.append(pil_frame)
        
        # Build video content for Qwen3-VL
        video_content = {
            "type": "video",
            "video": frame_list,
            "fps": fps,
        }
        
        messages = [
            {
                "role": "user",
                "content": [
                    video_content,
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Process inputs
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )
        
        # Move all tensors to the model's device
        inputs = {k: v.to(qwen_model.device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample,
            "use_cache": True,
            "pad_token_id": processor.tokenizer.pad_token_id,
        }
        
        if do_sample:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
        
        # Generate with optimizations
        with torch.inference_mode(), get_autocast_context():
            generated_ids = qwen_model.generate(**inputs, **gen_kwargs)
        
        # Decode output
        input_len = inputs['input_ids'].shape[1]
        generated_ids_trimmed = generated_ids[:, input_len:]
        
        output_text = processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )[0]
        
        return (output_text,)


class IcyQwen3BatchImageCaption:
    """
    Generate captions for multiple images in a batch.
    Processes images sequentially to manage memory.
    """
    
    CATEGORY = "IcyQwen3"
    FUNCTION = "caption_batch"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("captions",)
    OUTPUT_NODE = False
    DESCRIPTION = "Generate captions for a batch of images"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("ICYQWEN3_MODEL",),
                "images": ("IMAGE",),  # Batch of images [B, H, W, C]
                "prompt": ("STRING", {
                    "default": "Describe this image in detail.",
                    "multiline": True,
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
            },
            "optional": {
                "max_tokens": ("INT", {
                    "default": 256,
                    "min": 16,
                    "max": 2048,
                    "step": 16,
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.05,
                }),
                "top_p": ("FLOAT", {
                    "default": 0.8,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "top_k": ("INT", {
                    "default": 20,
                    "min": 1,
                    "max": 100,
                }),
                "separator": ("STRING", {
                    "default": "\n---\n",
                }),
                "do_sample": ("BOOLEAN", {"default": True}),
            }
        }
    
    def caption_batch(
        self,
        model: Dict[str, Any],
        images: torch.Tensor,
        prompt: str,
        seed: int = 0,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 20,
        separator: str = "\n---\n",
        do_sample: bool = True,
    ):
        # Set seed for reproducibility and to control ComfyUI caching
        torch.manual_seed(seed)
        qwen_model = model["model"]
        processor = model["processor"]
        
        batch_size = images.shape[0]
        captions = []
        
        for i in range(batch_size):
            # Convert single image
            img_np = (images[i].cpu().numpy() * 255).astype(np.uint8)
            pil_image = Image.fromarray(img_np, mode='RGB')
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": pil_image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            
            # Process
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt"
            )
            
            # Move all tensors to the model's device
            inputs = {k: v.to(qwen_model.device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}
            
            gen_kwargs = {
                "max_new_tokens": max_tokens,
                "do_sample": do_sample,
                "use_cache": True,
                "pad_token_id": processor.tokenizer.pad_token_id,
            }
            if do_sample:
                gen_kwargs["temperature"] = temperature
                gen_kwargs["top_p"] = top_p
                gen_kwargs["top_k"] = top_k
            
            # Generate with optimizations
            with torch.inference_mode(), get_autocast_context():
                generated_ids = qwen_model.generate(**inputs, **gen_kwargs)
            
            # Decode output
            input_len = inputs['input_ids'].shape[1]
            generated_ids_trimmed = generated_ids[:, input_len:]
            
            output_text = processor.batch_decode(
                generated_ids_trimmed, 
                skip_special_tokens=True, 
                clean_up_tokenization_spaces=False
            )[0]
            
            captions.append(output_text)
        
        # Join all captions with separator
        full_output = separator.join(captions)
        
        return (full_output,)


class IcyQwen3AllInOne:
    """
    All-in-one node for Qwen3-VL that handles model loading, captioning (single/batch/video), and unloading.
    Includes comprehensive tooltips for all features.
    """
    
    CATEGORY = "IcyQwen3"
    FUNCTION = "process"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output",)
    OUTPUT_NODE = False
    DESCRIPTION = "All-in-one: Load model, caption images/videos, and unload with a single node"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # Model loading parameters
                "model_name": (list(AVAILABLE_MODELS.keys()), {
                    "default": "Qwen3-VL-4B-Instruct-abliterated",
                    "tooltip": "Select the Qwen3-VL model to load. Larger models (8B, 32B) produce better quality but require more VRAM. 'Thinking' variants have enhanced reasoning."
                }),
                "quantization": (QUANTIZATION_OPTIONS, {
                    "default": "4bit",
                    "tooltip": "Quantization method for VRAM reduction. 4bit = lowest VRAM, good quality. 8bit = moderate VRAM, better quality. None/FP8 = full quality, highest VRAM."
                }),
                "device": (DEVICE_OPTIONS, {
                    "default": "auto",
                    "tooltip": "Device to load model on. 'auto' automatically detects and uses GPU if available. 'cuda' forces GPU. 'cpu' forces CPU (slow but works without GPU)."
                }),
                "attention": (ATTENTION_OPTIONS, {
                    "default": "sdpa",
                    "tooltip": "Attention implementation. 'sdpa' (default) works on all platforms. 'flash_attention_2' is fastest but requires Ampere+ GPU on Linux. 'eager' is most compatible but slowest."
                }),
                # Captioning parameters
                "mode": (["single", "batch", "video"], {
                    "default": "single",
                    "tooltip": "Caption mode: 'single' for one image, 'batch' for multiple images, 'video' for video frames"
                }),
                "prompt": ("STRING", {
                    "default": "Describe this image in detail.",
                    "multiline": True,
                    "tooltip": "The captioning prompt/question to ask the model. Be specific for better results."
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                    "tooltip": "Random seed for generation. Change this value to regenerate captions (also controls ComfyUI caching)"
                }),
            },
            "optional": {
                # Model loading optional parameters
                "cpu_offload": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable CPU offloading for large models. Offloads model layers to CPU when not in use. Useful when VRAM is limited but increases processing time."
                }),
                "low_cpu_mem": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Reduce CPU memory usage during model loading. Recommended for systems with limited RAM. May slightly increase load time."
                }),
                "max_pixels": ("INT", {
                    "default": 1003520,  # 1280 * 28 * 28
                    "min": 200704,       # 256 * 28 * 28
                    "max": 12845056,     # 16384 * 28 * 28
                    "step": 784,         # 28 * 28
                    "tooltip": "Maximum pixels for image processing. Higher values preserve more detail but require more VRAM and are slower. Default is good balance."
                }),
                "min_pixels": ("INT", {
                    "default": 200704,   # 256 * 28 * 28
                    "min": 784,          # 1 * 28 * 28
                    "max": 1003520,      # 1280 * 28 * 28
                    "step": 784,
                    "tooltip": "Minimum pixels for image processing. Ensures images are scaled up if too small. Lower values may lose detail but save VRAM."
                }),
                # Single mode inputs
                "image": ("IMAGE", {
                    "tooltip": "Single image input [H, W, C] in 0-1 range. Used in 'single' mode."
                }),
                # Batch mode inputs
                "images": ("IMAGE", {
                    "tooltip": "Batch of images [B, H, W, C] in 0-1 range. Used in 'batch' mode."
                }),
                # Video mode inputs
                "frames": ("IMAGE", {
                    "tooltip": "Video frames [B, H, W, C] in 0-1 range. Used in 'video' mode."
                }),
                "fps": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.1,
                    "max": 30.0,
                    "step": 0.1,
                    "tooltip": "Frames per second for video. Helps model understand temporal dynamics. Used in 'video' mode."
                }),
                "max_frames": ("INT", {
                    "default": 32,
                    "min": 1,
                    "max": 128,
                    "step": 1,
                    "tooltip": "Maximum frames to process from video. If video has more frames, they will be sampled. Used in 'video' mode."
                }),
                # Generation parameters
                "max_tokens": ("INT", {
                    "default": 512,
                    "min": 16,
                    "max": 8192,
                    "step": 16,
                    "tooltip": "Maximum number of tokens to generate. Higher values = longer captions, but slower generation."
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.05,
                    "tooltip": "Sampling temperature. 0.0 = deterministic, 1.0+ = more creative/random. Lower for factual descriptions."
                }),
                "top_p": ("FLOAT", {
                    "default": 0.8,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "Nucleus sampling threshold. Only sample from tokens with cumulative probability >= top_p. Lower = more focused."
                }),
                "top_k": ("INT", {
                    "default": 20,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Top-k sampling. Only sample from the k most likely tokens. Lower = more conservative."
                }),
                "do_sample": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Enable sampling (True) vs greedy decoding (False). Sampling is more creative, greedy is more deterministic."
                }),
                "enable_thinking": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable enhanced reasoning mode. Only works with 'Thinking' model variants. Adds '/think' prefix to prompt."
                }),
                # Batch mode specific
                "separator": ("STRING", {
                    "default": "\n---\n",
                    "tooltip": "String separator between batch captions. Used in 'batch' mode to separate individual image captions."
                }),
                # Unload option
                "unload_after": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Unload the model from memory after captioning to free VRAM. Useful when switching between different workflows."
                }),
            }
        }
    
    @classmethod
    def IS_CHANGED(cls, seed, model_name, quantization, device, attention, **kwargs):
        # Return combination of parameters to control caching
        return (seed, model_name, quantization, device, attention)
    
    def process(
        self,
        model_name: str,
        quantization: str,
        device: str,
        attention: str,
        mode: str,
        prompt: str,
        seed: int = 0,
        cpu_offload: bool = False,
        low_cpu_mem: bool = True,
        max_pixels: int = 1003520,
        min_pixels: int = 200704,
        image: Optional[torch.Tensor] = None,
        images: Optional[torch.Tensor] = None,
        frames: Optional[torch.Tensor] = None,
        fps: float = 1.0,
        max_frames: int = 32,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 20,
        do_sample: bool = True,
        enable_thinking: bool = False,
        separator: str = "\n---\n",
        unload_after: bool = False,
    ):
        # Set seed for reproducibility
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
        
        # Load model
        manager = get_model_manager()
        qwen_model, processor = manager.load_model(
            model_name=model_name,
            quantization=quantization,
            device=device,
            attention=attention,
            cpu_offload=cpu_offload,
            low_cpu_mem=low_cpu_mem,
            max_pixels=max_pixels,
            min_pixels=min_pixels,
        )
        
        # Build messages with thinking mode if enabled
        text_prompt = prompt
        if enable_thinking and "Thinking" in model_name:
            text_prompt = f"/think\n{prompt}"
        
        # Process based on mode
        if mode == "single":
            output = self._caption_single(
                qwen_model, processor, image, text_prompt,
                max_tokens, temperature, top_p, top_k, do_sample
            )
        elif mode == "batch":
            output = self._caption_batch(
                qwen_model, processor, images, text_prompt,
                max_tokens, temperature, top_p, top_k, do_sample, separator
            )
        elif mode == "video":
            output = self._caption_video(
                qwen_model, processor, frames, text_prompt,
                fps, max_frames, max_tokens, temperature, top_p, do_sample
            )
        else:
            output = "Error: Invalid mode selected"
        
        # Unload model if requested
        if unload_after:
            manager.unload()
        
        return (output,)
    
    def _caption_single(
        self,
        qwen_model: Any,
        processor: Any,
        image: torch.Tensor,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        do_sample: bool,
    ) -> str:
        """Caption a single image"""
        if image is None:
            return "Error: No image provided for single mode"
        
        # Convert ComfyUI image tensor to PIL Image
        if len(image.shape) == 4:
            image = image[0]  # Take first image from batch
        
        img_np = (image.cpu().numpy() * 255).astype(np.uint8)
        pil_image = Image.fromarray(img_np, mode='RGB')
        
        # Build messages
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Process and generate
        return self._generate_caption(
            qwen_model, processor, messages, max_tokens,
            temperature, top_p, None, do_sample
        )
    
    def _caption_batch(
        self,
        qwen_model: Any,
        processor: Any,
        images: torch.Tensor,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        do_sample: bool,
        separator: str,
    ) -> str:
        """Caption a batch of images"""
        if images is None:
            return "Error: No images provided for batch mode"
        
        batch_size = images.shape[0]
        captions = []
        
        for i in range(batch_size):
            # Convert single image
            img_np = (images[i].cpu().numpy() * 255).astype(np.uint8)
            pil_image = Image.fromarray(img_np, mode='RGB')
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": pil_image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            
            caption = self._generate_caption(
                qwen_model, processor, messages, max_tokens,
                temperature, top_p, top_k, do_sample
            )
            captions.append(caption)
        
        # Join all captions with separator
        return separator.join(captions)
    
    def _caption_video(
        self,
        qwen_model: Any,
        processor: Any,
        frames: torch.Tensor,
        prompt: str,
        fps: float,
        max_frames: int,
        max_tokens: int,
        temperature: float,
        top_p: float,
        do_sample: bool,
    ) -> str:
        """Caption video frames"""
        if frames is None:
            return "Error: No frames provided for video mode"
        
        # frames is [B, H, W, C] in 0-1 range
        batch_size = frames.shape[0]
        
        # Sample frames if we have more than max_frames
        if batch_size > max_frames:
            indices = np.linspace(0, batch_size - 1, max_frames, dtype=int)
            frames = frames[indices]
            batch_size = max_frames
        
        # Convert frames to list of PIL Images
        frame_list = []
        for i in range(batch_size):
            frame_np = (frames[i].cpu().numpy() * 255).astype(np.uint8)
            pil_frame = Image.fromarray(frame_np, mode='RGB')
            frame_list.append(pil_frame)
        
        # Build video content for Qwen3-VL
        video_content = {
            "type": "video",
            "video": frame_list,
            "fps": fps,
        }
        
        messages = [
            {
                "role": "user",
                "content": [
                    video_content,
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Process and generate
        return self._generate_caption(
            qwen_model, processor, messages, max_tokens,
            temperature, top_p, None, do_sample
        )
    
    def _generate_caption(
        self,
        qwen_model: Any,
        processor: Any,
        messages: list,
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        do_sample: bool,
    ) -> str:
        """Generate caption from processed messages"""
        # Process inputs
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )
        
        # Move all tensors to the model's device
        inputs = {k: v.to(qwen_model.device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample,
            "use_cache": True,
            "pad_token_id": processor.tokenizer.pad_token_id,
        }
        
        if do_sample:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
            if top_k is not None:
                gen_kwargs["top_k"] = top_k
        
        # Generate with optimizations
        with torch.inference_mode(), get_autocast_context():
            generated_ids = qwen_model.generate(**inputs, **gen_kwargs)
        
        # Decode output
        input_len = inputs['input_ids'].shape[1]
        generated_ids_trimmed = generated_ids[:, input_len:]
        
        output_text = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0]
        
        # Ensure it's a proper string
        if output_text is None:
            output_text = ""
        output_text = str(output_text).strip()
        
        return output_text


class IcyQwen3Unload:
    """
    Unload the Qwen3-VL model from memory to free up VRAM.
    """
    
    CATEGORY = "IcyQwen3"
    FUNCTION = "unload"
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    DESCRIPTION = "Unload Qwen3-VL model from memory to free VRAM"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
        }
    
    def unload(self):
        manager = get_model_manager()
        manager.unload()
        return ()
