import hashlib
import os

import av
from av.audio.resampler import AudioResampler
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


def _selected_video_frames(path: str, force_rate: float, frame_load_cap: int, skip_first_frames: int, select_every_nth: int):
    """Yield (frame, source fps) pairs matching the load widgets, in VHS
    order: force_rate resampling first, then skip_first_frames,
    select_every_nth and frame_load_cap (0 = no limit). Resampling follows
    ffmpeg -r semantics: every output slot takes the nearest source frame,
    so frames are dropped AND duplicated to hold the exact target rate."""
    with av.open(path) as container:
        if not container.streams.video:
            raise ValueError(f"Icy Video Loader: no video stream in {path}")
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        source_fps = float(stream.average_rate) if stream.average_rate else 0.0
        duration = float(container.duration) / av.time_base if container.duration is not None else None

        def resampled(decode):
            if force_rate <= 0:
                yield from decode
                return
            step = 1.0 / force_rate
            next_t = 0.0
            cur = None
            cur_t = 0.0
            for frame in decode:
                t = float(frame.time or 0.0)
                if cur is not None:
                    # emit output slots closer to the held frame than to the next
                    while next_t < cur_t + (t - cur_t) / 2.0 + 1e-9:
                        yield cur
                        next_t += step
                cur, cur_t = frame, t
            if cur is not None:
                limit = duration if duration is not None else cur_t + step
                while next_t < limit:
                    yield cur
                    next_t += step

        resampled_count = 0
        evaluated = 0
        for frame in resampled(container.decode(video=0)):
            resampled_count += 1
            if resampled_count <= skip_first_frames:
                continue
            evaluated += 1
            if evaluated % select_every_nth != 0:
                continue
            yield frame, source_fps
            if frame_load_cap > 0 and evaluated // select_every_nth >= frame_load_cap:
                break


def _load_video_frames(path: str, force_rate: float, frame_load_cap: int, skip_first_frames: int, select_every_nth: int):
    """Decode a video into an IMAGE batch with VHS-style frame controls.
    Returns (tensor BHWC float32, source fps or 0.0)."""
    frames = []
    source_fps = 0.0
    quarterturns = None
    for frame, fps in _selected_video_frames(path, force_rate, frame_load_cap, skip_first_frames, select_every_nth):
        source_fps = fps
        if quarterturns is None:
            # display rotation rides on the frames' side data
            quarterturns = int(frame.rotation or 0) // 90
        arr = frame.to_ndarray(format="rgb24")
        if quarterturns:
            arr = np.ascontiguousarray(np.rot90(arr, quarterturns))
        frames.append(torch.from_numpy(arr.astype(np.float32) / 255.0))

    if not frames:
        raise ValueError(f"Icy Video Loader: no video frames in {path}")
    return torch.stack(frames), source_fps


def _load_audio(path: str, start_sec: float = 0.0, duration_sec: float = 0.0) -> dict:
    """Decode the first audio stream into ComfyUI's AUDIO dict, trimmed to
    [start_sec, start_sec + duration_sec] (duration 0 = to the end)."""
    empty = {"waveform": torch.zeros(1, 2, 0, dtype=torch.float32), "sample_rate": 44100}
    with av.open(path) as container:
        if not container.streams.audio:
            return empty
        resampler = AudioResampler(format="fltp", layout="stereo")
        sample_rate = 44100
        chunks = []
        for frame in container.decode(audio=0):
            t = float(frame.time or 0.0)
            if t < start_sec:
                continue
            if duration_sec > 0 and t >= start_sec + duration_sec:
                break
            sample_rate = frame.sample_rate
            chunks.extend(out.to_ndarray() for out in resampler.resample(frame))
    if not chunks:
        return empty
    # planar chunks are (channels, samples) float32
    waveform = torch.from_numpy(np.concatenate(chunks, axis=1)).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}


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


class IcyVideoLoader:
    """Load a video from the input OR output folder as an IMAGE frame batch
    with audio, VHS-style frame controls, and a visual gallery picker."""

    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        try:
            files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        except OSError:
            files = []
        files = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTS]
        return {
            "required": {
                "folder": (["input", "output"], {"default": "input"}),
                "video": (sorted(files),),
                "force_rate": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 60.0, "step": 0.01}),
                "frame_load_cap": ("INT", {"default": 0, "min": 0, "max": 1000000, "step": 1}),
                "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": 1000000, "step": 1}),
                "select_every_nth": ("INT", {"default": 1, "min": 1, "max": 1000, "step": 1}),
            },
        }

    CATEGORY = "video"
    RETURN_TYPES = ("IMAGE", "INT", "AUDIO")
    RETURN_NAMES = ("IMAGE", "frame_count", "audio")
    FUNCTION = "load_video"
    DESCRIPTION = "Load a video from the input or output folder as a frame batch with audio. Browse and preview videos visually with the Gallery button, or drop a file straight onto the node. frame_count is the number of loaded frames. By icekiub."

    def load_video(self, folder, video, force_rate, frame_load_cap, skip_first_frames, select_every_nth):
        video_path = _resolve_path(folder, video)
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Icy Video Loader: video not found: {video_path}")

        frames, source_fps = _load_video_frames(video_path, force_rate, frame_load_cap, skip_first_frames, select_every_nth)

        # audio window follows VHS: skip offset plus the cap span at the
        # target rate (0 = to the end); select_every_nth doesn't shrink it
        fps = force_rate if force_rate > 0 else source_fps
        if fps > 0:
            audio = _load_audio(video_path, skip_first_frames / fps, frame_load_cap / fps)
        else:
            audio = _load_audio(video_path)
        return (frames, frames.shape[0], audio)

    @classmethod
    def IS_CHANGED(s, folder, video, **kwargs):
        # the engine passes every input; the frame-control widgets are already
        # part of the cache signature, so only the file identity matters here
        try:
            st = os.stat(_resolve_path(folder, video))
            return f"{st.st_mtime_ns}:{st.st_size}"
        except OSError:
            return ""

    @classmethod
    def VALIDATE_INPUTS(s, folder, video):
        video_path = _resolve_path(folder, video)
        if not os.path.isfile(video_path):
            return f"Invalid video file: {video}"
        return True
