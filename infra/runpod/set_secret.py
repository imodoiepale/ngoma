#!/usr/bin/env python3
"""Store a secret as a Windows DPAPI blob, readable only by the current Windows user.

Use this after rotating a credential so the scripts keep working without the secret
ever being written to disk in plaintext or pasted into a file that could be committed.

The blob format matches what the existing scripts read: hex-encoded DPAPI ciphertext.
Plaintext is written as UTF-16LE to match the PowerShell-produced blobs already in
work/, and read_dpapi() in runpod_api.py detects either encoding.

Usage:
    python set_secret.py hf          # prompts, echo off
    python set_secret.py runpod
    python set_secret.py whop --path ../course/whop-token.dpapi
"""

from __future__ import annotations

import argparse
import ctypes
import getpass
import sys
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent

TARGETS = {
    "hf": WORKSPACE / "work" / "hf-token.dpapi",
    "runpod": WORKSPACE / "work" / "runpod-token.dpapi",
    "whop": HERE.parent / "course" / "whop-token.dpapi",
}


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def protect(plaintext: str) -> bytes:
    raw = plaintext.encode("utf-16-le")
    blob_in = Blob(
        len(raw),
        ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_char)),
    )
    blob_out = Blob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=sorted(TARGETS))
    parser.add_argument("--path", help="override the output path")
    parser.add_argument("--value", help="secret value (omit to be prompted, which is safer)")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("error: DPAPI is Windows-only", file=sys.stderr)
        return 2

    secret = args.value or getpass.getpass(f"{args.name} secret (input hidden): ")
    secret = secret.strip()
    if not secret:
        print("error: empty secret", file=sys.stderr)
        return 2

    path = Path(args.path) if args.path else TARGETS[args.name]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(protect(secret).hex(), encoding="utf-8")
    print(f"wrote {path}  ({len(secret)} chars encrypted, prefix {secret[:3]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
