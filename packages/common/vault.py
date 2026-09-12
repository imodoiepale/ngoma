"""One place to read and store the studio's secrets.

Before this existed, secrets were half-wired. `set_secret.py` could encrypt only three
keys, wrote the Whop key to a folder nothing read, and every adapter added later
(OpenRouter, Postiz, Instagram, OpenWA, Hermes, Paperclip, TTS) read plain environment
variables only. So "store the key with set_secret.py" produced a file no code ever
opened. Three separate copies of the DPAPI decrypt routine had also appeared.

This module is the single implementation. Every adapter asks `get(ENV_NAME)`, which
returns the first of:

  1. the environment variable, so CI and one-off shells keep working
  2. the encrypted store: one Windows DPAPI blob per secret, OUTSIDE the repo, in
     %APPDATA%/epalle-studio/secrets/ (override with EPALLE_SECRETS_DIR)
  3. the legacy blob locations older scripts wrote, so nothing already stored is lost

It returns None when a secret is absent. It never raises for a missing secret and never
logs, prints or returns part of a value: callers decide what "missing" means, and error
messages name the secret, not its contents.

Named `vault` rather than `secrets` on purpose: a `secrets.py` on sys.path would shadow
Python's standard-library `secrets` module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# short name used on the command line -> environment variable the code reads
KNOWN: dict[str, str] = {
    "runpod": "RUNPOD_API_KEY",
    "hf": "HF_TOKEN",
    "whop": "WHOP_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "postiz": "POSTIZ_API_KEY",
    "ig-token": "IG_ACCESS_TOKEN",
    "ig-user": "IG_USER_ID",
    "openwa": "OPENWA_API_KEY",
    "hermes": "HERMES_API_KEY",
    "paperclip": "PAPERCLIP_API_KEY",
    "openai": "OPENAI_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
}
ENV_TO_NAME = {v: k for k, v in KNOWN.items()}

# Where the pre-vault scripts wrote blobs. Read, never written.
LEGACY: dict[str, list[Path]] = {
    "RUNPOD_API_KEY": [REPO / "work" / "runpod-token.dpapi",
                       REPO / "infra" / "runpod" / "runpod-token.dpapi"],
    "HF_TOKEN": [REPO / "work" / "hf-token.dpapi"],
    "WHOP_API_KEY": [REPO / "packages" / "publish" / "whop" / "whop-token.dpapi",
                     REPO / "infra" / "course" / "whop-token.dpapi"],
}


def store_dir() -> Path:
    override = os.environ.get("EPALLE_SECRETS_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "epalle-studio" / "secrets"


def blob_path(env_name: str) -> Path:
    name = ENV_TO_NAME.get(env_name, env_name.lower())
    return store_dir() / f"{name}.dpapi"


# ------------------------------------------------------------------ DPAPI

def _dpapi_available() -> bool:
    return sys.platform == "win32"


if _dpapi_available():
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def protect(plaintext: str) -> bytes:
    """Encrypt for the current Windows user. UTF-16LE, matching the older PowerShell blobs."""
    if not _dpapi_available():
        raise OSError("DPAPI is Windows-only; set the environment variable instead")
    raw = plaintext.encode("utf-16-le")
    blob_in = _Blob(len(raw), ctypes.cast(ctypes.create_string_buffer(raw),
                                          ctypes.POINTER(ctypes.c_char)))
    blob_out = _Blob()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def unprotect(ciphertext: bytes) -> str | None:
    """Decrypt a DPAPI blob. None if it cannot be decrypted by this user on this machine."""
    if not _dpapi_available() or not ciphertext:
        return None
    blob_in = _Blob(len(ciphertext), ctypes.cast(ctypes.create_string_buffer(ciphertext),
                                                 ctypes.POINTER(ctypes.c_char)))
    blob_out = _Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        return None
    try:
        raw = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    # Older blobs are UTF-16LE (PowerShell), some are UTF-8. Detect rather than guess.
    if len(raw) >= 2 and raw[1:2] == b"\x00":
        text = raw.decode("utf-16-le", errors="ignore")
    else:
        text = raw.decode("utf-8", errors="ignore")
    return text.strip().strip("\x00") or None


def read_blob(path: Path) -> str | None:
    """A blob file holds hex-encoded ciphertext. Missing or unreadable -> None."""
    try:
        data = path.read_text(encoding="utf-8").strip()
        return unprotect(bytes.fromhex(data)) if data else None
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ public API

def get(env_name: str) -> str | None:
    """The secret's value, or None. Environment first, then the store, then legacy blobs."""
    value = os.environ.get(env_name)
    if value:
        return value
    value = read_blob(blob_path(env_name))
    if value:
        return value
    for legacy in LEGACY.get(env_name, []):
        value = read_blob(legacy)
        if value:
            return value
    return None


def source(env_name: str) -> str:
    """Where a secret would come from — for diagnostics. Never includes the value."""
    if os.environ.get(env_name):
        return "environment"
    if read_blob(blob_path(env_name)):
        return f"encrypted store ({blob_path(env_name)})"
    for legacy in LEGACY.get(env_name, []):
        if read_blob(legacy):
            return f"legacy blob ({legacy})"
    return "not set"


def put(env_name: str, value: str, path: Path | None = None) -> Path:
    """Encrypt and store. The destination is outside the repository by default."""
    value = value.strip()
    if not value:
        raise ValueError("refusing to store an empty secret")
    dest = path or blob_path(env_name)
    try:
        dest.resolve().relative_to(REPO.resolve())
        inside_repo = True
    except ValueError:
        inside_repo = False
    if inside_repo:
        raise ValueError(f"refusing to write a secret inside the repository: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(protect(value).hex(), encoding="utf-8")
    return dest


def missing_hint(env_name: str) -> str:
    """The sentence an adapter should print when a secret it needs is absent."""
    name = ENV_TO_NAME.get(env_name)
    how = (f"uv run infra/runpod/set_secret.py {name}" if name
           else f"set the {env_name} environment variable")
    return f"{env_name} is not set. Store it with: {how}"
