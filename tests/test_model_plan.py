"""The pod download plan covers every model the repo's workflows ask for, honestly bucketed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "infra" / "runpod"))
import plan_models as pm  # noqa: E402

PLAN = json.loads(pm.PLAN.read_text(encoding="utf-8"))
BUCKETS = ("resolved", "auto_download", "creator_private", "manual", "unresolved")


def test_every_model_a_manifest_workflow_names_is_in_exactly_one_bucket():
    placed: dict[str, list[str]] = {}
    for b in BUCKETS:
        for r in PLAN[b]:
            placed.setdefault(r["file"], []).append(b)
    need = pm.required()
    missing = sorted(set(need) - set(placed))
    assert not missing, f"re-run infra/runpod/plan_models.py; not planned: {missing[:10]}"
    twice = {f: b for f, b in placed.items() if len(b) > 1}
    assert not twice, twice


def test_resolved_entries_say_where_and_why():
    for r in PLAN["resolved"]:
        assert r["repo"].count("/") == 1 and r["repo_path"] and r["folder"], r
        assert r.get("evidence"), r["file"]


def test_a_creators_private_lora_is_never_substituted():
    resolved = {r["file"] for r in PLAN["resolved"]}
    assert not resolved & pm.CREATOR_PRIVATE
    assert pm.PRIVATE_NAME.search("Lora_lora_000000500.safetensors")
    assert not pm.PRIVATE_NAME.search("flux-2-klein-9b-fp8.safetensors")


def test_hf_url_harvest_reads_the_file_path_not_trailing_prose():
    text = "Model: https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/blob/main/flux-2-klein-9b-fp8.safetensorsif no access"
    assert pm.HF_URL.findall(text) == []  # glued prose is ambiguous; never guess a filename
    ok = "vae: https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/vae/flux2-vae.safetensors\n"
    assert pm.HF_URL.findall(ok) == [("Comfy-Org/flux2-klein-9B", "main", "split_files/vae/flux2-vae.safetensors")]


def test_bought_skool_workflows_have_their_models_planned():
    skool = {w["canonical"] for w in json.loads(pm.MANIFEST.read_text(encoding="utf-8"))["workflows"]
             if any(s.startswith("skool:") for s in w.get("sources", []))}
    used = {u for b in BUCKETS for r in PLAN[b] for u in r.get("used_by", [])}
    need = pm.required()
    wanted = {u for rec in need.values() for u in rec["used_by"]} & skool
    assert wanted and wanted <= used
