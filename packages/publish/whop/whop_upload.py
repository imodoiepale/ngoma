#!/usr/bin/env python3
"""Upload a file to Whop and optionally attach it as a course or lesson thumbnail.

Whop's upload is a three-step presigned flow, not a multipart POST:
  1. POST /files {filename, visibility}      -> id, upload_url, upload_headers
  2. PUT the raw bytes to upload_url         -> bypasses api.whop.com entirely
  3. GET /files/{id} until upload_status=ready
Then the id can be referenced as {"id": file_id} wherever an attachment is accepted.

Usage:
    python whop_upload.py image.png
    python whop_upload.py image.png --course cors_xxx      # set course thumbnail
    python whop_upload.py image.png --lesson lesn_xxx      # set lesson thumbnail
    python whop_upload.py image.png --visibility private
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from whop_publish import Whop, WhopError, resolve_credentials

POLL_INTERVAL_S = 2
POLL_TIMEOUT_S = 300


def put_bytes(url: str, headers: dict, payload: bytes) -> int:
    request = urllib.request.Request(url, data=payload, method="PUT")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=600) as response:
        return response.status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--course", help="course id to set this file as the thumbnail of")
    parser.add_argument("--lesson", help="lesson id to set this file as the thumbnail of")
    parser.add_argument("--visibility", choices=("public", "private"), default="public")
    args = parser.parse_args()

    source = Path(args.path)
    if not source.exists():
        print(f"error: {source} not found", file=sys.stderr)
        return 2
    payload = source.read_bytes()

    api_key, _ = resolve_credentials(argparse.Namespace(api_key=None, experience_id="exp_x"))
    client = Whop(api_key)

    print(f"file    : {source.name} ({len(payload)/1024:.0f} KB, "
          f"{mimetypes.guess_type(source.name)[0] or 'unknown type'})")

    # 1. create the record
    try:
        created = client.request(
            "POST", "/files",
            body={"filename": source.name, "visibility": args.visibility},
        )
    except WhopError as exc:
        print(f"create failed: {exc}", file=sys.stderr)
        return 1
    record = created.get("data") or created
    file_id = record.get("id")
    upload_url = record.get("upload_url")
    upload_headers = record.get("upload_headers") or {}
    if not (file_id and upload_url):
        print(f"unexpected create response: {json.dumps(record)[:400]}", file=sys.stderr)
        return 1
    print(f"created : {file_id} (status={record.get('upload_status')})")

    # 2. PUT the raw bytes straight to storage
    try:
        status = put_bytes(upload_url, upload_headers, payload)
        print(f"uploaded: HTTP {status}")
    except urllib.error.HTTPError as exc:
        print(f"byte upload failed: HTTP {exc.code} "
              f"{exc.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
        return 1

    # 3. poll until processed
    deadline = time.time() + POLL_TIMEOUT_S
    state = None
    while time.time() < deadline:
        current = client.request("GET", f"/files/{file_id}")
        record = current.get("data") or current
        state = record.get("upload_status")
        if state == "ready":
            print(f"ready   : {record.get('url', '(no url returned)')[:110]}")
            break
        if state in ("failed", "error"):
            print(f"processing failed: {json.dumps(record)[:300]}", file=sys.stderr)
            return 1
        time.sleep(POLL_INTERVAL_S)
    else:
        print(f"timed out waiting for ready (last status={state})", file=sys.stderr)
        return 1

    # 4. attach
    target, path = (
        ("course", f"/courses/{args.course}") if args.course
        else ("lesson", f"/course_lessons/{args.lesson}") if args.lesson
        else (None, None)
    )
    if path:
        try:
            client.request("PATCH", path, body={"thumbnail": {"id": file_id}})
            print(f"attached: thumbnail set on {target} {args.course or args.lesson}")
        except WhopError as exc:
            print(f"attach failed: {exc}", file=sys.stderr)
            return 1

    print(f"\nfile id: {file_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
