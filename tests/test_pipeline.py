"""End-to-end tests for the studio.

Runs the whole pipeline against real repo data — real brand kits, real workflows, the real
corpus graph — with no API key, no GPU and no network.

What is asserted is deliberately weighted toward **refusals**. Most of this system's value
is in what it declines to do: publish an unapproved brief, validate an unreachable backend
as OK, derive a grammar from four samples, name a finding a dataset cannot support, promote
a skill into a protected area. A test suite that only checks happy paths would miss every
bug that has actually mattered here.

    uv run --with pytest --with pillow --with pyyaml -m pytest tests/ -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for pkg in ("brandkit", "compositor", "comfy-client", "image-router", "library",
            "strategy", "vision", "voice", "memory", "analytics", "publish", "ingest",
            "orchestrator"):
    sys.path.insert(0, str(REPO / "packages" / pkg))


# --------------------------------------------------------------- brand kit

def test_every_brand_loads():
    from brandkit import load_brand
    for key in ("ongea-pesa", "epalle"):
        b = load_brand(key)
        assert b.styles, f"{key} has no style grammars"
        assert b.logo_master.exists(), f"{key} logo master missing"


def test_calendar_style_families_all_resolve():
    """A calendar pointing at a nonexistent grammar must fail loudly, not silently."""
    from brandkit import load_brand
    b = load_brand("ongea-pesa")
    for item in b.calendar["items"]:
        assert item["style_family"] in b.styles


def test_style_grammars_forbid_text_and_marks():
    """The whole design rests on the model never rendering type or a logo."""
    from brandkit import load_brand
    for key in ("ongea-pesa", "epalle"):
        b = load_brand(key)
        for name, st in b.styles.items():
            neg = st["negative_prompt"].lower()
            assert "no text" in neg and "no logo" in neg, f"{key}/{name} allows text or marks"
            assert st["text_policy"].startswith("NONE"), f"{key}/{name} text_policy"


def test_request_refuses_ratio_a_grammar_does_not_declare():
    from brandkit import BrandError, build_request, load_brand
    b = load_brand("ongea-pesa")
    with pytest.raises(BrandError):
        build_request(b, style_key="crimson_monolith", ratio="16:9")


# --------------------------------------------------------------- routing

def test_carousels_and_reels_route_to_comfy():
    """Anything needing edit/identity/motion must not go to a hosted endpoint."""
    from brandkit import build_request, load_brand
    from router import choose
    b = load_brand("ongea-pesa")
    for item in b.calendar["items"]:
        if item["format"] in ("carousel", "reel"):
            plan = choose(build_request(b, item["id"]))
            assert plan.backend == "comfy", f"idea {item['id']} ({item['format']})"


def test_prices_are_contract_values_not_guesses():
    from pricing import quote
    assert quote("google/gemini-3-pro-image", "4k").usd == pytest.approx(0.24, abs=0.01)
    assert quote("openai/gpt-image-2", "4k", quality="high").usd == pytest.approx(0.73, abs=0.01)
    assert quote("made/up-model") is None, "unknown models must be UNKNOWN, never free"


# --------------------------------------------------------------- compositor

def test_composite_produces_master_with_manifest(tmp_path):
    from PIL import Image
    from brandkit import RATIO_PX, load_brand
    from compositor import composite

    b = load_brand("ongea-pesa")
    base = Image.new("RGB", (1200, 1500), (10, 10, 10))
    r = composite(base, b.spec, b.root,
                  {"headline": "SPEAK, SEND, DONE", "subhead": "Test",
                   "cta": "Get started", "attribution": "ONGEA PESA — BY NSAIT",
                   "disclosure": "AI-assisted imagery."},
                  "4:5", RATIO_PX["4:5"], tmp_path, "test-campaign")
    assert r.path.exists() and r.manifest_path.exists()
    assert Image.open(r.path).size == RATIO_PX["4:5"]
    assert r.contrast >= 4.5, "composited copy must clear WCAG AA"
    m = json.loads(r.manifest_path.read_text(encoding="utf-8"))
    assert len(m["sha256"]) == 64 and m["logo_master_sha256"]


# --------------------------------------------------------------- comfy client

def test_validation_is_three_state_not_boolean():
    """An unreachable backend must read UNVERIFIED, never OK. This was a real bug."""
    from client import ComfyClient
    v = ComfyClient("local", "http://127.0.0.1:59999").validate(
        "workflows/icekiub/Carousel_Pose_changer.json")
    assert v.state == "UNVERIFIED"
    assert v.ok is False, "unknown must not be truthy"


def test_node_count_counts_nodes_not_json_keys():
    from client import _count_nodes
    g = json.loads((REPO / "workflows/icekiub/KleinDataset_-_Icekiub_freelo.json")
                   .read_text(encoding="utf-8"))
    assert _count_nodes(g) == 21


def test_requirements_surface_the_gated_model():
    from client import requirements
    r = requirements("workflows/icekiub/Carousel_Pose_changer.json")
    assert any("klein-9b-kv" in m for m in r.model_files), \
        "the licence-gated model must be visible before a run is attempted"


# --------------------------------------------------------------- graph

def test_graph_answers_both_plan_gates():
    g = json.loads((REPO / "graph" / "graph.json").read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"]}
    kj = "node_pack:comfyui-kjnodes"
    assert kj in nodes
    dependents = {e["src"] for e in g["edges"]
                  if e["dst"] == kj and nodes[e["src"]]["kind"] == "workflow"}
    assert len(dependents) >= 30, "kjnodes should be the biggest dependency"
    # pack ids must be normalised: cnr_id and aux_id must not both exist
    labels = {n["label"] for n in g["nodes"] if n["kind"] == "node_pack"}
    assert not any("/" in l for l in labels), f"un-normalised pack ids: {labels}"


# --------------------------------------------------------------- strategy

def test_study_refuses_too_few_samples():
    from study import MIN_SAMPLES, derive
    g = derive([{"kind": "image", "aspect": "1:1", "mean_luma": 20, "saturation": 10,
                 "edge_density": 0.05, "palette": []}] * 4, "tiny")
    assert g.confidence == "insufficient" and not g.conventions


def test_plan_blocks_sensitive_briefs_and_ratio_mismatches():
    from datetime import date
    from brandkit import load_brand
    from plan import build
    b = load_brand("ongea-pesa")
    briefs = build(b, 30, date(2026, 9, 15))
    assert len(briefs) == 30
    assert any(x.status == "blocked_pending_approval" for x in briefs)
    for x in briefs:
        if x.format == "reel" and x.status == "ready":
            assert x.ratio == "9:16", "a ready reel must be 9:16"


def test_plan_cycles_ideas_rather_than_silently_shrinking():
    from datetime import date
    from brandkit import load_brand
    from plan import build
    b = load_brand("ongea-pesa")
    assert len(build(b, 180, date(2026, 3, 1))) == 180


def test_treatment_covers_the_whole_master():
    from brandkit import load_brand
    from treatment import build as build_treatment
    b = load_brand("epalle")
    t = build_treatment(b.spec, b.styles, "Test", None, 177.3, 24)
    covered = sum(s.duration_s for s in t.shots)
    assert abs(covered - 177.3) < 2.0, f"only {covered:.1f}s of a 177.3s master"
    assert any(s.kind == "hero" for s in t.shots)


# --------------------------------------------------------------- analytics

def test_underpowered_data_yields_no_per_grammar_claims():
    """The bug this prevents: a grammar seeded to UNDER-perform reported as +28%."""
    from analytics_helpers import fixture_posts  # noqa: PLC0415
    posts = fixture_posts(30)
    from learn import power_report, style_effects
    pw = power_report(posts, "saves")
    if not pw["can_support_claims"]:
        real = [f for f in style_effects(posts, "saves") if f.subject != "__suppressed__"]
        assert not real, "claims were made from data that cannot support them"


def test_well_powered_data_recovers_the_planted_signal():
    from analytics_helpers import fixture_posts  # noqa: PLC0415
    from learn import style_effects
    posts = fixture_posts(180)
    findings = {f.subject: f for f in style_effects(posts, "saves")
                if f.subject != "__suppressed__"}
    assert "kenyan_meme_original" in findings, "the strongest planted signal was missed"
    assert findings["kenyan_meme_original"].predicate == "performed_well_for"
    if "data_magazine_graphic" in findings:
        assert findings["data_magazine_graphic"].predicate == "underperformed_for", \
            "a grammar seeded to under-perform was reported as a winner"


# --------------------------------------------------------------- memory

def test_memory_is_bitemporal(tmp_path):
    from store import Fact, believed, connect, record, supersede
    con = connect(tmp_path / "m.sqlite3")
    old = record(con, Fact(brand="t", kind="learning", subject="a",
                           predicate="performed_well_for", valid_from="2026-07-01",
                           source="x", confidence=0.5, sample_size=10))
    supersede(con, old, Fact(brand="t", kind="learning", subject="b",
                             predicate="performed_well_for", valid_from="2026-07-30",
                             source="y", confidence=0.5, sample_size=10), on="2026-07-29")
    assert [r["subject"] for r in believed(con, "t", as_of="2026-07-15")] == ["a"]
    assert [r["subject"] for r in believed(con, "t", as_of="2026-08-15")] == ["b"]


def test_memory_refuses_secrets_and_overconfidence(tmp_path):
    from store import Fact, MemoryError_, connect, episode, record
    con = connect(tmp_path / "m.sqlite3")
    with pytest.raises(MemoryError_):
        episode(con, "t", "publish", {"api_key": "sk-live-123"})
    with pytest.raises(MemoryError_):
        record(con, Fact(brand="t", kind="learning", subject="x",
                         predicate="p", confidence=0.9, sample_size=1))


# --------------------------------------------------------------- curator

def test_curator_refuses_protected_areas_on_perfect_evidence():
    from skill_curator import Evidence, evaluate, is_protected
    e = Evidence(subject="publishing authorisation rules", wins=9, days=30, items=200,
                 contexts=5, lift_pct=80.0, brand_consistency=1.0, holdout_pass=1.0)
    assert evaluate(e).eligible, "the gates themselves should pass here"
    assert is_protected(e.subject), "but the protected check must still refuse"


def test_curator_treats_unmeasured_as_failed():
    from skill_curator import Evidence, evaluate
    e = Evidence(subject="x", wins=5, days=7, items=30, contexts=3, lift_pct=40.0)
    v = evaluate(e)
    assert not v.eligible and v.unmeasured


# --------------------------------------------------------------- publishing

def test_publisher_refuses_unapproved_briefs(tmp_path):
    from postiz import _drafts_from_plan
    plan = tmp_path / "p.json"
    plan.write_text(json.dumps([
        {"day": 1, "date": "2026-09-15", "title": "ok", "idea_id": 1, "status": "ready"},
        {"day": 2, "date": "2026-09-16", "title": "gated", "idea_id": 2,
         "status": "blocked_pending_approval"}]), encoding="utf-8")
    drafts = _drafts_from_plan(plan, "ongea-pesa", "instagram", "i1", tmp_path, None)
    assert [d.title for d in drafts] == ["ok"], "a gated brief reached the publisher"


def test_now_requires_explicit_confirmation():
    from postiz import Draft, PostizError, send
    d = Draft(brand="t", title="t", platform="instagram", integration_id="i",
              caption="c", media=[])
    with pytest.raises(PostizError, match="confirmed"):
        send([d], post_type="now", dry_run=False)


def test_whatsapp_blocks_without_confirmation():
    from whatsapp import StatusItem, send
    r = send([StatusItem(kind="text", caption="hi", brand="t")],
             dry_run=False, confirmed=False)
    assert r["status"] == "BLOCKED"


# --------------------------------------------------------------- voice

def test_voice_extracts_and_flags_ambiguity():
    from transcribe import extract
    b = extract("make me a carousel for ongeya pesa about matatu fare, in swahili, "
                "four by five, no orange teal grade")
    assert b.brand == "ongea-pesa" and b.format == "carousel" and b.ratio == "4:5"
    assert "sw" in b.languages
    assert any("confirm" in a for a in b.ambiguities), "a misheard brand must be flagged"
    assert any("orange teal" in c for c in b.constraints)


def test_voice_refuses_to_guess_a_vague_brief():
    from transcribe import extract
    b = extract("I want something for the launch")
    assert b.brand is None and b.format is None and len(b.ambiguities) >= 2


def test_captions_are_sized_from_the_frame():
    """Captions once rendered 5x too large because PlayRes defaulted to 384x288."""
    from mux import script_to_ass
    ass = script_to_ass("hello there", 4.0, 1080, 1920)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass


# --------------------------------------------------------------- orchestration

def test_risky_task_kinds_always_need_a_human(tmp_path):
    from control import Task, connect, propose
    con = connect(tmp_path / "c.sqlite3")
    for kind in ("publish", "skill_promote", "spend_increase", "whatsapp_status"):
        tid = propose(con, Task(brand="t", kind=kind, title=kind, assigned_to="w"))
        row = con.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
        assert row["status"] == "awaiting_approval", f"{kind} dispatched without a human"


def test_a_worker_cannot_approve_its_own_task(tmp_path):
    from control import ControlError, Task, connect, propose, approve
    con = connect(tmp_path / "c.sqlite3")
    tid = propose(con, Task(brand="t", kind="publish", title="x", assigned_to="claude"))
    with pytest.raises(ControlError, match="own task"):
        approve(con, tid, "claude")
    approve(con, tid, "human")          # a human still can


def test_budget_is_checked_before_work_starts(tmp_path):
    from control import ControlError, Task, add_worker, connect, propose, admit
    con = connect(tmp_path / "c.sqlite3")
    add_worker(con, "tiny", "local", "test", budget_usd=0.05)
    tid = propose(con, Task(brand="t", kind="plan", title="x",
                            assigned_to="tiny", estimate_usd=2.0))
    with pytest.raises(ControlError, match="BEFORE work starts"):
        admit(con, tid)


def test_unknown_task_kinds_are_refused(tmp_path):
    """An unclassified kind would default to whichever gate is convenient."""
    from control import ControlError, Task, connect, propose
    con = connect(tmp_path / "c.sqlite3")
    with pytest.raises(ControlError, match="unknown task kind"):
        propose(con, Task(brand="t", kind="exfiltrate", title="x"))


def test_audit_log_is_tamper_evident(tmp_path):
    from control import Task, connect, propose, verify_audit
    con = connect(tmp_path / "c.sqlite3")
    propose(con, Task(brand="t", kind="plan", title="one"))
    propose(con, Task(brand="t", kind="plan", title="two"))
    assert verify_audit(con)[0]
    con.execute("UPDATE audit SET action='task.tampered' WHERE id=1")
    con.commit()
    ok, msg = verify_audit(con)
    assert not ok and "row 1" in msg


def test_local_workers_run_an_allowlist_not_the_task_spec():
    """A task spec is data; data must not choose what executes."""
    from workers import Local, WorkerError
    with pytest.raises(WorkerError, match="allowlist"):
        Local().build({"kind": "rm -rf /", "spec": {}})


def test_deterministic_tasks_have_a_local_entrypoint():
    from workers import Local
    for kind in ("graph_rebuild", "plan", "analyse", "test"):
        assert kind in Local.ENTRYPOINTS


def test_absent_runtimes_report_missing_not_ready():
    from workers import REGISTRY
    ok, why = REGISTRY["hermes"].available()
    if not ok:
        assert why and "hermes" in why.lower()


def test_paperclip_approval_map_uses_real_vocabulary():
    from paperclip import APPROVAL_MAP, APPROVAL_TYPES
    assert set(APPROVAL_MAP.values()) <= APPROVAL_TYPES
