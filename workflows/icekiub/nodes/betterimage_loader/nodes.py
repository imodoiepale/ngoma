import hashlib
import os

import av
import folder_paths
import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".mpg", ".mpeg", ".ts", ".flv", ".wmv"}


def _resolve_path(folder: str, media: str) -> str:
    """Resolve a widget value to an absolute file path.

    The widget value is a path relative to the chosen folder root
    (e.g. "IMG_1550.jpg" or "pasted/image (305).png"). It may also carry a
    legacy "[subfolder/...]" annotation from older versions, which we strip.
    """
    folder = (folder or "input").lower()
    if folder == "output":
        root = folder_paths.get_output_directory()
    else:
        root = folder_paths.get_input_directory()
    root = os.path.normpath(root)

    rel = (media or "").strip()
    # legacy "name [subfolder/rel]" annotation -> "rel/name"
    if rel.endswith("]") and " [subfolder/" in rel:
        name_part, sub_part = rel[:-1].split(" [subfolder/", 1)
        rel = (sub_part.strip() + "/" + name_part.strip()).strip("/")
    # strip any remaining "[input]"/"[output]"/"[temp]" suffix
    elif rel.endswith("]") and " [" in rel:
        rel = rel[: rel.rfind(" [")].strip()

    rel = rel.replace("\\", "/").strip("/")
    # block path traversal
    if ".." in rel.split("/"):
        rel = os.path.basename(rel)

    candidate = os.path.normpath(os.path.join(root, rel))
    if os.path.commonpath((candidate, root)) != root:
        candidate = os.path.join(root, os.path.basename(rel))
    return candidate


def _media_entries(media: str) -> list[str]:
    return [ln.strip() for ln in (media or "").replace("\r\n", "\n").split("\n") if ln.strip()]


def _video_first_frame(path: str) -> Image.Image:
    with av.open(path) as container:
        frame = next(iter(container.decode(video=0)), None)
    if frame is None:
        raise ValueError(f"Icy MultiRef Loader: no video frames in {path}")
    return frame.to_image()


class IcyImageLoader:
    """Load images from the input OR output folder with a visual grid browser.
    Returns IMAGE and MASK, matching the built-in LoadImage behaviour."""

    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        try:
            files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        except OSError:
            files = []
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {
            "required": {
                "folder": (["input", "output"], {"default": "input"}),
                "image": (sorted(files), {"image_upload": True}),
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("IMAGE", "MASK")
    FUNCTION = "load_image"
    DESCRIPTION = "Load an image from the input or output folder. Use the Gallery button on the node to visually browse both folders in an interactive grid. By icekiub."

    def load_image(self, folder, image):
        image_path = _resolve_path(folder, image)
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"IcyImageLoader: image not found: {image_path}")

        img = Image.open(image_path)
        output_images = []
        output_masks = []
        w = h = None

        for i in ImageSequence.Iterator(img):
            i = ImageOps.exif_transpose(i)
            rgb = i.convert("RGB")

            if w is None:
                w, h = rgb.size
            if rgb.size != (w, h):
                continue

            arr = np.array(rgb).astype(np.float32) / 255.0
            tensor = torch.from_numpy(arr)[None,]

            if "A" in i.getbands():
                mask = np.array(i.getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32)

            output_images.append(tensor)
            output_masks.append(mask.unsqueeze(0))

        out_image = torch.cat(output_images, dim=0)
        out_mask = torch.cat(output_masks, dim=0)
        return (out_image, out_mask)

    @classmethod
    def IS_CHANGED(s, folder, image):
        image_path = _resolve_path(folder, image)
        try:
            m = hashlib.sha256()
            with open(image_path, "rb") as f:
                m.update(f.read())
            return m.digest().hex()
        except OSError:
            return ""

    @classmethod
    def VALIDATE_INPUTS(s, folder, image):
        image_path = _resolve_path(folder, image)
        if not os.path.isfile(image_path):
            return f"Invalid image file: {image}"
        return True


class IcyMultiRefLoader:
    """Load multiple reference media as one IMAGE batch. Each line of the
    widget is a path relative to the chosen folder root; videos contribute
    their first frame. Filled in by the Gallery button or by dropping media
    files onto the node."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "folder": (["input", "output"], {"default": "input"}),
                "media": ("STRING", {"multiline": True, "default": "", "placeholder": "one reference per line"}),
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "MASK") + ("IMAGE",) * 8
    RETURN_NAMES = ("IMAGE", "MASK") + tuple(f"IMAGE_{i}" for i in range(1, 9))
    FUNCTION = "load_refs"
    DESCRIPTION = "Load multiple reference images (videos use their first frame). Drop media files straight onto the node's list or pick several at once with the Gallery button. IMAGE_1..IMAGE_8 hold each reference separately in list order at native size - wire them into separate image inputs such as ICY LM Studio's image/image2..image8. IMAGE/MASK is the full ordered batch, resized to the first image's size. By icekiub."

    def load_refs(self, folder, media):
        entries = _media_entries(media)
        if not entries:
            raise ValueError("Icy MultiRef Loader: no references selected - drop media onto the node or use the Gallery button")

        frames = []
        for rel in entries:
            media_path = _resolve_path(folder, rel)
            if not os.path.isfile(media_path):
                raise FileNotFoundError(f"Icy MultiRef Loader: media not found: {media_path}")

            if os.path.splitext(media_path)[1].lower() in VIDEO_EXTS:
                frame = ImageOps.exif_transpose(_video_first_frame(media_path))
            else:
                with Image.open(media_path) as img:
                    frame = ImageOps.exif_transpose(next(iter(ImageSequence.Iterator(img))))
            rgb = frame.convert("RGB")
            alpha = frame.getchannel("A") if "A" in frame.getbands() else None
            frames.append((rgb, alpha))

        w, h = frames[0][0].size
        batch_images = []
        batch_masks = []
        for rgb, alpha in frames:
            if rgb.size != (w, h):
                rgb = rgb.resize((w, h), Image.Resampling.LANCZOS)
                if alpha is not None:
                    alpha = alpha.resize((w, h))
            batch_images.append(torch.from_numpy(np.array(rgb).astype(np.float32) / 255.0)[None,])
            if alpha is not None:
                mask = 1.0 - torch.from_numpy(np.array(alpha).astype(np.float32) / 255.0)
                batch_masks.append(mask.unsqueeze(0))
            else:
                batch_masks.append(torch.zeros((1, h, w), dtype=torch.float32))

        out = [torch.cat(batch_images, dim=0), torch.cat(batch_masks, dim=0)]
        # individual slots keep each reference at its native size, in list order
        for rgb, _alpha in frames[:8]:
            out.append(torch.from_numpy(np.array(rgb).astype(np.float32) / 255.0)[None,])
        while len(out) < 10:
            out.append(None)
        return tuple(out)

    @classmethod
    def IS_CHANGED(s, folder, media):
        parts = []
        for rel in _media_entries(media):
            try:
                st = os.stat(_resolve_path(folder, rel))
                parts.append(f"{rel}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                parts.append(rel)
        return hashlib.sha256("|".join(parts).encode()).hexdigest()
