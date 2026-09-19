"""Talk to the director engine from the command line.

    plan   --client C --brief brief.json [--save]        a brief becomes a workflow
    say    --client C --session S --text "..."           one utterance grows the workflow
    describe --client C --text "..." [--session S]       a sentence becomes (or extends) a workflow
    run    --client C --workflow W --stage S [--mode M]   run a stage under its mode
    possibilities                                        what each kind of reference can drive
    ports-check                                          every engine step has a port map

Nothing here spends or publishes without the run mode and the control plane allowing it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "packages" / "strategy"))


def cmd_plan(a: argparse.Namespace) -> int:
    import director
    import workflow_author as wa
    from brief import EngineBrief
    brief = EngineBrief.from_dict(json.loads(Path(a.brief).read_text(encoding="utf-8")))
    if a.client:
        brief.client = a.client
    wf = director.plan(brief)
    if a.json:
        print(json.dumps(wf, indent=2, ensure_ascii=False))
        return 0
    dest = wa.save(wf)
    print(f"wrote {dest.relative_to(REPO)}: {len(wf['stages'])} stages, {len(wf['nodes'])} nodes, "
          f"{len(wf['edges'])} links, {len(wf['gaps'])} gap(s)")
    for g in wf["gaps"]:
        print(f"  gap {g['node']}: {g['reason']}")
    return 0


def cmd_say(a: argparse.Namespace) -> int:
    import session
    out = session.say(a.client, a.session, a.text, workflow_id=a.workflow)
    print(json.dumps(out, indent=2, ensure_ascii=False) if a.json else out["reply"])
    return 0


def cmd_describe(a: argparse.Namespace) -> int:
    """The describe bar's contract; see session.describe. A refused brief (a person's name,
    an unknown client, nothing to add) is a JSON `error` and exit code 2, never a traceback."""
    import session
    answers: dict[str, str] = {}
    for kv in a.answer or []:
        if "=" not in kv:
            print(json.dumps({"error": f"--answer wants key=value, got {kv!r}", "refused": False}), file=sys.stdout)
            return 2
        k, v = kv.split("=", 1)
        answers[k.strip()] = v.strip()
    try:
        out = session.describe(a.client, a.text, session_id=a.session, workflow_id=a.workflow, mode=a.mode, answers=answers)
    except session.DescribeError as e:
        err = {"error": str(e), "refused": "names a person" in str(e), "route": None, "id": None,
               "questions": [], "continuations": [], "plan": None, "reply": str(e)}
        print(json.dumps(err, ensure_ascii=False) if a.json else f"refused: {e}")
        return 2
    except Exception as e:  # an unknown client, a validation failure: still a clean message
        err = {"error": f"{type(e).__name__}: {e}", "refused": False, "route": None, "id": None,
               "questions": [], "continuations": [], "plan": None, "reply": str(e)}
        print(json.dumps(err, ensure_ascii=False) if a.json else f"error: {e}")
        return 1
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0
    print(out["reply"])
    for s in out["plan"]["steps"]:
        flag = " (each)" if s["each"] else ""
        params = ", ".join(f"{k}={v}" for k, v in s["params"].items() if v not in (None, "", {}))
        print(f"  {s['id']:<6} {s['step']:<24} {s['status']:<12}{flag}{'  ' + params if params else ''}")
    for q in out["questions"]:
        print(f"  ? {q['key']}: {q['prompt']} {q.get('options') or ''}")
    for c in out["continuations"]:
        print(f"  + could continue with {c['step']}{'@each' if c.get('each') else ''} {c.get('params') or ''} est ${c['estimate']['usd']}")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    import runner
    out = runner.run_stage(a.client, a.workflow, a.stage, mode=a.mode, backend=a.backend, approve_as=a.approve_as)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok", True) else 1


def cmd_possibilities(a: argparse.Namespace) -> int:
    import references
    print(references.render_possibilities())
    return 0


def cmd_ports_check(a: argparse.Namespace) -> int:
    import ports
    import workflow_author as wa
    problems = ports.validate_port_maps(wa.load_catalog())
    for p in problems:
        print(f"  {p}")
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="flags by command:\n"
                                        "  plan  --brief FILE [--client C] [--json]\n"
                                        "  say   --client C --session S --text T [--workflow W] [--json]\n"
                                        "  describe --client C --text T [--session S] [--workflow W] [--mode plan|create|direct] [--answer k=v] [--json]\n"
                                        "  run   --client C --workflow W --stage S [--mode M] [--backend B] [--approve-as NAME]")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="a brief file becomes a workflow")
    p.add_argument("--brief", required=True, help="path to an EngineBrief JSON")
    p.add_argument("--client")
    p.add_argument("--json", action="store_true", help="print instead of saving")
    p.set_defaults(fn=cmd_plan)
    s = sub.add_parser("say", help="one utterance grows a session's workflow")
    s.add_argument("--client", required=True)
    s.add_argument("--session", required=True, help="session id; created if new")
    s.add_argument("--workflow", help="workflow id to attach a new session to")
    s.add_argument("--text", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_say)
    d = sub.add_parser("describe", help="a sentence becomes a workflow, or extends one")
    d.add_argument("--client", required=True, help="workspace id (a folder in brands/ with brand.yaml)")
    d.add_argument("--text", required=True, help="what to make, in plain words; or `carousel@each slides=10`")
    d.add_argument("--session", help="session id; a second describe with the same id extends the workflow")
    d.add_argument("--workflow", help="workflow id to extend")
    d.add_argument("--mode", default="create", choices=["plan", "create", "direct"], help="plan writes nothing; direct forces the director")
    d.add_argument("--answer", action="append", metavar="KEY=VALUE", help="answer a question: collection=red-dress, slides=10, persona=..., kind=carousel")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=cmd_describe)
    r = sub.add_parser("run", help="run one stage of a workflow under its mode")
    r.add_argument("--client", required=True)
    r.add_argument("--workflow", required=True)
    r.add_argument("--stage", required=True, help="stage id, or `next`")
    r.add_argument("--mode", choices=["dry-run", "stage-approval", "auto"], help="override the workflow's run_mode")
    r.add_argument("--backend", default="pod", choices=["local", "pod", "serverless"])
    r.add_argument("--approve-as", help="a human name approving this stage's task")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("possibilities", help="what each kind of reference can drive").set_defaults(fn=cmd_possibilities)
    sub.add_parser("ports-check", help="every engine step has a port map").set_defaults(fn=cmd_ports_check)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
