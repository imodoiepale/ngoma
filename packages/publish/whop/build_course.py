#!/usr/bin/env python3
"""Assemble whop-course.json from lessons/*.md.

Lesson files are named NN-MM-slug.md where NN is the chapter index and MM the lesson
index within that chapter. Ordering is taken from those numbers, which matters because
the Whop API has no `order` field on chapter or lesson create -- ordering follows
creation sequence.

Usage:
    python build_course.py            # write whop-course.json
    python build_course.py --check    # validate only, non-zero exit on problems
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LESSON_DIR = HERE / "lessons"
OUT_PATH = HERE / "whop-course.json"

COURSE = {
    "title": "EPALLE AI Creative Studio",
    "tagline": "Build character, UGC and music-video pipelines on your own GPU studio",
    "description": (
        "A practical course in running a self-hosted generative studio: persistent GPU "
        "infrastructure, character datasets from a handful of references, motion transfer "
        "and character replacement, claim-safe short-form advertising localised for East "
        "African and francophone markets, and original music-video direction."
    ),
    "visibility": "hidden",
    "require_completing_lessons_in_order": True,
    "certificate_after_completion_enabled": True,
}

# Whop lesson_type enum, from the verified API contract.
VALID_LESSON_TYPES = {"text", "video", "pdf", "multi", "quiz", "knowledge_check"}
VALID_EMBED_TYPES = {"youtube", "loom"}
TITLE_MAX = 120

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
FILENAME_RE = re.compile(r"^(\d+)-(\d+)-[a-z0-9-]+\.md$")


def parse_frontmatter(text: str, path: Path) -> tuple[dict, str]:
    """Minimal frontmatter parser: `key: value` plus `key:` followed by `- item` lines.

    Deliberately not PyYAML -- this keeps the course build dependency-free.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path.name}: missing or malformed frontmatter block")

    raw, body = match.group(1), match.group(2)
    meta: dict = {}
    current_list_key: str | None = None

    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if current_list_key is None:
                raise ValueError(f"{path.name}: list item outside of a key: {line!r}")
            meta[current_list_key].append(line.lstrip()[2:].strip())
            continue
        if ":" not in line:
            raise ValueError(f"{path.name}: cannot parse frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            meta[key] = []
            current_list_key = key
        else:
            current_list_key = None
            meta[key] = None if value in ("null", "~") else value

    return meta, body.strip()


def load_lessons() -> list[dict]:
    lessons = []
    for path in sorted(LESSON_DIR.glob("*.md")):
        name_match = FILENAME_RE.match(path.name)
        if not name_match:
            raise ValueError(
                f"{path.name}: filename must be NN-MM-slug.md so ordering is explicit"
            )
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"), path)

        for required in ("chapter", "title", "lesson_type"):
            if not meta.get(required):
                raise ValueError(f"{path.name}: frontmatter missing '{required}'")

        lesson_type = meta["lesson_type"]
        if lesson_type not in VALID_LESSON_TYPES:
            raise ValueError(
                f"{path.name}: lesson_type {lesson_type!r} not one of "
                f"{sorted(VALID_LESSON_TYPES)}"
            )

        title = meta["title"]
        if len(title) > TITLE_MAX:
            raise ValueError(
                f"{path.name}: title is {len(title)} chars, Whop caps it at {TITLE_MAX}"
            )

        embed_type = meta.get("embed_type")
        embed_id = meta.get("embed_id")
        if embed_type and embed_type not in VALID_EMBED_TYPES:
            raise ValueError(
                f"{path.name}: embed_type {embed_type!r} not one of "
                f"{sorted(VALID_EMBED_TYPES)}"
            )
        if bool(embed_type) != bool(embed_id):
            raise ValueError(
                f"{path.name}: embed_type and embed_id must be set together or both null"
            )
        if embed_type and lesson_type != "video":
            raise ValueError(
                f"{path.name}: an embed is set but lesson_type is {lesson_type!r}; "
                "use lesson_type: video"
            )
        if not body:
            raise ValueError(f"{path.name}: lesson body is empty")

        lessons.append(
            {
                "_chapter_index": int(name_match.group(1)),
                "_lesson_index": int(name_match.group(2)),
                "_source": path.name,
                "chapter": meta["chapter"],
                "title": title,
                "lesson_type": lesson_type,
                "content": body,
                "embed_type": embed_type,
                "embed_id": embed_id,
                "references": meta.get("references") or [],
            }
        )
    return lessons


def build(lessons: list[dict]) -> dict:
    # Chapter order comes from the filename prefix, and each prefix must map to exactly
    # one chapter title.
    order: dict[int, str] = {}
    for lesson in lessons:
        idx, name = lesson["_chapter_index"], lesson["chapter"]
        if order.setdefault(idx, name) != name:
            raise ValueError(
                f"chapter index {idx} maps to both {order[idx]!r} and {name!r}"
            )

    chapters = []
    for idx in sorted(order):
        group = sorted(
            (les for les in lessons if les["_chapter_index"] == idx),
            key=lambda les: les["_lesson_index"],
        )
        seen = [les["_lesson_index"] for les in group]
        if len(set(seen)) != len(seen):
            raise ValueError(f"chapter {order[idx]!r} has duplicate lesson indexes: {seen}")
        chapters.append(
            {
                "title": order[idx],
                "lessons": [
                    {
                        "title": les["title"],
                        "lesson_type": les["lesson_type"],
                        "content": les["content"],
                        "embed_type": les["embed_type"],
                        "embed_id": les["embed_id"],
                        "references": les["references"],
                        "source_file": les["_source"],
                    }
                    for les in group
                ],
            }
        )

    return {**COURSE, "chapters": chapters}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="validate only, do not write output"
    )
    args = parser.parse_args()

    try:
        lessons = load_lessons()
        if not lessons:
            print(f"no lesson files found in {LESSON_DIR}", file=sys.stderr)
            return 1
        course = build(lessons)
    except ValueError as exc:
        print(f"course build failed: {exc}", file=sys.stderr)
        return 1

    total_lessons = sum(len(ch["lessons"]) for ch in course["chapters"])
    total_words = sum(
        len(les["content"].split()) for ch in course["chapters"] for les in ch["lessons"]
    )
    print(
        f"{len(course['chapters'])} chapters, {total_lessons} lessons, "
        f"~{total_words:,} words"
    )
    for chapter in course["chapters"]:
        print(f"  {chapter['title']}")
        for lesson in chapter["lessons"]:
            embed = (
                f" [{lesson['embed_type']}:{lesson['embed_id']}]"
                if lesson["embed_type"]
                else ""
            )
            print(
                f"    - {lesson['title']} ({lesson['lesson_type']}, "
                f"{len(lesson['content'].split())} words){embed}"
            )

    if args.check:
        print("check only, nothing written")
        return 0

    OUT_PATH.write_text(
        json.dumps(course, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_PATH.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
