---
chapter: Operations
title: Archive, search and daily source watch
lesson_type: text
embed_type: null
embed_id: null
---

# Archive, search and daily source watch

This field moves weekly. A model that changed how you work three months ago has been
superseded twice. The purpose of an archive is to stop paying the same research cost
repeatedly, and to make "what did that tutorial say about masks" a five-second question.

## Archive once, properly

When you find a useful source, capture it completely the first time:

- The media itself.
- The transcript or captions.
- The full description — specifically the **unshortened** links, since platform UIs truncate
  them and the useful resource is usually in the hidden part.
- Metadata: uploader, date, duration, IDs.
- Comments, where available. Often the highest-signal part, because that is where people
  report what actually broke.
- Any attached workflow files or resource bundles.

Capture partially and you will return to the source later, find it edited, region-locked or
deleted, and have to reconstruct.

## Index for retrieval, not storage

An archive nobody can search is a hard drive. Build a full-text index over the *text* — the
transcripts, descriptions, captions, and workflow JSON — with a stable identifier per source,
so a query returns a pointer to the exact source and a snippet of context.

Two rules that keep it useful:

- **Index text, store media.** Full-text search over transcripts is fast and small; the video
  files are just referenced.
- **Rebuild is cheap, so rebuild often.** Treat the index as derived, never as the source of
  truth. It should be reconstructible from the archive directory in one command.

Keep your index count honest. If your notes say one number and the index says another, the
index is right and the notes are stale — this is exactly the kind of small drift that erodes
trust in your own documentation.

## Monitoring sources

Maintain a machine-readable list of sources to watch, with per-source scope — a whole channel,
a single video and its context, a profile and its new posts. Then a scheduled job:

1. Reads the source list.
2. Fetches current items.
3. **Deduplicates against what you already have,** by stable source ID.
4. Downloads only the new material and re-indexes.
5. Reports.

Point four is the one that determines whether this survives contact with real life: **report
only changes.** A job that says "nothing new" every day trains you to ignore it. A job that
speaks only when something arrived, or when something failed, stays worth reading.

## Make the automation real

The distinction that matters more than any implementation detail: a scheduled job either
exists as a registered, running thing, or it does not exist. A description of a monitoring
job in a document is not a monitoring job.

Concretely, when you claim a watcher exists, be able to answer:

- What is the schedule, in what timezone?
- Where is it registered, and what command does it run?
- Where does its output go?
- When did it last run, and what did it say?

If you cannot answer all four, you have prose, not automation. Verify by listing the scheduled
jobs on the system and finding it there.

Also know your scheduler's lifetime. Some schedulers are session-scoped and vanish when the
process exits; some expire after a fixed period. A watcher that silently stopped a month ago is
worse than no watcher, because you have been trusting it.

## Failure handling

Downloads fail for ordinary reasons: rate limits, region blocks, authentication walls,
platform changes, deleted sources. Design for it:

- Record per-item status, not just an overall success.
- Distinguish "failed, retry later" from "unavailable, stop trying".
- Keep the downloader itself updatable — platform extractors break constantly and a version
  bump is usually the entire fix.
- Never let a partial run be reported as a complete one. Report retrieved-versus-expected
  counts and name what failed.

That last point is a habit, not a feature. "Downloaded the profile" and "downloaded 175 of 187
posts, 12 unavailable" are different statements, and only the second one is useful.

## Deliverable

A complete archive of at least ten sources with transcripts and unshortened links, a working
full-text index you can query, and a registered scheduled watcher that you have verified
appears in the system's job list.
