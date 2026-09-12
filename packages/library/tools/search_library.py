#!/usr/bin/env python3
import pathlib, sqlite3, sys
db = pathlib.Path(__file__).resolve().parents[1] / "library.sqlite3"
query = " ".join(sys.argv[1:]).strip()
if not query: raise SystemExit("Usage: python search_library.py <words>")
with sqlite3.connect(db) as con:
    rows = con.execute("SELECT path, title, snippet(search,2,'[',']','…',18) FROM search WHERE search MATCH ? ORDER BY rank LIMIT 30", (query,))
    for path, title, snippet in rows: print(f"{path}\n  {title}\n  {snippet}\n")
