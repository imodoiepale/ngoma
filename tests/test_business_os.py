"""Business OS, creator links and workflow intake: the numbers and gates people will act on."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for pkg in ("strategy", "ingest"):
    sys.path.insert(0, str(REPO / "packages" / pkg))
sys.path.insert(0, str(REPO / "packages" / "library" / "tools"))

import business_os  # noqa: E402
import link_miner  # noqa: E402
import unit_economics as ue  # noqa: E402
import workflow_fetch  # noqa: E402
from register_workflow import NotAWorkflow, analyse  # noqa: E402


# ---- unit economics ---------------------------------------------------------------

def test_the_1000_images_anchor_is_reproduced_from_measured_inputs():
    pack = ue.social_manager_daily_pack(1000)
    assert ue.KLEIN_T2I_POD.basis == "measured"
    assert round(ue.KLEIN_T2I_POD.per_hour) == 444
    assert pack["fits_six_hours"] and 2.0 < pack["hours_per_day"] < 3.0
    # the GPU route must be visibly cheaper than hosted for volume, not assumed to be
    assert pack["gpu_cost_per_day"].usd < pack["hosted_cost_per_day"].usd


def test_every_rate_declares_its_basis():
    assert all(r.basis in ("measured", "contract", "assumed") for r in ue.GPU_RATES.values())


def test_mrr_range_rejects_disordered_scenarios():
    with pytest.raises(ValueError):
        ue.mrr_range(100, 10, (5, 3, 8))


# ---- ideas ------------------------------------------------------------------------

def test_exactly_fifty_ideas_with_every_field():
    doc = business_os.load()
    assert len(doc["ideas"]) == 50


def test_margins_include_people_time_and_fees():
    idea = {"id": "T", "family": "service", "buyer": "x", "offer": "y", "price_usd": 100,
            "clients": [1, 1, 1], "gpu_hours": 0, "api_usd": 0, "setup_usd": 0, "fixed_usd": 0}
    c = business_os.cost(idea)
    expected = business_os.LABOR_HOURS["service"] * business_os.LABOR_USD_PER_HOUR + 100 * business_os.FEE_RATE
    assert c.cost_per_client == pytest.approx(expected)
    assert c.base["margin"] < 1.0


def test_no_idea_is_loss_making_at_its_own_base_scenario():
    """A negative base margin means the price or the plan is wrong; fix the input, do not ship it."""
    doc = business_os.load()
    bad = [(r.idea["id"], r.base["margin"]) for r in business_os.costed_all(doc) if r.base["mrr"] and r.base["margin"] < 0]
    assert not bad, bad


def test_adult_ideas_cannot_drop_their_hard_gates(tmp_path):
    doc = business_os.load()
    for i in doc["ideas"]:
        if i["family"] == "adult":
            i["compliance"] = "platform rules"
    p = tmp_path / "ideas.yaml"
    import yaml
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(business_os.IdeaError, match="hard compliance gates"):
        business_os.load(p)


# ---- links ------------------------------------------------------------------------

@pytest.mark.parametrize("url,kind,paid", [
    ("https://www.skool.com/matrix-lab-6660/about", "skool", True),
    ("https://www.patreon.com/LoRAtech", "patreon", True),
    ("https://discord.gg/kUc76uk7HA", "discord", False),
    ("https://youtu.be/Bvpn3miGpw0", "youtube", False),
    ("https://huggingface.co/krea/Krea-2-Raw", "huggingface", False),
    ("https://huggingface.co/Comfy-Org/x/resolve/main/model.safetensors", "model_file", False),
    ("https://huggingface.co/datasets/malcolmrey/workflows/blob/main/H3/workflow_minimaxh3_refmod.json", "workflow_json", False),
    ("https://github.com/JsonMatrixLab/matrix-power-nodes", "github_repo", False),
    ("https://runpod.io?ref=jc6190fx", "runpod_referral", False),
    ("https://try.elevenlabs.io/ckic81ihjagm?via=x", "affiliate", False),
])
def test_links_are_classified_by_host_not_by_substring(url, kind, paid):
    assert link_miner.classify(url) == (kind, paid)


# ---- workflow intake --------------------------------------------------------------

def test_fetch_refuses_hosts_outside_the_allowlist():
    with pytest.raises(workflow_fetch.FetchRefused):
        workflow_fetch.direct_url("https://evil.example.com/workflow.json")
    with pytest.raises(workflow_fetch.FetchRefused):
        workflow_fetch.direct_url("http://huggingface.co/x/blob/main/w.json")
    with pytest.raises(workflow_fetch.FetchRefused):
        workflow_fetch.direct_url("https://github.com/a/b/blob/main/setup.exe")


def test_fetch_rewrites_blob_pages_to_raw_bytes():
    assert workflow_fetch.direct_url("https://github.com/a/b/blob/main/w.json") == \
        "https://raw.githubusercontent.com/a/b/main/w.json"
    assert workflow_fetch.direct_url("https://huggingface.co/datasets/m/w/blob/main/H3/w.json") == \
        "https://huggingface.co/datasets/m/w/resolve/main/H3/w.json"


def test_a_json_file_that_is_not_a_graph_is_rejected_not_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow_fetch, "DEST", tmp_path)

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    row = {"url": "https://github.com/a/b/blob/main/w.json", "channel": "c", "video_id": "v"}
    with pytest.raises(NotAWorkflow):
        workflow_fetch.fetch_one(row, opener=lambda req, timeout: Resp(json.dumps({"hello": 1}).encode()))
    assert not any(tmp_path.rglob("*.json"))


def test_attribution_never_guesses_a_pack():
    graph = {"nodes": [
        {"type": "H3RefModCreateFromFolder", "properties": {}},
        {"type": "VAELoader", "properties": {}},
        {"type": "SomeMysteryNode", "properties": {}},
        {"type": "PathchSageAttentionKJ", "properties": {"cnr_id": "comfyui-kjnodes"}},
    ]}
    a = analyse(json.dumps(graph).encode())
    assert a["node_packs"] == ["FranckyB/ComfyUI-H3RefModPicker", "comfy-core", "comfyui-kjnodes"]
    assert a["unattributed_node_types"] == ["SomeMysteryNode"]
