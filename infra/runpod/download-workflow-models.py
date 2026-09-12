import os
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(os.environ.get("EPALLE_ROOT", "/workspace/epalle"))
MODELS = ROOT / "models"

FILES = [
    ("black-forest-labs/FLUX.2-klein-9b-kv", "flux-2-klein-9b-kv.safetensors", "diffusion_models", None),
    ("black-forest-labs/FLUX.2-klein-9b-fp8", "flux-2-klein-9b-fp8.safetensors", "diffusion_models", None),
    ("Comfy-Org/flux2-klein-9B", "split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors", "text_encoders", None),
    ("Comfy-Org/flux2-klein-9B", "split_files/vae/flux2-vae.safetensors", "vae", None),
    ("Kijai/WanVideo_comfy_fp8_scaled", "SCAIL/Wan21-14B-SCAIL-preview_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
    ("Kijai/WanVideo_comfy", "umt5-xxl-enc-fp8_e4m3fn.safetensors", "text_encoders", None),
    ("Wan-AI/Wan2.2-Animate-14B", "process_checkpoint/det/yolov10m.onnx", "detection", None),
    ("Kijai/vitpose_comfy", "onnx/vitpose-h-wholebody.onnx", "detection", None),
]


def install(repo, filename, folder, output_name):
    destination = MODELS / folder / (output_name or Path(filename).name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size:
        print(f"present {destination}")
        return
    downloaded = Path(hf_hub_download(repo_id=repo, filename=filename, token=os.environ.get("HF_TOKEN")))
    temporary = destination.with_suffix(destination.suffix + ".partial")
    shutil.copyfile(downloaded, temporary)
    temporary.replace(destination)
    print(f"installed {repo}/{filename} -> {destination}")


def main():
    failures = []
    for entry in FILES:
        try:
            install(*entry)
        except Exception as exc:
            failures.append((entry[0], entry[1], str(exc)))
    if failures:
        print("\nModels requiring attention:")
        for repo, filename, error in failures:
            print(f"- https://huggingface.co/{repo} :: {filename} :: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
