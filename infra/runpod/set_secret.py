#!/usr/bin/env python3
"""Store a studio secret, encrypted for the current Windows user (DPAPI).

Every adapter reads secrets through packages/common/vault.py: the environment variable
first, then the blob this script writes. Blobs go to %APPDATA%/epalle-studio/secrets/,
outside the repository, so a stored key can never be committed.

Usage:
    uv run infra/runpod/set_secret.py openrouter     # prompts, input hidden
    uv run infra/runpod/set_secret.py ig-token
    uv run infra/runpod/set_secret.py --list         # which secrets are set, and from where
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "common"))
import vault  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", nargs="?", choices=sorted(vault.KNOWN))
    parser.add_argument("--list", action="store_true", help="show where each secret comes from")
    parser.add_argument("--path", help="override the output path (must be outside the repo)")
    parser.add_argument("--value", help="secret value (omit to be prompted, which is safer)")
    args = parser.parse_args()

    if args.list:
        for name, env in sorted(vault.KNOWN.items()):
            print(f"{name:<11} {env:<20} {vault.source(env)}")
        return 0
    if not args.name:
        parser.error("name a secret to store, or pass --list")
    if sys.platform != "win32":
        print(f"error: DPAPI is Windows-only; set {vault.KNOWN[args.name]} instead", file=sys.stderr)
        return 2

    env = vault.KNOWN[args.name]
    secret = args.value or getpass.getpass(f"{env} (input hidden): ")
    try:
        dest = vault.put(env, secret, Path(args.path) if args.path else None)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    # Never echo any part of the value, not even a prefix.
    print(f"stored {env} -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
