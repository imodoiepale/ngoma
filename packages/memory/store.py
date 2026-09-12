"""Temporal memory — what worked, for whom, when, and what superseded it.

The corpus graph (`graph/`) is static: workflows, node packs, models. This is the other
half — operational facts that *change*, and whose change is the point:

    "Pearl editorial performed well for Kenyan professionals"   valid 1 Jul - 29 Jul
    "Editorial cartoon superseded it"                           valid from 30 Jul

A plain key-value store loses that. Overwriting "what works" with the latest answer throws
away the thing you most need later: that it used to be true, when it stopped, and what
replaced it. So every fact here is **bitemporal** — it carries `valid_from`, an optional
`valid_to`, and the observation that produced it.

Design decisions worth stating:

  * **SQLite, not Neo4j, by default.** Graphiti + Neo4j is the richer answer and
    `infra/memory/` deploys it, but it needs Docker, a database and an LLM key to extract
    entities. Everything else in this repo runs with none of those, and a memory layer you
    cannot query on a laptop is a memory layer you will not use. The schema below maps
    cleanly onto Graphiti's episode/entity/edge model when you want it.
  * **Nothing is deleted.** Superseding a fact closes its validity window and records what
    replaced it. `as_of()` reconstructs what the system believed on any past date.
  * **Confidence travels with the fact.** A learning from 3 posts and one from 300 are not
    the same claim, and the store refuses to pretend otherwise.
  * **No secrets, no binaries, no raw prompts.** Memory holds ids, checksums, metrics and
    relationships. Assets stay on disk.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "packages" / "memory" / "memory.sqlite3"
VAULT = REPO / "memory-vault"

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
  id           INTEGER PRIMARY KEY,
  brand        TEXT NOT NULL,
  kind         TEXT NOT NULL,      -- learning | metric | approval | fatigue | correction
  subject      TEXT NOT NULL,      -- what the fact is about (a style, hook, audience...)
  predicate    TEXT NOT NULL,      -- performed_well_for | fatigued_for | superseded | ...
  object       TEXT,               -- the other side, when there is one
  value        REAL,               -- the measured number, when there is one
  unit         TEXT,
  audience     TEXT,
  platform     TEXT,
  confidence   REAL NOT NULL DEFAULT 0.5,
  sample_size  INTEGER NOT NULL DEFAULT 0,
  valid_from   TEXT NOT NULL,
  valid_to     TEXT,               -- NULL = still believed
  superseded_by INTEGER REFERENCES facts(id),
  source       TEXT NOT NULL,      -- experiment id, plan file, human name
  recorded_at  TEXT NOT NULL,
  note         TEXT
);
CREATE INDEX IF NOT EXISTS ix_facts_brand   ON facts(brand);
CREATE INDEX IF NOT EXISTS ix_facts_subject ON facts(subject);
CREATE INDEX IF NOT EXISTS ix_facts_live    ON facts(brand, valid_to);

CREATE TABLE IF NOT EXISTS episodes (
  id          INTEGER PRIMARY KEY,
  brand       TEXT NOT NULL,
  kind        TEXT NOT NULL,       -- publish | analytics | review | decision
  ref         TEXT,                -- campaign id, post id, plan path
  happened_at TEXT NOT NULL,
  payload     TEXT NOT NULL,       -- JSON; ids and metrics only, never assets or secrets
  recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ep_brand ON episodes(brand, happened_at);
"""

# Anything matching these never enters memory. Cheap, and it catches the obvious mistakes.
FORBIDDEN_KEYS = {"api_key", "apikey", "token", "secret", "password", "authorization",
                  "access_token", "refresh_token", "cookie", "prompt_raw"}


class MemoryError_(RuntimeError):
    pass


@dataclass
class Fact:
    brand: str
    kind: str
    subject: str
    predicate: str
    object: str | None = None
    value: float | None = None
    unit: str | None = None
    audience: str | None = None
    platform: str | None = None
    confidence: float = 0.5
    sample_size: int = 0
    valid_from: str = field(default_factory=lambda: date.today().isoformat())
    valid_to: str | None = None
    source: str = "unspecified"
    note: str | None = None


def connect(db: Path = DB) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    """Refuse to store anything secret-shaped. Memory is shared context, not a vault."""
    bad = [k for k in payload if k.lower() in FORBIDDEN_KEYS]
    if bad:
        raise MemoryError_(
            f"refusing to store key(s) {bad} in memory — credentials and raw prompts never "
            f"belong here. Store ids and metrics instead.")
    return payload


def record(con: sqlite3.Connection, f: Fact) -> int:
    if f.sample_size and f.sample_size < 3 and f.confidence > 0.6:
        raise MemoryError_(
            f"confidence {f.confidence} from {f.sample_size} sample(s) is not a finding. "
            f"Lower the confidence or gather more data.")
    cur = con.execute(
        "INSERT INTO facts (brand,kind,subject,predicate,object,value,unit,audience,platform,"
        "confidence,sample_size,valid_from,valid_to,source,recorded_at,note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f.brand, f.kind, f.subject, f.predicate, f.object, f.value, f.unit, f.audience,
         f.platform, f.confidence, f.sample_size, f.valid_from, f.valid_to, f.source,
         datetime.now(timezone.utc).isoformat(), f.note))
    con.commit()
    return int(cur.lastrowid)


def supersede(con: sqlite3.Connection, old_id: int, new: Fact, on: str | None = None) -> int:
    """Close a fact's validity window and link what replaced it. Never deletes."""
    row = con.execute("SELECT * FROM facts WHERE id=?", (old_id,)).fetchone()
    if not row:
        raise MemoryError_(f"no fact with id {old_id}")
    if row["valid_to"]:
        raise MemoryError_(f"fact {old_id} already ended on {row['valid_to']}")
    when = on or new.valid_from or date.today().isoformat()
    new_id = record(con, new)
    con.execute("UPDATE facts SET valid_to=?, superseded_by=? WHERE id=?",
                (when, new_id, old_id))
    con.commit()
    return new_id


def believed(con: sqlite3.Connection, brand: str | None = None,
             subject: str | None = None, as_of: str | None = None) -> list[sqlite3.Row]:
    """What was believed on a date. Defaults to now."""
    when = as_of or date.today().isoformat()
    q = ["SELECT * FROM facts WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)"]
    args: list[Any] = [when, when]
    if brand:
        q.append("AND brand = ?")
        args.append(brand)
    if subject:
        q.append("AND subject LIKE ?")
        args.append(f"%{subject}%")
    q.append("ORDER BY confidence DESC, sample_size DESC")
    return list(con.execute(" ".join(q), args))


def history(con: sqlite3.Connection, subject: str) -> list[sqlite3.Row]:
    return list(con.execute(
        "SELECT * FROM facts WHERE subject LIKE ? ORDER BY valid_from", (f"%{subject}%",)))


def episode(con: sqlite3.Connection, brand: str, kind: str, payload: dict[str, Any],
            ref: str | None = None, happened_at: str | None = None) -> int:
    cur = con.execute(
        "INSERT INTO episodes (brand,kind,ref,happened_at,payload,recorded_at) "
        "VALUES (?,?,?,?,?,?)",
        (brand, kind, ref, happened_at or datetime.now(timezone.utc).isoformat(),
         json.dumps(_scrub(payload), ensure_ascii=False),
         datetime.now(timezone.utc).isoformat()))
    con.commit()
    return int(cur.lastrowid)


# --------------------------------------------------------------- the seven questions

PRE_CAMPAIGN = [
    ("What brand rules are currently valid?", "rule"),
    ("What worked with this audience?", "performed_well_for"),
    ("Which styles have become repetitive?", "fatigued_for"),
    ("What did we publish in the last 30 days?", None),
    ("What failed?", "underperformed_for"),
    ("What was corrected by a human?", "correction"),
    ("Which approved skills apply?", "skill"),
]


def brief_context(con: sqlite3.Connection, brand: str) -> dict[str, Any]:
    """The questions to ask before planning a campaign, answered from memory."""
    out: dict[str, Any] = {"brand": brand, "as_of": date.today().isoformat()}
    live = believed(con, brand)
    out["valid_rules"] = [dict(r) for r in live if r["kind"] == "rule"]
    out["worked"] = [dict(r) for r in live if r["predicate"] == "performed_well_for"]
    out["fatigued"] = [dict(r) for r in live if r["predicate"] == "fatigued_for"]
    out["failed"] = [dict(r) for r in live if r["predicate"] == "underperformed_for"]
    out["corrections"] = [dict(r) for r in live if r["kind"] == "correction"]
    recent = con.execute(
        "SELECT kind, ref, happened_at FROM episodes WHERE brand=? "
        "AND happened_at >= date('now','-30 day') ORDER BY happened_at DESC LIMIT 50", (brand,))
    out["last_30_days"] = [dict(r) for r in recent]
    if not live:
        out["note"] = ("memory is empty for this brand. Every answer below is 'unknown', "
                       "which is the honest state before anything has been published — "
                       "not a signal that nothing is fatigued.")
    return out


# --------------------------------------------------------------- vault mirror

def write_vault(con: sqlite3.Connection, brand: str | None = None) -> int:
    """Mirror live facts as Obsidian-openable notes.

    The database stays authoritative; these are the human-readable view. Wiki-links make
    the relationships browsable in a graph view without running Neo4j.
    """
    VAULT.mkdir(parents=True, exist_ok=True)
    rows = believed(con, brand)
    n = 0
    for r in rows:
        slug = f"{r['kind']}-{r['id']:05d}"
        body = [
            "---",
            f"id: {r['id']}",
            f"brand: {r['brand']}",
            f"kind: {r['kind']}",
            f"confidence: {r['confidence']}",
            f"sample_size: {r['sample_size']}",
            f"valid_from: {r['valid_from']}",
            f"valid_to: {r['valid_to'] or 'still believed'}",
            f"source: {r['source']}",
            "---",
            "",
            f"# {r['subject']} — {r['predicate'].replace('_', ' ')}"
            + (f" {r['object']}" if r["object"] else ""),
            "",
        ]
        if r["value"] is not None:
            body.append(f"Measured: **{r['value']}{r['unit'] or ''}** "
                        f"over {r['sample_size']} item(s).")
        if r["note"]:
            body += ["", r["note"]]
        body += ["", "Related:", f"- [[subject - {r['subject']}]]"]
        if r["audience"]:
            body.append(f"- [[audience - {r['audience']}]]")
        if r["object"]:
            body.append(f"- [[subject - {r['object']}]]")
        (VAULT / f"{slug}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        n += 1
    (VAULT / "README.md").write_text(
        "# Memory vault\n\n"
        "Human-readable mirror of `packages/memory/memory.sqlite3`. The database is\n"
        "authoritative; these notes are regenerated by `store.py vault` and are safe to\n"
        "delete. Open this folder as an Obsidian vault to browse the graph.\n\n"
        f"{n} live fact(s) as of {date.today().isoformat()}.\n", encoding="utf-8")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Temporal memory: what worked, when, and why.")
    ap.add_argument("command", choices=["record", "supersede", "believed", "history",
                                        "context", "vault", "seed", "stats"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--kind", default="learning")
    ap.add_argument("--subject")
    ap.add_argument("--predicate", default="performed_well_for")
    ap.add_argument("--object")
    ap.add_argument("--value", type=float)
    ap.add_argument("--unit")
    ap.add_argument("--audience")
    ap.add_argument("--confidence", type=float, default=0.5)
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--source", default="manual")
    ap.add_argument("--note")
    ap.add_argument("--id", type=int)
    ap.add_argument("--as-of")
    a = ap.parse_args()

    con = connect()

    if a.command == "stats":
        f = con.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"]
        live = con.execute("SELECT COUNT(*) c FROM facts WHERE valid_to IS NULL").fetchone()["c"]
        ep = con.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
        print(f"{f} fact(s) total, {live} still believed, {ep} episode(s)")
        print(f"db: {DB}")
        return

    if a.command == "record":
        if not a.subject:
            raise SystemExit("--subject is required")
        fid = record(con, Fact(brand=a.brand, kind=a.kind, subject=a.subject,
                               predicate=a.predicate, object=a.object, value=a.value,
                               unit=a.unit, audience=a.audience, confidence=a.confidence,
                               sample_size=a.samples, source=a.source, note=a.note))
        print(f"recorded fact {fid}")
        return

    if a.command == "supersede":
        if not a.id or not a.subject:
            raise SystemExit("--id (the fact being replaced) and --subject are required")
        nid = supersede(con, a.id, Fact(
            brand=a.brand, kind=a.kind, subject=a.subject, predicate=a.predicate,
            object=a.object, value=a.value, unit=a.unit, audience=a.audience,
            confidence=a.confidence, sample_size=a.samples, source=a.source, note=a.note))
        print(f"fact {a.id} ended; superseded by {nid}")
        return

    if a.command == "believed":
        rows = believed(con, a.brand, a.subject, a.as_of)
        if not rows:
            print(f"nothing believed for {a.brand} as of {a.as_of or 'today'}")
        for r in rows:
            v = f"  {r['value']}{r['unit'] or ''}" if r["value"] is not None else ""
            print(f"[{r['id']:>3}] {r['subject']} {r['predicate']} {r['object'] or ''}{v}"
                  f"   conf {r['confidence']} n={r['sample_size']}  since {r['valid_from']}")
        return

    if a.command == "history":
        if not a.subject:
            raise SystemExit("--subject is required")
        for r in history(con, a.subject):
            end = r["valid_to"] or "now"
            sup = f" -> superseded by {r['superseded_by']}" if r["superseded_by"] else ""
            print(f"[{r['id']:>3}] {r['valid_from']} .. {end}  {r['subject']} "
                  f"{r['predicate']} {r['object'] or ''}{sup}")
        return

    if a.command == "context":
        ctx = brief_context(con, a.brand)
        print(json.dumps(ctx, indent=2, ensure_ascii=False)[:2500])
        return

    if a.command == "vault":
        n = write_vault(con, a.brand)
        print(f"{n} live fact(s) mirrored to {VAULT}")
        return

    if a.command == "seed":
        # A worked example of supersession, so the shape is obvious before real data lands.
        old = record(con, Fact(
            brand=a.brand, kind="learning", subject="pearl_editorial_data",
            predicate="performed_well_for", object="saves", audience="kenyan professionals",
            value=18.0, unit="% lift", confidence=0.72, sample_size=14,
            valid_from="2026-07-01", source="EXP-221",
            note="carousels in this grammar out-saved the baseline across four runs"))
        new = supersede(con, old, Fact(
            brand=a.brand, kind="learning", subject="kenyan_meme_original",
            predicate="performed_well_for", object="saves", audience="kenyan professionals",
            value=26.0, unit="% lift", confidence=0.68, sample_size=12,
            valid_from="2026-07-30", source="EXP-251",
            note="overtook pearl editorial; pearl was not wrong, it was superseded"),
            on="2026-07-29")
        record(con, Fact(
            brand=a.brand, kind="learning", subject="pearl_editorial_data",
            predicate="fatigued_for", audience="kenyan professionals",
            confidence=0.6, sample_size=12, valid_from="2026-07-30", source="EXP-251",
            note="repeat exposure; rest the grammar rather than retire it"))
        episode(con, a.brand, "analytics", {"experiment": "EXP-251", "items": 12},
                ref="EXP-251")
        print(f"seeded: fact {old} superseded by {new}, plus a fatigue fact and an episode")
        print("this is a worked example of the shape, not real performance data")
        return


if __name__ == "__main__":
    try:
        main()
    except MemoryError_ as e:
        raise SystemExit(f"error: {e}")
