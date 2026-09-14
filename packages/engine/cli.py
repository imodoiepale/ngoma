"""Talk to the director engine from the command line.

    plan   --client C --brief brief.json [--save]        a brief becomes a workflow
    say    --client C --session S --text "..."           one utterance grows the workflow
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
