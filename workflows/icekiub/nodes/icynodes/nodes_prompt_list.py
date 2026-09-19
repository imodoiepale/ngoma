"""ComfyUI custom node: read .txt files from a folder and output them as a prompt list."""

from __future__ import annotations

import os
import random
from pathlib import Path

try:
    import folder_paths  # provided by ComfyUI at runtime
except Exception:  # allows the module to be imported/tested outside ComfyUI
    folder_paths = None

SORT_MODES = ["name", "name_desc", "modified", "modified_desc", "random"]


def _search_roots() -> list[Path]:
    """Roots that a relative folder_path is resolved against, in order."""
    roots: list[Path] = []
    if folder_paths is not None:
        base = getattr(folder_paths, "base_path", None)
        if base:
            roots.append(Path(base))
        try:
            roots.append(Path(folder_paths.get_input_directory()))
        except Exception:
            pass
    roots.append(Path.cwd())
    return roots


def resolve_folder(folder_path: str) -> Path:
    raw = str(folder_path or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError(
            "folder_path is empty — point it at a folder that contains .txt prompt files."
        )
    raw = os.path.expanduser(raw)
    candidate = Path(raw)

    tried: list[Path] = []
    if candidate.is_absolute():
        tried.append(candidate)
    else:
        for root in _search_roots():
            tried.append(root / candidate)

    for path in tried:
        if path.is_dir():
            return path

    listing = "\n  ".join(str(p) for p in tried)
    raise FileNotFoundError(f"Could not find prompt folder '{raw}'. Tried:\n  {listing}")


def collect_txt_files(folder: Path, recursive: bool) -> list[Path]:
    it = folder.rglob("*") if recursive else folder.iterdir()
    return [p for p in it if p.is_file() and p.suffix.lower() == ".txt"]


def sort_files(files: list[Path], sort: str, seed: int) -> list[Path]:
    files = list(files)
    if sort == "random":
        random.Random(seed).shuffle(files)
        return files
    if sort == "name":
        files.sort(key=lambda p: p.name.lower())
    elif sort == "name_desc":
        files.sort(key=lambda p: p.name.lower(), reverse=True)
    elif sort in ("modified", "modified_desc"):
        files.sort(key=lambda p: (p.stat().st_mtime, p.name.lower()))
        if sort == "modified_desc":
            files.reverse()
    return files


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class PromptListFromFolder:
    """Load every .txt file in a folder as a prompt list."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "E:\\prompts  (or a path relative to ComfyUI)",
                }),
                "sort": (SORT_MODES, {
                    "default": "name",
                    "tooltip": "Order of the prompts: file name or modified date, or a seeded shuffle",
                }),
                "max_prompts": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFF,
                    "tooltip": "Load at most this many prompts (0 = no limit). Applied after sorting/shuffling.",
                }),
                "recursive": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Also read .txt files in subfolders",
                }),
                "skip_empty": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Ignore files that contain only whitespace",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFF,
                    "control_after_generate": True,
                    "tooltip": "Shuffle seed — only used when sort is 'random'",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("prompts", "filenames", "count", "combined")
    OUTPUT_IS_LIST = (True, True, False, False)
    OUTPUT_TOOLTIPS = (
        "One prompt per .txt file (list output — downstream nodes run once per prompt)",
        "File name each prompt was loaded from",
        "Number of prompts loaded",
        "All prompts joined with newlines",
    )
    FUNCTION = "load"
    CATEGORY = "icy"
    DESCRIPTION = (
        "Reads every .txt file in a folder and outputs the contents as a list of prompts. "
        "Connect 'prompts' to a CLIP Text Encode node and the workflow runs once per prompt."
    )

    @classmethod
    def IS_CHANGED(cls, folder_path, sort, recursive, skip_empty, seed, max_prompts):
        try:
            folder = resolve_folder(folder_path)
            files = collect_txt_files(folder, recursive)
            signature = [
                (f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in sorted(files)
            ]
            return repr((sort, recursive, skip_empty, seed, max_prompts, str(folder), signature))
        except Exception:
            return float("NaN")

    def load(self, folder_path, sort, recursive, skip_empty, seed, max_prompts):
        folder = resolve_folder(folder_path)
        files = sort_files(collect_txt_files(folder, recursive), sort, seed)

        prompts: list[str] = []
        filenames: list[str] = []
        for path in files:
            text = read_text(path).strip()
            if skip_empty and not text:
                continue
            prompts.append(text)
            filenames.append(path.name)

        if not prompts:
            detail = (
                " — all of them were empty; disable 'skip_empty' to include them"
                if files and skip_empty
                else ""
            )
            raise ValueError(
                f"No usable .txt files found in '{folder}' "
                f"(checked {len(files)} .txt file(s){detail})"
            )

        if max_prompts > 0:
            prompts = prompts[:max_prompts]
            filenames = filenames[:max_prompts]

        return (prompts, filenames, len(prompts), "\n".join(prompts))
