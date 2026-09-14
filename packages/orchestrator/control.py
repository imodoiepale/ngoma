"""Control plane — goals, tasks, budgets, approvals and an audit trail.

The job a "company control plane" actually does, implemented against the tools that are
installed here rather than against a product that may or may not exist.

The separation that matters is not which vendor runs it. It is:

    the control plane decides WHAT may happen and WHO pays for it
    the worker runtime decides HOW to do it

Keep those apart and you can swap either side. Merge them and the thing that decides what
is allowed is the same thing that wants to do it — which is how an autonomous system
removes its own brakes.

So this module owns: goals, tasks, assignment, spend, approval gates and an append-only
audit log. It knows nothing about how a task gets done. `workers.py` owns that, and any
runtime — Claude Code, Codex, or something else later — plugs in behind one interface.

Four invariants, enforced rather than documented:

  * **Budgets are checked before work starts, not after it bills.** A task whose estimate
    exceeds its remaining budget never dispatches.
  * **A worker cannot approve its own task.** Approver identity is recorded and compared.
  * **The audit log is append-only.** Rows are never updated or deleted; a correction is a
    new row that references the old one.
  * **Risky task types always require a human**, regardless of budget or confidence.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "packages" / "orchestrator" / "control.sqlite3"

# Task types that ALWAYS need a human, whatever the budget says. These are the actions
# whose cost is not measured in dollars.
ALWAYS_HUMAN = {
    "publish",           # reaches an audience
    "publish_now",
    "whatsapp_status",
    "spend_increase",    # changes what may be spent
    "skill_promote",     # changes what the system will do next time
    "brand_change",      # changes what the brand is
    "credential_change",
    "delete",
    "engine_run",        # one approval to let the director engine run a whole workflow
    "engine_stage",      # one approval per stage when the engine is in stage-approval mode
}

# Task types a worker may take unattended, given budget.
AUTONOMOUS_OK = {
    "plan", "analyse", "harvest", "transcribe", "graph_rebuild", "validate",
    "generate_draft", "composite", "research", "test", "report",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY, brand TEXT NOT NULL, title TEXT NOT NULL,
  metric TEXT, target REAL, due TEXT, status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, runtime TEXT NOT NULL,
  role TEXT, budget_usd REAL NOT NULL DEFAULT 0, spent_usd REAL NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY, brand TEXT NOT NULL, goal_id INTEGER REFERENCES goals(id),
  kind TEXT NOT NULL, title TEXT NOT NULL, spec TEXT NOT NULL,
  assigned_to TEXT REFERENCES workers(name),
  estimate_usd REAL NOT NULL DEFAULT 0, actual_usd REAL,
  status TEXT NOT NULL DEFAULT 'proposed',
  requires_human INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT, approved_at TEXT,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  started_at TEXT, finished_at TEXT, result TEXT
);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status, brand);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, subject TEXT, detail TEXT,
  prev_hash TEXT, hash TEXT NOT NULL
);
"""

TERMINAL = {"done", "failed", "cancelled", "rejected"}


class ControlError(RuntimeError):
    pass


@dataclass
class Task:
    brand: str
    kind: str
    title: str
    spec: dict[str, Any] = field(default_factory=dict)
    goal_id: int | None = None
    assigned_to: str | None = None
    estimate_usd: float = 0.0
    created_by: str = "system"


def connect(db: Path = DB) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit(con: sqlite3.Connection, actor: str, action: str,
          subject: str | None = None, detail: Any = None) -> str:
    """Append-only, hash-chained. A tampered or deleted row breaks the chain and
    `verify_audit` will say where."""
    prev = con.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev["hash"] if prev else ""
    at = _now()
    payload = json.dumps(detail, ensure_ascii=False, sort_keys=True) if detail else ""
    h = hashlib.sha256(f"{prev_hash}|{at}|{actor}|{action}|{subject}|{payload}"
                       .encode()).hexdigest()
    con.execute("INSERT INTO audit (at,actor,action,subject,detail,prev_hash,hash) "
                "VALUES (?,?,?,?,?,?,?)", (at, actor, action, subject, payload, prev_hash, h))
    con.commit()
    return h


def verify_audit(con: sqlite3.Connection) -> tuple[bool, str]:
    prev = ""
    for r in con.execute("SELECT * FROM audit ORDER BY id"):
        expect = hashlib.sha256(
            f"{prev}|{r['at']}|{r['actor']}|{r['action']}|{r['subject']}|{r['detail'] or ''}"
            .encode()).hexdigest()
        if expect != r["hash"]:
            return False, f"chain breaks at audit row {r['id']} ({r['action']})"
        prev = r["hash"]
    return True, f"chain intact across {con.execute('SELECT COUNT(*) c FROM audit').fetchone()['c']} row(s)"


# ---------------------------------------------------------------- workers

def add_worker(con: sqlite3.Connection, name: str, runtime: str, role: str,
               budget_usd: float, actor: str = "human") -> int:
    cur = con.execute(
        "INSERT OR REPLACE INTO workers (name,runtime,role,budget_usd,spent_usd,enabled,created_at) "
        "VALUES (?,?,?,?,COALESCE((SELECT spent_usd FROM workers WHERE name=?),0),1,?)",
        (name, runtime, role, budget_usd, name, _now()))
    audit(con, actor, "worker.add", name,
          {"runtime": runtime, "role": role, "budget_usd": budget_usd})
    con.commit()
    return int(cur.lastrowid)


def worker(con: sqlite3.Connection, name: str) -> sqlite3.Row:
    r = con.execute("SELECT * FROM workers WHERE name=?", (name,)).fetchone()
    if not r:
        raise ControlError(f"no worker named {name!r}; run `workers` to list them")
    return r


def remaining_budget(con: sqlite3.Connection, name: str) -> float:
    w = worker(con, name)
    return round(w["budget_usd"] - w["spent_usd"], 4)


# ---------------------------------------------------------------- tasks

def propose(con: sqlite3.Connection, t: Task) -> int:
    if t.kind not in ALWAYS_HUMAN | AUTONOMOUS_OK:
        raise ControlError(
            f"unknown task kind {t.kind!r}. Add it to AUTONOMOUS_OK or ALWAYS_HUMAN "
            f"deliberately — an unclassified task type would default to whichever is "
            f"convenient, and that is how gates erode.")
    needs_human = t.kind in ALWAYS_HUMAN
    cur = con.execute(
        "INSERT INTO tasks (brand,goal_id,kind,title,spec,assigned_to,estimate_usd,"
        "status,requires_human,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (t.brand, t.goal_id, t.kind, t.title, json.dumps(t.spec, ensure_ascii=False),
         t.assigned_to, t.estimate_usd, "awaiting_approval" if needs_human else "ready",
         int(needs_human), t.created_by, _now()))
    tid = int(cur.lastrowid)
    audit(con, t.created_by, "task.propose", str(tid),
          {"kind": t.kind, "title": t.title, "estimate_usd": t.estimate_usd,
           "requires_human": needs_human})
    con.commit()
    return tid


def approve(con: sqlite3.Connection, task_id: int, approver: str) -> None:
    r = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not r:
        raise ControlError(f"no task {task_id}")
    if r["status"] != "awaiting_approval":
        raise ControlError(f"task {task_id} is {r['status']}, not awaiting approval")
    if approver == r["assigned_to"]:
        raise ControlError(
            f"{approver!r} is the assigned worker and cannot approve its own task. "
            f"Separation of duties is the point of the gate.")
    if approver == r["created_by"] and approver != "human":
        raise ControlError(
            f"{approver!r} created this task and cannot also approve it.")
    con.execute("UPDATE tasks SET status='ready', approved_by=?, approved_at=? WHERE id=?",
                (approver, _now(), task_id))
    audit(con, approver, "task.approve", str(task_id), {"kind": r["kind"]})
    con.commit()


def reject(con: sqlite3.Connection, task_id: int, actor: str, why: str) -> None:
    con.execute("UPDATE tasks SET status='rejected', result=? WHERE id=?",
                (json.dumps({"rejected_by": actor, "why": why}), task_id))
    audit(con, actor, "task.reject", str(task_id), {"why": why})
    con.commit()


def admit(con: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    """The gate every task passes immediately before work starts."""
    r = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not r:
        raise ControlError(f"no task {task_id}")
    if r["status"] != "ready":
        raise ControlError(
            f"task {task_id} is {r['status']}. Only `ready` tasks dispatch"
            + (" — this one still needs human approval." if r["status"] == "awaiting_approval" else "."))
    if not r["assigned_to"]:
        raise ControlError(f"task {task_id} has no assigned worker")
    w = worker(con, r["assigned_to"])
    if not w["enabled"]:
        raise ControlError(f"worker {w['name']} is disabled")
    left = remaining_budget(con, w["name"])
    if r["estimate_usd"] > left:
        raise ControlError(
            f"task {task_id} estimates ${r['estimate_usd']:.2f} but {w['name']} has "
            f"${left:.2f} left of ${w['budget_usd']:.2f}. Budget is checked BEFORE work "
            f"starts, not after it bills.")
    return r


def start(con: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    r = admit(con, task_id)
    con.execute("UPDATE tasks SET status='running', started_at=? WHERE id=?",
                (_now(), task_id))
    audit(con, r["assigned_to"], "task.start", str(task_id), None)
    con.commit()
    return r


def finish(con: sqlite3.Connection, task_id: int, ok: bool,
           actual_usd: float = 0.0, result: Any = None) -> None:
    r = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not r:
        raise ControlError(f"no task {task_id}")
    con.execute("UPDATE tasks SET status=?, actual_usd=?, finished_at=?, result=? WHERE id=?",
                ("done" if ok else "failed", actual_usd, _now(),
                 json.dumps(result, ensure_ascii=False, default=str)[:4000], task_id))
    if r["assigned_to"] and actual_usd:
        con.execute("UPDATE workers SET spent_usd = spent_usd + ? WHERE name=?",
                    (actual_usd, r["assigned_to"]))
    audit(con, r["assigned_to"] or "system", "task.finish", str(task_id),
          {"ok": ok, "actual_usd": actual_usd})
    con.commit()


def queue(con: sqlite3.Connection, brand: str | None = None,
          status: str | None = None) -> list[sqlite3.Row]:
    q = ["SELECT * FROM tasks WHERE 1=1"]
    a: list[Any] = []
    if brand:
        q.append("AND brand=?")
        a.append(brand)
    if status:
        q.append("AND status=?")
        a.append(status)
    q.append("ORDER BY CASE status WHEN 'awaiting_approval' THEN 0 WHEN 'ready' THEN 1 "
             "WHEN 'running' THEN 2 ELSE 3 END, id")
    return list(con.execute(" ".join(q), a))


def main() -> None:
    ap = argparse.ArgumentParser(description="Control plane: tasks, budgets, approvals, audit.")
    ap.add_argument("command", choices=["init", "workers", "add-worker", "propose",
                                        "queue", "approve", "reject", "audit", "verify"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--name")
    ap.add_argument("--runtime", default="claude-code")
    ap.add_argument("--role", default="")
    ap.add_argument("--budget", type=float, default=5.0)
    ap.add_argument("--kind")
    ap.add_argument("--title")
    ap.add_argument("--assign")
    ap.add_argument("--estimate", type=float, default=0.0)
    ap.add_argument("--id", type=int)
    ap.add_argument("--why", default="")
    ap.add_argument("--actor", default=None)
    a = ap.parse_args()

    con = connect()
    actor = a.actor or getpass.getuser()

    if a.command == "init":
        add_worker(con, "claude", "claude-code", "implementer", 10.0, actor)
        add_worker(con, "codex", "codex-cli", "reviewer", 10.0, actor)
        add_worker(con, "verifier", "claude-code", "independent verifier", 5.0, actor)
        print("seeded 3 workers. `workers` to see them.")
        return

    if a.command == "add-worker":
        if not a.name:
            raise SystemExit("--name is required")
        add_worker(con, a.name, a.runtime, a.role, a.budget, actor)
        print(f"worker {a.name} ({a.runtime}) budget ${a.budget:.2f}")
        return

    if a.command == "workers":
        for w in con.execute("SELECT * FROM workers ORDER BY name"):
            left = w["budget_usd"] - w["spent_usd"]
            print(f"{w['name']:<12} {w['runtime']:<14} {w['role']:<22} "
                  f"${w['spent_usd']:.2f}/${w['budget_usd']:.2f} (${left:.2f} left)"
                  f"{'' if w['enabled'] else '  DISABLED'}")
        return

    if a.command == "propose":
        if not (a.kind and a.title):
            raise SystemExit("--kind and --title are required")
        tid = propose(con, Task(brand=a.brand, kind=a.kind, title=a.title,
                                assigned_to=a.assign, estimate_usd=a.estimate,
                                created_by=actor))
        r = con.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
        print(f"task {tid} created, status={r['status']}")
        if r["status"] == "awaiting_approval":
            print(f"  `{a.kind}` always needs a human. Approve with:")
            print(f"    uv run packages/orchestrator/control.py approve --id {tid}")
        return

    if a.command == "queue":
        rows = queue(con, a.brand)
        if not rows:
            print("queue is empty")
        for r in rows:
            flag = "!" if r["requires_human"] and r["status"] == "awaiting_approval" else " "
            print(f"[{r['id']:>3}]{flag} {r['status']:<18} {r['kind']:<16} "
                  f"{r['title'][:34]:<36} {r['assigned_to'] or '-':<10} "
                  f"est ${r['estimate_usd']:.2f}")
        return

    if a.command == "approve":
        if not a.id:
            raise SystemExit("--id is required")
        approve(con, a.id, actor)
        print(f"task {a.id} approved by {actor}; status=ready")
        return

    if a.command == "reject":
        if not a.id:
            raise SystemExit("--id is required")
        reject(con, a.id, actor, a.why or "no reason given")
        print(f"task {a.id} rejected")
        return

    if a.command == "audit":
        for r in con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 30"):
            print(f"{r['at'][:19]}  {r['actor']:<12} {r['action']:<16} "
                  f"{r['subject'] or '':<6} {(r['detail'] or '')[:70]}")
        return

    if a.command == "verify":
        ok, msg = verify_audit(con)
        print(("OK  " if ok else "BROKEN  ") + msg)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    try:
        main()
    except ControlError as e:
        raise SystemExit(f"error: {e}")
