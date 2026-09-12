"""Paperclip adapter — mirror the local control plane into a real company control plane.

Paperclip is real: `paperclipai/paperclip`, MIT, TypeScript, embedded Postgres, Docker
quickstart. Verified 2026-09-12 against the GitHub API and the repo's own Drizzle schema
and docs.

> **Disambiguation.** Not `thoughtbot/paperclip` (the archived Ruby attachment gem), and
> not npm `paperclip` (which is `@paperclip-ui`, a visual web tool). The npm package here
> is **`paperclipai`**.

## Why both this and `control.py`

They are not competing; they are different scopes, and keeping them apart is the point.

`control.py` is **local and always available** — SQLite, no daemon, no Docker, no network.
It gates every task this studio runs, and it works on a laptop on a plane. Paperclip is a
**company** control plane: an org chart of agents with `reportsTo`, monthly budgets with
`hardStopEnabled`, a typed approval workflow, and an activity log with human attribution.
It is the better answer once more than one person is involved.

So: `control.py` stays authoritative for what this repo executes. This module *mirrors*
goals, tasks and approvals into Paperclip when it is deployed, so a human supervising a
team sees them where the rest of the company lives. Mirroring one way keeps a single
source of truth; two authoritative task stores is how they diverge.

Its data model maps onto ours almost exactly, which is a good sign for both:

    ours              Paperclip
    ----              ---------
    goals             goals            (hierarchical, parentId)
    tasks             issues           (+ issue_approvals, issue_comments)
    workers           agents           (reportsTo, budgetMonthlyCents, adapterType)
    budget check      budget_policies  (hardStopEnabled, warnPercent)
    approvals         approvals        (APPROVAL_TYPES enum)
    audit             activity_log     (actorType, responsibleUserId)

Notably, Paperclip ships **`hermes_local` and `hermes_gateway` adapter types** built in, so
a Hermes worker registered here can be the same Hermes agent Paperclip drives.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_URL = "http://localhost:3100"

# Paperclip's own approval vocabulary, from packages/shared/src/constants.ts.
APPROVAL_TYPES = {"hire_agent", "approve_ceo_strategy",
                  "budget_override_required", "request_board_approval"}

# Which of our task kinds map to a Paperclip approval, where one exists.
APPROVAL_MAP = {
    "spend_increase": "budget_override_required",
    "skill_promote": "request_board_approval",
    "brand_change": "request_board_approval",
    "publish": "request_board_approval",
    "publish_now": "request_board_approval",
    "whatsapp_status": "request_board_approval",
}


class PaperclipError(RuntimeError):
    pass


def base_url() -> str:
    return os.environ.get("PAPERCLIP_URL", DEFAULT_URL).rstrip("/")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "User-Agent": "epalle-studio/1.0"}
    key = os.environ.get("PAPERCLIP_API_KEY")
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _req(method: str, path: str, body: Any = None, timeout: int = 60) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base_url()}/api{path}", data=data,
                                 headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                # Something answered, but it is not Paperclip. A port collision is the
                # common cause and it should read as one, not as a JSON stack trace.
                head = raw[:120].decode("utf-8", "replace").replace(chr(10), " ")
                raise PaperclipError(
                    f"{base_url()} answered {method} {path} with non-JSON, so it is "
                    f"probably not Paperclip - check what else is on that port. "
                    f"First bytes: {head!r}") from e
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise PaperclipError(
                f"Paperclip rejected the request ({e.code}). In `authenticated` mode the "
                f"public API needs an agent key; in `local_trusted` mode auth is skipped. "
                f"Company scoping is enforced server-side, so a 403 can also mean the key "
                f"belongs to a different company. Server said: {detail}") from e
        raise PaperclipError(f"{method} {path} -> {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise PaperclipError(
            f"could not reach Paperclip at {base_url()}: {e.reason}. Start it with "
            f"`npx paperclipai run` (or the Docker quickstart) — see infra/paperclip/.") from e


def reachable() -> tuple[bool, str]:
    try:
        _req("GET", "/agents")
        return True, base_url()
    except PaperclipError as e:
        return False, str(e)[:160]


def agents() -> list[dict[str, Any]]:
    r = _req("GET", "/agents")
    return r if isinstance(r, list) else r.get("agents", r.get("data", []))


def mirror(brand: str, dry_run: bool = True, limit: int = 25) -> dict[str, Any]:
    """Push local tasks into Paperclip as issues. One-way, by design."""
    from control import connect, queue  # noqa: PLC0415

    con = connect()
    rows = queue(con, brand)[:limit]
    payloads = []
    for r in rows:
        approval = APPROVAL_MAP.get(r["kind"])
        payloads.append({
            "title": r["title"],
            "description": (
                f"Mirrored from the studio control plane (task {r['id']}).\n\n"
                f"kind: {r['kind']}\nbrand: {r['brand']}\n"
                f"estimate: ${r['estimate_usd']:.2f}\nstatus here: {r['status']}\n\n"
                f"The studio remains authoritative for execution; this issue exists so "
                f"supervision happens where the rest of the company lives."),
            "labels": [brand, r["kind"]],
            "external_ref": f"studio:{r['id']}",
            "requires_approval": bool(r["requires_human"]),
            "approval_type": approval,
        })
    if dry_run:
        return {"status": "DRY_RUN", "would_create": len(payloads),
                "sample": payloads[:2], "url": base_url()}

    ok, why = reachable()
    if not ok:
        raise PaperclipError(why)
    created, failed = [], []
    for p in payloads:
        try:
            res = _req("POST", "/issues", p)
            created.append(res.get("id") or p["external_ref"])
        except PaperclipError as e:
            failed.append({"title": p["title"], "error": str(e)[:200]})
    return {"status": "DONE", "created": len(created), "failed": failed}


def status() -> dict[str, Any]:
    from control import connect, queue, verify_audit  # noqa: PLC0415

    con: sqlite3.Connection = connect()
    up, why = reachable()
    chain_ok, chain_msg = verify_audit(con)
    return {
        "local_control_plane": {
            "tasks": len(queue(con)),
            "awaiting_approval": len(queue(con, status="awaiting_approval")),
            "audit_chain": chain_msg,
            "audit_intact": chain_ok,
        },
        "paperclip": {"url": base_url(), "reachable": up, "detail": why if not up else "ok"},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Mirror the local control plane into Paperclip.")
    ap.add_argument("command", choices=["status", "agents", "mirror", "setup"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    if a.command == "status":
        print(json.dumps(status(), indent=2))
        return

    if a.command == "agents":
        for ag in agents():
            print(f"{str(ag.get('id'))[:10]:<12} {ag.get('role', '?'):<16} "
                  f"{ag.get('name', '?'):<20} {ag.get('status', '?')}")
        return

    if a.command == "mirror":
        res = mirror(a.brand, dry_run=not a.live, limit=a.limit)
        print(json.dumps(res, indent=2)[:1800])
        if res.get("status") == "DRY_RUN":
            print("\n(dry run — pass --live to create issues in Paperclip)")
        return

    if a.command == "setup":
        print("""Paperclip — company control plane (optional)

  github.com/paperclipai/paperclip · MIT · TypeScript · Node 24.11+, pnpm 9+
  npm package is `paperclipai` (NOT `paperclip`, which is an unrelated UI tool)

Quickstart — one container, embedded Postgres, no external database:

  npx paperclipai onboard --yes
  npx paperclipai run                      # http://localhost:3100

Or Docker: docker/docker-compose.quickstart.yml. Persistent volume at /paperclip.

Required environment:
  BETTER_AUTH_SECRET=$(openssl rand -hex 32)
  plus at least one LLM provider key
  PAPERCLIP_DEPLOYMENT_MODE=authenticated | local_trusted
  PAPERCLIP_DEPLOYMENT_EXPOSURE=private | public

Connect this studio:
  export PAPERCLIP_URL=http://localhost:3100
  export PAPERCLIP_API_KEY=<agent key from POST /api/agents/{id}/keys>
  uv run packages/orchestrator/paperclip.py status

Hermes: Paperclip ships `hermes_local` and `hermes_gateway` adapter types built in
(package @paperclipai/hermes-paperclip-adapter). So a Hermes worker registered in this
studio can be the same agent Paperclip drives. Set the adapter on the Paperclip agent, not
here.

Scope, deliberately: the studio's control.py stays authoritative for what executes.
Paperclip receives a one-way mirror for supervision. Two authoritative task stores is how
they diverge.""")
        return


if __name__ == "__main__":
    try:
        main()
    except PaperclipError as e:
        raise SystemExit(f"error: {e}")
