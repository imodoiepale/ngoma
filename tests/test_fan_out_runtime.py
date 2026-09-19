"""The fan-out runtime: a node marked `each` runs once per item, with per-item seeds, an
`items/<i>/` layout, a `group` per source item, `partial` when some items fail, a `max_items`
cap, a cost that multiplies by items (and slides), a rights gate on consent steps, and an export
that lands `posts/<group>/slide-<n>` so one folder is one post. docs/engine/BATCHES.md
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
sys.path.insert(0, str(REPO / "packages" / "orchestrator"))
import cost  # noqa: E402
import edit  # noqa: E402
import runner  # noqa: E402
import workflow_author as wa  # noqa: E402

TEMPLATE = REPO / "brands" / "_templates" / "workflows" / "batch-character-to-carousels.studio.json"
FIXTURE = REPO / "brands" / "epalle" / "references" / "red-dress"
CAT = wa.load_catalog()


class FakeComfy:
    """Pretends to be ComfyUI. Records submissions and uploads; `fail_pids` stay in error."""
    calls: list[dict] = []
    uploads: list[str] = []
    fail_pids: set[str] = set()
    outcome = "COMPLETED"

    def __init__(self, backend="pod"):
        self.backend, self.base_url = backend, "http://fake"

    def submit(self, graph, workflow_name=None, dry_run=True):
        assert not dry_run
        FakeComfy.calls.append({"name": workflow_name, "graph": graph})
        return {"prompt_id": f"p{len(FakeComfy.calls)}"}

    def upload(self, path, subfolder="studio", overwrite=True):
        FakeComfy.uploads.append(Path(path).name)
        return f"{subfolder}/{Path(path).name}"

    def wait(self, pid, **_):
        if pid in FakeComfy.fail_pids or FakeComfy.outcome != "COMPLETED":
            return {"status": "ERROR" if pid in FakeComfy.fail_pids else FakeComfy.outcome, "detail": "boom"}
        return {"status": "COMPLETED", "outputs": [{"filename": f"{pid}.png", "subfolder": "", "type": "output"}]}


def _collection(folder: Path, n: int, **meta) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (folder / f"look-{i}.png").write_bytes(b"\x89PNG stub " + bytes([i]))
    doc = {"name": folder.name, "use": "data", "rights": "owned", "kind": "image", "consent": False, **meta}
    (folder / "collection.json").write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "brands"
    (root / "zz-test").mkdir(parents=True)
    (root / "zz-test" / "brand.yaml").write_text("name: ZZ\npalette:\n  measured: {ground: '#0A0A0A', surface: '#FEFEFE', accent: '#22C55E', hairline: '#262626'}\n"
                                                 "logo: {master: assets/logo.png, min_width_pct: 12}\n", encoding="utf-8")
    (root / "zz-test" / "assets").mkdir()
    (root / "zz-test" / "assets" / "logo.png").write_bytes(b"\x89PNG logo")
    shutil.copytree(FIXTURE, root / "zz-test" / "references" / "red-dress")
    _collection(root / "zz-test" / "references" / "persona", 1, notes=["fictional persona"])
    monkeypatch.setattr(wa, "BRANDS", root)
    monkeypatch.setattr(runner, "BRANDS", root)
    monkeypatch.setattr(cost, "budget_usd", lambda: 50.0)

    def fetch(c, o, dest):
        dest.mkdir(parents=True, exist_ok=True)
        p = dest / o["filename"]
        p.write_bytes(b"\x89PNG out " + o["filename"].encode())
        return str(p.relative_to(root.parent)).replace("\\", "/"), "0" * 64
    monkeypatch.setattr(runner, "_fetch", fetch)
    FakeComfy.calls, FakeComfy.uploads, FakeComfy.fail_pids, FakeComfy.outcome = [], [], set(), "COMPLETED"

    wf = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    wf["client"] = "zz-test"
    for n in wf["nodes"]:
        if n["id"] == "refs.batch":
            n["data"]["params"]["folder"] = "brands/zz-test/references/red-dress"
        if n["id"] == "refs.persona":
            n["data"]["params"]["folder"] = "brands/zz-test/references/persona"
    wa.save(wf)
    return {"client": "zz-test", "wf": wf, "root": root, "db": tmp_path / "control.sqlite3", "tmp": tmp_path}


def _node(wf, nid):
    return next(n for n in wf["nodes"] if n["id"] == nid)


def _manifests(world, node_id):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((world["root"] / "zz-test" / "runs" / world["wf"]["id"] / node_id).rglob("manifest.json"))]


def _run(world, stage, **kw):
    kw.setdefault("mode", "dry-run")
    return runner.run_stage(world["client"], world["wf"]["id"], stage, db=world["db"], comfy_factory=FakeComfy,
                            wf=world["wf"], save=False, **kw)


def _collection_meta(world, name, **changes):
    cj = world["root"] / "zz-test" / "references" / name / "collection.json"
    doc = json.loads(cj.read_text(encoding="utf-8-sig"))
    doc.update(changes)
    cj.write_text(json.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------- the template and a dry run

def test_the_batch_template_validates_and_fans_out_twice():
    wf = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert wa.validate(wf) == []
    each = [n["kind"] for n in wf["nodes"] if wa.is_each(n)]
    assert each == ["klein-headswap", "carousel"]
    assert wf["consent_required"] and _node(wf, "carousels.carousel")["data"]["params"]["slides"] == 10


def test_dry_run_over_the_fixture_writes_three_items_and_three_posts(world):
    out = _run(world, "next")
    assert out["stage"] == "swap" and out["ok"], out
    swap = out["results"][0]
    assert swap["each"] and swap["items"] == 3 and swap["groups"] == ["0", "1", "2"]
    assert out["cost_estimate"]["items"] == 3 and out["cost_estimate"]["basis"] == "assumed"
    m = _manifests(world, "swap.character-swap")[-1]
    assert m["status"] == "dry-run" and m["each"] and len(m["items"]) == 3 and m["item_count"] == 3
    assert m["cost_estimate"]["items"] == 3 and m["cost_estimate"]["gpu_seconds"] == 3 * 12
    assert [it["group"] for it in m["items"]] == ["0", "1", "2"]
    assert all(it["input"].startswith("brands/zz-test/references/red-dress/") for it in m["items"])
    assert m["bindings"]["face"] == "brands/zz-test/references/persona/look-0.png"   # binds once for every item
    assert m["layout"] == "items/<index>/" and m["workflow"] == world["wf"]["id"]
    assert m["comfy_workflow"].endswith("I2I_no_lora_faceswap_subs.json")
    assert FakeComfy.calls == []

    out = _run(world, "next")
    assert out["stage"] == "carousels" and out["ok"]
    car = _manifests(world, "carousels.carousel")[-1]
    assert len(car["items"]) == 3 and [it["group"] for it in car["items"]] == ["0", "1", "2"]
    assert car["items"][1]["input"] == "<swap.character-swap#1>"
    assert car["cost_estimate"] == {**car["cost_estimate"], "items": 3, "slides": 10, "per": "slide", "gpu_seconds": 3 * 10 * 10.0}
    assert len(car["bindings"]["prompt"].splitlines()) == 10

    out = _run(world, "next")
    assert out["stage"] == "finish" and out["ok"]
    by_kind = {r["kind"]: r for r in out["results"]}
    assert "3 post" in by_kind["compositor"]["note"]
    assert "posts/<group>/" in by_kind["export"]["note"] and "groups 0, 1, 2" in by_kind["export"]["note"]
    assert _run(world, "next")["stage"] is None


def test_per_item_seeds_are_base_plus_index_times_variants(world):
    node = _node(world["wf"], "swap.character-swap")
    node["data"]["seed"] = 1000
    node["data"]["variant_count"] = 2
    _run(world, "swap")
    m = _manifests(world, "swap.character-swap")[-1]
    assert [it["seeds"] for it in m["items"]] == [[1000, 1001], [1002, 1003], [1004, 1005]]
    assert m["cost_estimate"]["gpu_seconds"] == 3 * 2 * 12


def test_more_items_than_max_items_blocks_with_a_clear_note(world, monkeypatch):
    monkeypatch.setattr(cost, "max_items", lambda: 2)
    out = _run(world, "swap")
    assert not out["ok"] and out["results"][0]["status"] == "blocked"
    assert "max_items is 2" in out["results"][0]["note"] and "engine.yaml" in out["results"][0]["note"]


def test_max_items_comes_from_engine_yaml():
    assert cost.config()["max_items"] == 100 and cost.max_items() == 100


# ---------------------------------------------------------------- the rights gate

def test_rights_unclear_is_refused_with_the_rights_message(world):
    _collection_meta(world, "red-dress", rights="unclear")
    out = _run(world, "swap")
    r = out["results"][0]
    assert not out["ok"] and r["status"] == "blocked"
    assert "rights gate" in r["note"] and "rights: unclear" in r["note"] and "owned, licensed or fictional" in r["note"]
    assert _manifests(world, "swap.character-swap")[-1]["reason"] == "rights"
    assert FakeComfy.calls == []


def test_a_real_person_without_a_release_is_a_hard_refusal_and_a_release_lets_it_through(world):
    _collection_meta(world, "persona", real_person=True, consent=False)
    r = _run(world, "swap")["results"][0]
    assert r["status"] == "blocked" and "real person without a written release" in r["note"] and "consent: true" in r["note"]
    _collection_meta(world, "persona", real_person=True, consent=True, release="releases/persona.pdf")
    assert _run(world, "swap")["results"][0]["status"] == "dry-run"


def test_a_study_collection_never_feeds_a_model(world):
    _collection_meta(world, "red-dress", use="study")
    r = _run(world, "swap")["results"][0]
    assert r["status"] == "blocked" and "never feed a model" in r["note"]


def test_no_collection_json_warns_a_dry_run_and_blocks_a_live_run(world):
    (world["root"] / "zz-test" / "references" / "persona" / "collection.json").unlink()
    r = _run(world, "swap")["results"][0]
    assert r["status"] == "dry-run"
    assert "no collection.json" in _manifests(world, "swap.character-swap")[-1]["rights_warning"]
    out = _run(world, "swap", mode="stage-approval", approve_as="human")
    assert not out["ok"] and out["results"][0]["status"] == "blocked" and "no collection.json" in out["results"][0]["note"]
    assert FakeComfy.calls == []


def test_the_gate_only_watches_consent_steps():
    spec = CAT["by_kind"]["carousel"]
    assert not spec.get("consent")
    assert runner.rights_gate({"nodes": [], "edges": []}, {"id": "x", "kind": "carousel", "data": {}}, spec, "auto") == ("", "")
    for kind in ("klein-headswap", "klein-i2i", "faceswap"):
        assert CAT["by_kind"][kind].get("consent"), kind


def test_declared_rights_vocabulary():
    assert runner.declared_rights("c", {"use": "data", "rights": "owned"}) == ""
    assert runner.declared_rights("c", {"use": "data", "rights": "licensed"}) == ""
    assert runner.declared_rights("c", {"use": "data", "rights": "fictional"}) == ""
    assert runner.declared_rights("c", {"use": "data", "rights": "unclear", "fictional": True}) == ""
    assert "rights: unclear" in runner.declared_rights("c", {"use": "data", "rights": "unclear"})
    assert "inspiration collection" in runner.declared_rights("c", {"use": "inspiration", "rights": "owned"})
    assert "real person" in runner.declared_rights("c", {"rights": "owned", "subject": "real-person"})
    assert runner.declared_rights("c", {"rights": "owned", "subject": "real-person", "consent": True}) == ""


# ---------------------------------------------------------------- live runs against FakeComfy

def _live(world, stage):
    return _run(world, stage, mode="stage-approval", approve_as="human")


def test_a_live_fan_out_submits_once_per_item_with_its_own_seed_and_uploads_the_face_once(world):
    _node(world["wf"], "swap.character-swap")["data"]["seed"] = 500
    out = _live(world, "swap")
    assert out["ok"], out
    assert len(FakeComfy.calls) == 3
    assert FakeComfy.uploads == ["look-0.png", "look-a.png", "look-b.png", "look-c.png"]   # persona face once, then each item
    m = _manifests(world, "swap.character-swap")[-1]
    assert m["status"] == "completed" and m["failed"] == [] and len(m["files"]) == 3
    assert [it["status"] for it in m["items"]] == ["completed"] * 3
    assert [it["seeds"] for it in m["items"]] == [[500], [501], [502]]
    for it in m["items"]:
        assert it["files"] and all(f"/items/{it['index']}/" in f for f in it["files"])
        assert it["prompt_ids"] and "gpu_seconds_actual" in it
    assert m["groups"] == ["0", "1", "2"]
    # the seed each ComfyUI graph received is the item's seed
    seeds = [{str(n["id"]): n for n in c["graph"]["nodes"]}["31"]["widgets_values"][0] for c in FakeComfy.calls]
    assert seeds == [500, 501, 502]


def test_some_items_failing_makes_the_node_partial_and_passes_on_the_rest(world):
    FakeComfy.fail_pids = {"p2"}
    out = _live(world, "swap")
    r = out["results"][0]
    assert not out["ok"] and r["status"] == "partial" and r["failed"] == [1]
    m = _manifests(world, "swap.character-swap")[-1]
    assert [it["status"] for it in m["items"]] == ["completed", "error", "completed"]
    assert len(m["files"]) == 2 and m["groups"] == ["0", "2"]
    assert "item 1" in m["detail"]
    # downstream sees only the completed items, with their groups kept
    items = runner.upstream_items(world["wf"], _node(world["wf"], "carousels.carousel"))["image"]
    assert [it["group"] for it in items] == ["0", "2"]
    car = _run(world, "carousels")["results"][0]
    assert car["items"] == 2 and car["groups"] == ["0", "2"]


def test_three_failures_in_a_row_stop_the_batch_before_spending_more(world):
    for i in range(3, 6):
        (world["root"] / "zz-test" / "references" / "red-dress" / f"extra-{i}.png").write_bytes(b"\x89PNG")
    FakeComfy.fail_pids = {"p1", "p2", "p3", "p4", "p5", "p6"}
    out = _live(world, "swap")
    m = _manifests(world, "swap.character-swap")[-1]
    assert out["results"][0]["status"] == "error" and m["status"] == "error"
    assert [it["status"] for it in m["items"]] == ["error"] * 3 + ["skipped"] * 3
    assert len(FakeComfy.calls) == 3


def test_retry_items_reruns_only_those_indices_with_the_same_seeds(world):
    node = _node(world["wf"], "swap.character-swap")
    node["data"]["seed"] = 500
    node["data"]["retry_items"] = [2]
    out = _live(world, "swap")
    assert out["ok"] and len(FakeComfy.calls) == 1
    m = _manifests(world, "swap.character-swap")[-1]
    assert [it["index"] for it in m["items"]] == [2] and m["items"][0]["seeds"] == [502] and m["item_count"] == 3


def test_the_approval_task_carries_the_item_count(world):
    out = _run(world, "swap", mode="stage-approval")
    assert not out["ok"] and "3 item(s)" in out["note"] and "assumed" in out["note"]
    assert FakeComfy.calls == []


def test_end_to_end_live_lands_one_post_folder_per_source_image(world, monkeypatch):
    import compositor

    def fake_composite(base, spec, root, block, ratio, size, out_dir, campaign, slide=None, provenance=None, dark_ground=True):
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{campaign}_{ratio.replace(':', 'x')}" + (f"_{slide[0]:02d}" if slide else "")
        p = out_dir / f"{stem}.png"
        p.write_bytes(b"\x89PNG dressed")
        return compositor.CompositeResult(p, p.with_suffix(".json"), "0" * 64, 7.0, [])
    monkeypatch.setattr(compositor, "composite", fake_composite)

    assert _live(world, "swap")["ok"]
    car = _live(world, "carousels")
    assert car["ok"] and len(FakeComfy.calls) == 6
    cm = _manifests(world, "carousels.carousel")[-1]
    assert [it["group"] for it in cm["items"]] == ["0", "1", "2"] and cm["cost_estimate"]["slides"] == 10
    fin = _live(world, "finish")
    assert fin["ok"], fin
    comp = _manifests(world, "finish.compositor")[-1]
    assert comp["status"] == "completed" and comp["groups"] == ["0", "1", "2"]
    exp = _manifests(world, "finish.export")[-1]
    assert exp["status"] == "completed" and exp["layout"] == "posts/<group>/slide-<n>"
    posts = world["root"] / "zz-test" / "runs" / world["wf"]["id"] / "finish.export" / exp["run_id"] / "export" / "posts"
    assert sorted(p.name for p in posts.iterdir() if p.is_dir()) == ["0", "1", "2"]
    assert (posts / "1" / "slide-01.png").exists()
    assert json.loads((posts.parent / "posts.json").read_text(encoding="utf-8"))["posts"] == {"0": ["slide-01.png"], "1": ["slide-01.png"], "2": ["slide-01.png"]}


# ---------------------------------------------------------------- cost

def test_cost_multiplies_by_items_and_slides_as_the_spec_says():
    swap = cost.estimate("wardrobe", items=50)
    car = cost.estimate("carousel", items=50, slides=10)
    assert swap["gpu_seconds"] == 600 and car["gpu_seconds"] == 5000 and swap["gpu_seconds"] + car["gpu_seconds"] == 5600
    assert car["basis"] == "assumed" and car["per"] == "slide" and car["per_item_gpu_seconds"] == 100
    assert car["formula"] == "10 s x 10 unit(s) x 50 item(s)"
    assert cost.estimate("compositor", items=50)["usd"] == 0
    assert cost.estimate("image-to-video", 2, seconds_of_video=6, items=3)["gpu_seconds"] == 90 * 2 * 6 * 3


def test_estimate_nodes_takes_item_counts_per_node():
    nodes = [{"id": "a", "kind": "wardrobe", "data": {}}, {"id": "b", "kind": "carousel", "data": {"params": {"slides": 10}}}]
    e = cost.estimate_nodes(nodes, {"a": 50, "b": 50})
    assert e["gpu_seconds"] == 5600 and e["items"] == 100 and e["basis"] == "assumed"
    assert cost.estimate_nodes(nodes)["gpu_seconds"] == 12 + 100


def test_the_gate_estimate_covers_every_item(world):
    node = _node(world["wf"], "swap.character-swap")
    assert runner._item_count(world["wf"], node, CAT) == 1          # nothing provided yet
    runner._provide_inputs(world["wf"], CAT)                        # what run_stage does before the gate
    assert runner._item_count(world["wf"], node, CAT) == 3
    assert runner._item_count(world["wf"], _node(world["wf"], "finish.compositor"), CAT) == 1


# ---------------------------------------------------------------- export layout

def test_export_lays_grouped_files_out_as_posts(tmp_path):
    files = []
    for i in range(4):
        p = tmp_path / f"img{i}.png"
        p.write_bytes(b"x")
        files.append(p)
    dry = edit.export(files, tmp_path / "out", dry_run=True, groups=["0", "0", "1", None])
    assert dry["status"] == "dry-run" and "posts/<group>/slide-<n>" in dry["note"] and dry["expected"]["groups"] == ["0", "1", "ungrouped"]
    r = edit.export(files, tmp_path / "out", dry_run=False, groups=["0", "0", "1", None])
    assert r["layout"] == "posts/<group>/slide-<n>"
    assert (tmp_path / "out" / "posts" / "0" / "slide-02.png").exists() and (tmp_path / "out" / "posts" / "1" / "slide-01.png").exists()
    assert (tmp_path / "out" / "posts" / "ungrouped" / "slide-01.png").exists()
    flat = edit.export(files[:2], tmp_path / "flat", dry_run=False)
    assert flat["layout"] == "flat" and (tmp_path / "flat" / "img0.png").exists()


# ---------------------------------------------------------------- the items that flow between nodes

def test_upstream_items_uses_placeholders_only_for_dry_runs(world):
    car = _node(world["wf"], "carousels.carousel")
    assert runner.upstream_items(world["wf"], car) == {"image": []}
    _run(world, "swap")
    assert runner.upstream_items(world["wf"], car) == {"image": []}
    ph = runner.upstream_items(world["wf"], car, placeholders=True)["image"]
    assert [p["placeholder"] for p in ph] == ["<swap.character-swap#0>", "<swap.character-swap#1>", "<swap.character-swap#2>"]
    assert runner.upstream_files(world["wf"], car) == {"image": []}


def test_a_pick_after_a_fan_out_keeps_the_group_of_what_it_passes(world):
    wf = world["wf"]
    _live(world, "swap")
    swap = _node(wf, "swap.character-swap")
    run_id = swap["data"]["results"][-1]["run_id"]
    pick = {"id": "p", "kind": "pick", "position": {"x": 0, "y": 0}, "data": {"params": {"k": 2}, "picked": [f"{swap['id']}#{run_id}#2", f"{swap['id']}#{run_id}#0"]}}
    wf["nodes"].append(pick)
    wf["edges"].append({"id": "ep", "source": swap["id"], "sourceHandle": "image", "target": "p", "targetHandle": "candidates", "type": "image"})
    car = _node(wf, "carousels.carousel")
    for e in wf["edges"]:
        if e["target"] == car["id"]:
            e["source"], e["sourceHandle"] = "p", "chosen"
    items = runner.upstream_items(wf, car)["image"]
    assert [it["group"] for it in items] == ["2", "0"]
    assert wa.validate(wf) == []
