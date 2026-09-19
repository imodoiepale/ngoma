import asyncio
import hashlib
import os
import tempfile
import time

import av
from av.audio.resampler import AudioResampler
from aiohttp import web
from PIL import Image
from server import PromptServer

from .nodes_image_loader import VIDEO_EXTS, _selected_video_frames  # noqa: F401 (routes use these)

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


def _list_for_folder(folder: str, media=False):
    import folder_paths

    folder = (folder or "input").lower()
    if folder == "output":
        root = folder_paths.get_output_directory()
    else:
        root = folder_paths.get_input_directory()
    exts = VIDEO_EXTS if media == "video" else (MEDIA_EXTS if media else IMAGE_EXTS)
    items = _scan(root, root, "", exts)
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


@PromptServer.instance.routes.get("/icy_loader/list")
async def icy_list(request):
    """Return media listings for input and output folders.
    Query: ?folder=input|output (defaults to both), ?media=1 to include videos,
    ?media=video for videos only."""
    from folder_paths import get_input_directory, get_output_directory

    folder = request.rel_url.query.get("folder")
    raw = request.rel_url.query.get("media", "")
    media = "video" if raw == "video" else raw in ("1", "true")
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


@PromptServer.instance.routes.get("/icy_loader/vinfo")
async def icy_vinfo(request):
    """Source video stats via PyAV. ?type=input|output&filename=&subfolder="""
    folder = request.rel_url.query.get("type") or request.rel_url.query.get("folder") or "input"
    filename = request.rel_url.query.get("filename")
    subfolder = request.rel_url.query.get("subfolder", "")
    src = _resolve_source(folder, filename, subfolder)
    if not src or not os.path.isfile(src):
        return web.Response(status=404)

    def probe(path):
        with av.open(path) as container:
            streams = container.streams.video
            if not streams:
                raise ValueError("no video stream")
            stream = streams[0]
            fps = float(stream.average_rate) if stream.average_rate else 0.0
            duration = float(container.duration) / av.time_base if container.duration is not None else 0.0
            frames = int(stream.frames or 0)
            if not frames and fps and duration:
                frames = int(duration * fps)
            return {
                "width": stream.codec_context.width or 0,
                "height": stream.codec_context.height or 0,
                "fps": round(fps, 3),
                "duration": round(duration, 2),
                "frames": frames,
                "size": os.path.getsize(path),
            }

    try:
        info = await asyncio.to_thread(probe, src)
    except Exception:
        return web.Response(status=500)
    return web.json_response(info)


# ----------------------- streaming preview transcode -----------------------

PREVIEW_MAX_WIDTH = 512
PREVIEW_DIR = os.path.join(tempfile.gettempdir(), "icy_loader_previews")
PREVIEW_LOCKS: dict = {}

os.makedirs(PREVIEW_DIR, exist_ok=True)


class _PreviewSink:
    """File-like sink the muxer writes into; queues chunks for streaming and
    mirrors them to a cache file. write() runs on the transcode thread."""

    def __init__(self, tmp_path, dest):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.broken = False
        self.tmp_path = tmp_path
        self.dest = dest
        self._fh = open(tmp_path, "wb")

    def write(self, data):
        if self.broken:
            raise OSError("preview client gone")
        self._fh.write(data)
        self.queue.put_nowait(bytes(data))
        return len(data)

    def finish(self, commit):
        self._fh.close()
        self._fh = None
        try:
            if commit:
                os.replace(self.tmp_path, self.dest)
            else:
                os.unlink(self.tmp_path)
        except OSError:
            pass


def _encode_preview_audio(src, out, start_sec, end_sec):
    """Encode the [start_sec, end_sec) audio window to AAC for the preview.
    Returns the encoded packets (empty when the file has no audio)."""
    with av.open(src) as inp:
        if not inp.streams.audio:
            return []
        resampler = AudioResampler(format="fltp", layout="stereo", rate=44100)
        astream = out.add_stream("aac", rate=44100)
        astream.layout = "stereo"
        astream.bit_rate = 128_000
        packets = []
        expected = 0
        for frame in inp.decode(audio=0):
            t = float(frame.time or 0.0)
            if t < start_sec - 1e-3:
                continue
            if end_sec is not None and t >= end_sec:
                break
            for f in resampler.resample(frame):
                f.pts = expected
                expected += f.samples
                packets.extend(astream.encode(f))
        packets.extend(astream.encode())
        return packets


def _transcode_preview_sync(src, sink, force_rate, cap, skip, nth):
    from fractions import Fraction

    with av.open(src) as inp:
        if not inp.streams.video:
            raise ValueError("no video stream")
        vstream = inp.streams.video[0]
        source_fps = float(vstream.average_rate) if vstream.average_rate else 0.0
        duration = float(inp.duration) / av.time_base if inp.duration is not None else 0.0

    # audio window matches the node's AUDIO output: skip offset + cap span
    eff = force_rate if force_rate > 0 else source_fps
    start_sec = skip / eff if eff > 0 else 0.0
    end_sec = start_sec + cap / eff if (cap > 0 and eff > 0) else (duration or None)

    with av.open(sink, "w", format="mp4", options={"movflags": "+frag_keyframe+empty_moov"}) as out:
        apackets = _encode_preview_audio(src, out, start_sec, end_sec)
        # mux interleaved: audio packets up to the current video timestamp,
        # otherwise the mp4 interleaver receives a wholly out-of-order track
        ai = 0

        def flush_audio(upto_sec):
            nonlocal ai
            while ai < len(apackets):
                p = apackets[ai]
                t = float(p.pts * p.time_base) if p.pts is not None else 0.0
                if t > upto_sec:
                    break
                out.mux(p)
                ai += 1

        ostream = None
        rate = 0
        index = 0
        for frame, src_fps in _selected_video_frames(src, force_rate, cap, skip, nth):
            scale = min(1.0, PREVIEW_MAX_WIDTH / frame.width)
            width = max(2, int(frame.width * scale) // 2 * 2)
            height = max(2, int(frame.height * scale) // 2 * 2)
            if ostream is None:
                rate = (Fraction(force_rate).limit_denominator(1001) if force_rate > 0
                        else Fraction(int(round(src_fps or 25))))
                # every nth slot is kept, so pace the stream at rate/nth to hold
                # each frame for its full stride: same duration, choppier motion
                rate /= nth
                ostream = out.add_stream("libx264", rate=rate)
                ostream.width = width
                ostream.height = height
                ostream.pix_fmt = "yuv420p"
                ostream.bit_rate = 1_500_000
                ostream.gop_size = max(1, round(float(rate))) * 2
                ostream.options = {"preset": "veryfast"}
            f = frame.reformat(width=width, height=height, format="yuv420p")
            # reformat keeps the input time base: restamp so playback runs at rate
            f.time_base = Fraction(1, 1) / rate
            f.pts = index
            index += 1
            for packet in ostream.encode(f):
                out.mux(packet)
            flush_audio(f.pts / float(rate))
        if ostream is not None:
            for packet in ostream.encode():
                out.mux(packet)
        flush_audio(float("inf"))


@PromptServer.instance.routes.get("/icy_loader/preview")
async def icy_preview(request):
    """Stream a re-encode of exactly the frames the load widgets will fetch,
    so force_rate / frame_load_cap / skip_first_frames / select_every_nth all
    show in the on-node preview. Query matches /icy_loader/thumb plus
    force_rate, cap, skip, nth. Results are cached to disk and the URL is
    fully parameterised, so nothing is re-encoded when nothing changed."""
    q = request.rel_url.query
    src = _resolve_source(q.get("type") or "input", q.get("filename"), q.get("subfolder", ""))
    if not src or not os.path.isfile(src):
        return web.Response(status=404)
    try:
        force_rate = float(q.get("force_rate", 0) or 0)
        cap = int(float(q.get("cap", 0) or 0))
        skip = int(float(q.get("skip", 0) or 0))
        nth = max(1, int(float(q.get("nth", 1) or 1)))
    except ValueError:
        return web.Response(status=400)

    try:
        mtime = int(os.path.getmtime(src))
    except OSError:
        return web.Response(status=404)
    key = hashlib.md5(f"{src}|{mtime}|{force_rate}|{cap}|{skip}|{nth}".encode()).hexdigest()
    dest = os.path.join(PREVIEW_DIR, key + ".mp4")
    headers = {
        "Content-Type": "video/mp4",
        "Cache-Control": "public, max-age=86400, immutable",
    }
    if os.path.isfile(dest):
        return web.FileResponse(dest, headers=headers)

    # the temp dir can be wiped by OS/cleaner cleanup while the server runs
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    sink = _PreviewSink(dest + f".{os.getpid()}.{time.monotonic_ns()}.tmp", dest)

    def transcode():
        ok = False
        try:
            _transcode_preview_sync(src, sink, force_rate, cap, skip, nth)
            ok = True
        except Exception:
            pass
        finally:
            sink.finish(ok)
            sink.queue.put_nowait(None)

    lock = PREVIEW_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        if os.path.isfile(dest):
            PREVIEW_LOCKS.pop(key, None)
            return web.FileResponse(dest, headers=headers)
        task = asyncio.create_task(asyncio.to_thread(transcode))
        resp = web.StreamResponse(headers=headers)
        await resp.prepare(request)
        try:
            while True:
                chunk = await sink.queue.get()
                if chunk is None:
                    break
                await resp.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            sink.broken = True
        try:
            await task
        except Exception:
            pass
    PREVIEW_LOCKS.pop(key, None)
    return resp


print("Icy Loader by icekiub: extension loaded")
