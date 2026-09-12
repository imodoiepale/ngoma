#!/usr/bin/env python3
import json, pathlib, sqlite3, hashlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "library.sqlite3"
TEXT_SUFFIXES = {".txt", ".md", ".vtt", ".srt", ".description", ".json"}
# The vendored yt-dlp checkout is ~1,100 .py files. Indexing it buried the actual
# research material -- transcripts, descriptions and workflows -- under extractor
# source code, so it is excluded from the searchable index.
EXCLUDE_PARTS = {".git", "node_modules", ".next", "yt-dlp", "__pycache__", ".venv"}
def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
with sqlite3.connect(DB) as con:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS assets(path TEXT PRIMARY KEY, kind TEXT, bytes INTEGER, sha256 TEXT, source_id TEXT, title TEXT, text TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(path, title, text);
    DELETE FROM assets; DELETE FROM search;
    """)
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == DB or any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        body = ""
        if path.suffix.lower() in TEXT_SUFFIXES or path.name.endswith(".description"):
            try: body = path.read_text("utf-8", errors="replace")
            except OSError: pass
        source_id = next((p for p in path.parts if re.fullmatch(r"[A-Za-z0-9_-]{11}", p)), "")
        title = path.stem
        con.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)", (rel, path.suffix.lower() or "file", path.stat().st_size, sha256(path), source_id, title, body))
        con.execute("INSERT INTO search VALUES(?,?,?)", (rel, title, body))
    con.commit()
    count = con.execute("SELECT count(*) FROM assets").fetchone()[0]
print(json.dumps({"database": str(DB), "assets": count}))
