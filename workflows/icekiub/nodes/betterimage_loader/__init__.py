import asyncio
import hashlib
import os
import tempfile
import time

import av
from aiohttp import web
from PIL import Image
from server import PromptServer

from .nodes import VIDEO_EXTS, IcyImageLoader, IcyMultiRefLoader

WEB_DIRECTORY = "./web/js"

NODE_CLASS_MAPPINGS = {
    "IcyImageLoader": IcyImageLoader,
    "IcyMultiRefLoader": IcyMultiRefLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IcyImageLoader": "❄️ Icy Image Loader (icekiub)",
    "IcyMultiRefLoader": "❄️ Icy MultiRef Loader (icekiub)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def _scan(folder_root: str, base_dir: str, rel_base: str, exts):
    """Recursively collect media files under base_dir, returning dicts with
    display + load info. rel_base is the path relative to folder_root used as
    the `subfolder` query for the /view endpoint (always within the root)."""
    results = []
    if not os.path.isdir(base_dir):
        return results
    try:
        entries = sorted(os.listdir(base_dir))
    except OSError:
        return results
    for name in entries:
        full = os.path.join(base_dir, name)
        if os.path.isdir(full):
            results.extend(_scan(folder_root, full, os.path.join(rel_base, name) if rel_base else name, exts))
            continue
        if os.path.splitext(name)[1].lower() not in exts:
            continue
        try:
            stat = os.stat(full)
        except OSError:
            continue
        rel_path = f"{rel_base}/{name}" if rel_base else name
        results.append(
            {
                "name": name,
                "path": rel_path,
                "subfolder": rel_base,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        )
    return results


def _list_for_folder(folder: str, media: bool = False):
    import folder_paths

    folder = (folder or "input").lower()
    if folder == "output":
        root = folder_paths.get_output_directory()
    else:
        root = folder_paths.get_input_directory()
    items = _scan(root, root, "", MEDIA_EXTS if media else IMAGE_EXTS)
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


@PromptServer.instance.routes.get("/icy_loader/list")
async def icy_list(request):
    """Return media listings for input and output folders.
    Query: ?folder=input|output (defaults to both), ?media=1 to include videos."""
    from folder_paths import get_input_directory, get_output_directory

    folder = request.rel_url.query.get("folder")
    media = request.rel_url.query.get("media") in ("1", "true")
    if folder in ("input", "output"):
        data = {folder: _list_for_folder(folder, media)}
    else:
        data = {"input": _list_for_folder("input", media), "output": _list_for_folder("output", media)}
    data["_generated"] = time.time()
    data["_input_dir"] = os.path.basename(get_input_directory())
    data["_output_dir"] = os.path.basename(get_output_directory())
    return web.json_response(data)


# ----------------------- cached thumbnails -----------------------

THUMB_DIR = os.path.join(tempfile.gettempdir(), "icy_loader_thumbs")
THUMB_SIZE = (300, 300)
THUMB_LOCKS: dict = {}

os.makedirs(THUMB_DIR, exist_ok=True)


def _resolve_source(folder, filename, subfolder):
    import folder_paths

    folder = (folder or "input").lower()
    if folder == "output":
        root = folder_paths.get_output_directory()
    else:
        root = folder_paths.get_input_directory()
    # security: keep within root
    name = os.path.basename(filename or "")
    if not name or name.startswith("/") or ".." in name:
        return None
    sub = subfolder or ""
    if ".." in sub:
        return None
    candidate = os.path.normpath(os.path.join(root, sub, name))
    if os.path.commonpath((candidate, root)) != os.path.normpath(root):
        return None
    return candidate


def _make_thumbnail_sync(path, dest):
    if os.path.splitext(path)[1].lower() in VIDEO_EXTS:
        with av.open(path) as container:
            frame = next(iter(container.decode(video=0)), None)
        if frame is None:
            raise ValueError("no video frames")
        img = frame.to_image().convert("RGB")
    else:
        with Image.open(path) as src:
            img = src.convert("RGB")
    img.thumbnail(THUMB_SIZE)
    img.save(dest, format="WEBP", quality=78)


@PromptServer.instance.routes.get("/icy_loader/thumb")
async def icy_thumb(request):
    """Fast, disk-cached thumbnail. ?type=input|output&filename=&subfolder="""
    folder = request.rel_url.query.get("type") or request.rel_url.query.get("folder") or "input"
    filename = request.rel_url.query.get("filename")
    subfolder = request.rel_url.query.get("subfolder", "")
    src = _resolve_source(folder, filename, subfolder)
    if not src or not os.path.isfile(src):
        return web.Response(status=404)

    try:
        mtime = int(os.path.getmtime(src))
    except OSError:
        return web.Response(status=404)

    key = hashlib.md5(f"{folder}|{src}|{mtime}".encode()).hexdigest()
    dest = os.path.join(THUMB_DIR, key + ".webp")

    if not os.path.isfile(dest):
        lock = THUMB_LOCKS.setdefault(key, asyncio.Lock())
        async with lock:
            if not os.path.isfile(dest):
                try:
                    await asyncio.to_thread(_make_thumbnail_sync, src, dest)
                except Exception:
                    THUMB_LOCKS.pop(key, None)
                    return web.Response(status=500)
        THUMB_LOCKS.pop(key, None)

    try:
        with open(dest, "rb") as f:
            data = f.read()
    except OSError:
        return web.Response(status=500)

    return web.Response(
        body=data,
        content_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "Content-Disposition": f'filename="{os.path.basename(filename)}"',
        },
    )


print("Icy Loader by icekiub: extension loaded")
