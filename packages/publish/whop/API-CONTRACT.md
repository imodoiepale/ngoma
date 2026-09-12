# Whop Courses API — verified contract

Fetched from the official docs on 2026-09-06. Do not guess these fields; re-verify if
publishing starts failing.

- Base URL: `https://api.whop.com/api/v1`
- Auth header: `Authorization: Bearer $WHOP_API_KEY`
- Version header: `Api-Version-Date: 2026-07-01` (date-based versioning, optional but recommended)
- Required permission: `courses:update`
- Key type: an **Account API Key** (Whop dashboard -> Account API Keys -> Create)

## POST /courses

| Field | Type | Required |
|---|---|---|
| `experience_id` | string (`exp_...`) | yes |
| `title` | string | yes |
| `tagline` | string \| null | no |
| `description` | string \| null | no |
| `thumbnail` | `{id: string}` \| null | no |
| `order` | string \| null | no |
| `visibility` | `"visible"` \| `"hidden"` \| null | no |
| `certificate_after_completion_enabled` | boolean \| null | no |
| `require_completing_lessons_in_order` | boolean \| null | no |

## POST /course_chapters

| Field | Type | Required |
|---|---|---|
| `course_id` | string (`course_...`) | yes |
| `title` | string \| null | no |

Chapters have no `order` field on create — ordering follows creation sequence, so chapters
must be created in curriculum order.

## POST /course_lessons

| Field | Type | Required |
|---|---|---|
| `chapter_id` | string (`chap_...`) | yes |
| `lesson_type` | `text` \| `video` \| `pdf` \| `multi` \| `quiz` \| `knowledge_check` | yes |
| `title` | string \| null (max 120 chars) | no |
| `content` | string \| null (Markdown body) | no |
| `embed_type` | `youtube` \| `loom` \| null | no |
| `embed_id` | string \| null | no |
| `days_from_course_start_until_unlock` | integer \| null | no |
| `thumbnail` | `{id: string}` \| null | no |

Lessons also have no `order` field on create — same rule, create in order.

## Idempotency

There is no upsert. `whop_publish.py` therefore lists existing courses/chapters/lessons and
matches on title before creating, so a re-run does not duplicate the tree.

Sources:
- https://docs.whop.com/developer/api/getting-started
- https://docs.whop.com/api-reference/courses/create-course
- https://docs.whop.com/api-reference/course-chapters/create-course-chapter
- https://docs.whop.com/api-reference/course-lessons/create-course-lesson
