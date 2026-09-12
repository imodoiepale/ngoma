#!/usr/bin/env python3
"""Publish whop-course.json to Whop via the Courses API.

Contract is documented in API-CONTRACT.md and was verified against the official docs.
There is no upsert endpoint, so this script achieves idempotency by listing existing
courses / chapters / lessons and matching on title before creating anything. Re-running
it does not duplicate the tree.

Credentials, in precedence order:
  1. --api-key / --experience-id flags
  2. WHOP_API_KEY / WHOP_EXPERIENCE_ID environment variables
  3. .env.whop in this directory (gitignored), KEY=VALUE lines
  4. whop-token.dpapi in this directory (Windows DPAPI, current user)

Usage:
    python whop_publish.py --dry-run        # print the exact request plan, no network
    python whop_publish.py --check-auth     # verify the key and show the account
    python whop_publish.py                  # publish (course stays hidden)
    python whop_publish.py --make-visible   # flip visibility to visible
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
COURSE_PATH = HERE / "whop-course.json"
ENV_PATH = HERE / ".env.whop"

API_BASE = "https://api.whop.com/api/v1"
API_VERSION_DATE = "2026-07-01"
PAGE_SIZE = 100
MAX_RETRIES = 4


# --------------------------------------------------------------------------- creds


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


def _read_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def resolve_credentials(args) -> tuple[str, str]:
    env_file = _read_env_file()

    api_key = (
        args.api_key
        or _secret("WHOP_API_KEY")
        or env_file.get("WHOP_API_KEY")
        or _secret("WHOP_API_KEY")
    )
    experience_id = (
        args.experience_id
        or os.environ.get("WHOP_EXPERIENCE_ID")
        or env_file.get("WHOP_EXPERIENCE_ID")
    )

    problems = []
    if not api_key:
        problems.append(
            "No Whop API key. Create an Account API Key in the Whop dashboard with the\n"
            "  'courses:update' permission, then write it to this file:\n"
            f"    {ENV_PATH}\n"
            "  as:\n"
            "    WHOP_API_KEY=apik_...\n"
            "    WHOP_EXPERIENCE_ID=exp_...\n"
            "  (.env.whop is gitignored. Do not paste the key into a chat or a commit.)"
        )
    if not experience_id:
        problems.append(
            "No Whop experience ID. A course is created inside an existing experience.\n"
            "  Run with --check-auth to list the experiences this key can see."
        )
    elif not experience_id.startswith("exp_"):
        problems.append(
            f"Experience ID {experience_id!r} does not look like a Whop experience ID "
            "(expected an 'exp_' prefix)."
        )

    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        raise SystemExit(2)

    return api_key, experience_id


# ----------------------------------------------------------------------- transport


class WhopError(RuntimeError):
    def __init__(self, status: int, body: str, method: str, path: str):
        super().__init__(f"{method} {path} -> HTTP {status}: {body[:600]}")
        self.status = status
        self.body = body


class Whop:
    def __init__(self, api_key: str, verbose: bool = False):
        self._api_key = api_key
        self.verbose = verbose
        self.calls = 0

    def request(self, method: str, path: str, *, params=None, body=None):
        url = f"{API_BASE}{path}"
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean)}"

        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")

        for attempt in range(MAX_RETRIES):
            req = urllib.request.Request(url, data=payload, method=method)
            req.add_header("Authorization", f"Bearer {self._api_key}")
            req.add_header("Api-Version-Date", API_VERSION_DATE)
            req.add_header("Accept", "application/json")
            if payload is not None:
                req.add_header("Content-Type", "application/json")

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self.calls += 1
                    text = resp.read().decode("utf-8")
                    if self.verbose:
                        print(f"  {method} {path} -> {resp.status}")
                    return json.loads(text) if text.strip() else {}
            except urllib.error.HTTPError as exc:
                text = exc.read().decode("utf-8", "replace")
                # Retry on rate limit and transient server errors only.
                if exc.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    if retry_after and retry_after.isdigit():
                        delay = max(delay, int(retry_after))
                    print(
                        f"  {method} {path} -> HTTP {exc.code}, retrying in {delay}s",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue
                raise WhopError(exc.code, text, method, path) from exc
            except urllib.error.URLError as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc

        raise RuntimeError("unreachable")

    def paginate(self, path: str, params: dict) -> list[dict]:
        """Walk a cursor-paginated list endpoint and return every item."""
        items: list[dict] = []
        cursor = None
        while True:
            page = self.request(
                "GET", path, params={**params, "first": PAGE_SIZE, "after": cursor}
            )
            items.extend(page.get("data") or [])
            info = page.get("page_info") or {}
            if not info.get("has_next_page"):
                return items
            cursor = info.get("end_cursor")
            if not cursor:
                return items


# ------------------------------------------------------------------------- publish


def find_by_title(items: list[dict], title: str) -> dict | None:
    target = title.strip().casefold()
    for item in items:
        if (item.get("title") or "").strip().casefold() == target:
            return item
    return None


def lesson_payload(chapter_id: str, lesson: dict) -> dict:
    payload = {
        "chapter_id": chapter_id,
        "lesson_type": lesson["lesson_type"],
        "title": lesson["title"],
        "content": lesson["content"],
    }
    if lesson.get("embed_type") and lesson.get("embed_id"):
        payload["embed_type"] = lesson["embed_type"]
        payload["embed_id"] = lesson["embed_id"]
    return payload


def publish(client: Whop, course: dict, experience_id: str, make_visible: bool) -> dict:
    created = {"course": 0, "chapters": 0, "lessons": 0}
    skipped = {"chapters": 0, "lessons": 0}

    existing = client.paginate("/courses", {"experience_id": experience_id})
    course_obj = find_by_title(existing, course["title"])

    if course_obj:
        course_id = course_obj["id"]
        print(f"course already exists: {course_id} ({course['title']!r})")
    else:
        # `description` is documented as a nullable string, but the live API rejects a
        # plain string of any length with "Invalid value for parameter 'description'"
        # (tested at 60/120/200/307 chars; omitting it succeeds). It presumably expects
        # a rich-text structure the docs do not describe. Left out rather than guessed
        # at -- the tagline carries the summary, and the description can be set in the
        # dashboard.
        body = {
            "experience_id": experience_id,
            "title": course["title"],
            "tagline": course.get("tagline"),
            "visibility": "visible" if make_visible else "hidden",
            "require_completing_lessons_in_order": course.get(
                "require_completing_lessons_in_order"
            ),
            "certificate_after_completion_enabled": course.get(
                "certificate_after_completion_enabled"
            ),
        }
        result = client.request("POST", "/courses", body=body)
        course_obj = result.get("data") or result
        course_id = course_obj["id"]
        created["course"] = 1
        print(f"created course {course_id} (visibility="
              f"{'visible' if make_visible else 'hidden'})")

    # Creating a course auto-generates a placeholder "Chapter 1" containing an empty
    # "Lesson 1". It sorts first, and because this course sets
    # require_completing_lessons_in_order, an empty lesson would gate the entire
    # curriculum behind it. Remove it before adding the real chapters.
    if created["course"]:
        for chapter in client.paginate("/course_chapters", {"course_id": course_id}):
            if (chapter.get("title") or "").strip().casefold() != "chapter 1":
                continue
            lessons = client.paginate("/course_lessons", {"chapter_id": chapter["id"]})
            if any((lesson.get("content") or "").strip() for lesson in lessons):
                continue  # not a placeholder; leave it alone
            for lesson in lessons:
                client.request("DELETE", f"/course_lessons/{lesson['id']}")
            client.request("DELETE", f"/course_chapters/{chapter['id']}")
            print(f"  removed auto-generated placeholder chapter {chapter['id']}")

    # Chapters must be created in curriculum order -- the API has no order field on create.
    existing_chapters = client.paginate("/course_chapters", {"course_id": course_id})

    for chapter in course["chapters"]:
        chapter_obj = find_by_title(existing_chapters, chapter["title"])
        if chapter_obj:
            chapter_id = chapter_obj["id"]
            skipped["chapters"] += 1
            print(f"  chapter exists: {chapter['title']!r} ({chapter_id})")
        else:
            result = client.request(
                "POST",
                "/course_chapters",
                body={"course_id": course_id, "title": chapter["title"]},
            )
            chapter_obj = result.get("data") or result
            chapter_id = chapter_obj["id"]
            created["chapters"] += 1
            print(f"  created chapter {chapter_id}: {chapter['title']!r}")

        existing_lessons = client.paginate("/course_lessons", {"chapter_id": chapter_id})
        for lesson in chapter["lessons"]:
            if find_by_title(existing_lessons, lesson["title"]):
                skipped["lessons"] += 1
                print(f"    lesson exists: {lesson['title']!r}")
                continue
            result = client.request(
                "POST", "/course_lessons", body=lesson_payload(chapter_id, lesson)
            )
            lesson_obj = result.get("data") or result
            created["lessons"] += 1
            print(f"    created lesson {lesson_obj.get('id')}: {lesson['title']!r}")

    return {"course_id": course_id, "created": created, "skipped": skipped}


def print_plan(course: dict, experience_id: str, make_visible: bool) -> None:
    print("DRY RUN - no network calls will be made\n")
    print(f"POST {API_BASE}/courses")
    print(
        json.dumps(
            {
                "experience_id": experience_id or "<MISSING>",
                "title": course["title"],
                "tagline": course.get("tagline"),
                "description": course.get("description"),
                "visibility": "visible" if make_visible else "hidden",
                "require_completing_lessons_in_order": course.get(
                    "require_completing_lessons_in_order"
                ),
                "certificate_after_completion_enabled": course.get(
                    "certificate_after_completion_enabled"
                ),
            },
            indent=2,
        )
    )
    total_lessons = 0
    for index, chapter in enumerate(course["chapters"], 1):
        print(f"\nPOST {API_BASE}/course_chapters  #{index}")
        print(json.dumps({"course_id": "<from previous response>",
                          "title": chapter["title"]}, indent=2))
        for lesson in chapter["lessons"]:
            total_lessons += 1
            preview = lesson["content"][:70].replace("\n", " ")
            embed = (
                f", embed={lesson['embed_type']}:{lesson['embed_id']}"
                if lesson.get("embed_type")
                else ""
            )
            print(
                f"  POST {API_BASE}/course_lessons  "
                f"[{lesson['lesson_type']}{embed}] {lesson['title']!r} "
                f"({len(lesson['content'].split())} words) -- {preview}..."
            )
    print(
        f"\nTotal: 1 course, {len(course['chapters'])} chapters, {total_lessons} lessons"
        f" = {1 + len(course['chapters']) + total_lessons} write calls"
    )
    print("Idempotency: a real run lists existing items and matches on title first.")


def check_auth(client: Whop) -> int:
    print("Verifying credentials...")
    try:
        me = client.request("GET", "/me")
        data = me.get("data") or me
        print(f"  authenticated: {json.dumps(data)[:400]}")
    except WhopError as exc:
        if exc.status in (401, 403):
            print(f"  key rejected (HTTP {exc.status}). Check the key and its permissions.",
                  file=sys.stderr)
            return 1
        print(f"  /me not available ({exc.status}); continuing to experience check.")

    try:
        experiences = client.paginate("/experiences", {})
    except WhopError as exc:
        print(f"error: could not list experiences: {exc}", file=sys.stderr)
        return 1

    if not experiences:
        print("  no experiences visible to this key.")
        return 1
    print(f"  {len(experiences)} experience(s) visible:")
    for experience in experiences:
        print(f"    {experience.get('id')}  {experience.get('name')!r}")
    print("\nUse one of these IDs as WHOP_EXPERIENCE_ID.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the request plan without calling the API")
    parser.add_argument("--check-auth", action="store_true",
                        help="verify the key and list visible experiences")
    parser.add_argument("--make-visible", action="store_true",
                        help="create the course visible instead of hidden")
    parser.add_argument("--api-key")
    parser.add_argument("--experience-id")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not COURSE_PATH.exists():
        print(f"error: {COURSE_PATH.name} missing. Run: python build_course.py",
              file=sys.stderr)
        return 1
    course = json.loads(COURSE_PATH.read_text(encoding="utf-8"))

    if args.dry_run:
        env_file = _read_env_file()
        experience_id = (
            args.experience_id
            or os.environ.get("WHOP_EXPERIENCE_ID")
            or env_file.get("WHOP_EXPERIENCE_ID")
        )
        print_plan(course, experience_id, args.make_visible)
        return 0

    api_key, experience_id = resolve_credentials(args)
    client = Whop(api_key, verbose=args.verbose)

    if args.check_auth:
        return check_auth(client)

    if args.make_visible:
        print("WARNING: --make-visible creates a publicly visible course.")

    try:
        summary = publish(client, course, experience_id, args.make_visible)
    except WhopError as exc:
        print(f"\npublish failed: {exc}", file=sys.stderr)
        if exc.status in (401, 403):
            print("The key was rejected. Confirm it carries 'courses:update'.",
                  file=sys.stderr)
        return 1

    print(
        f"\ndone in {client.calls} API calls. "
        f"created: {summary['created']}, already present: {summary['skipped']}"
    )
    print(f"course id: {summary['course_id']}")
    if not args.make_visible:
        print("The course is HIDDEN. Review it in the Whop dashboard, then publish it "
              "visible when you are satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
