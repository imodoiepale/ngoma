# EPALLE Creative Studio Library

This archive keeps source material, transcripts, public metadata, comments returned by the platform, workflows, model manifests, and local search data together. It is a working research library; ownership and reuse rights remain with each source creator.

## Layout

- videos/source-id: archived YouTube media, captions, descriptions, thumbnails and info metadata when available.
- sources: user-provided transcripts and downloaded public resource attachments.
- workflows: MATRIX Dataset V1, SCAIL-2, MiniMax H3 and related reference graphs.
- manifests: source lists, checksums, model revisions and monitor configuration.
- tools/yt-dlp: source checkout of the downloader used for this archive.
- library.sqlite3: full-text search index across readable files.

## Fast search

Run `python tools/search_library.py "character replacement"`.

Rebuild after adding files with `python tools/build_library_index.py`.

The daily Codex automation reads manifests/monitored-sources.json, deduplicates by source ID, and reports only new material, access problems, or failures. Instagram may show public profile metadata while withholding full media from logged-out tools; such gaps are recorded rather than bypassed.
