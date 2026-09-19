"""References: what a folder of images lets the engine do, and the gate it must pass. No network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
sys.path.insert(0, str(REPO / "packages" / "library"))
import references as refs  # noqa: E402
import workflow_author as wa  # noqa: E402

RefCollection = refs.RefCollection   # the engine's, whichever module currently owns the name `schema`
CAT = wa.load_catalog()


def _feature(**over) -> dict:
    base = {"path": "x.png", "kind": "image", "width": 1080, "height": 1350, "aspect": "4:5",
            "palette": [{"hex": "#150F0A", "share": 0.8, "luma": 15.9, "sat": 0.5, "hue": 0.07},
                        {"hex": "#4B3120", "share": 0.1, "luma": 53.3, "sat": 0.57, "hue": 0.07},
                        {"hex": "#8C7058", "share": 0.05, "luma": 116.2, "sat": 0.37, "hue": 0.08}],
            "mean_luma": 24.0, "contrast": 31.0, "saturation": 100.0, "warm_ratio": 0.7,
            "subject_quadrant": "bottom-left", "quiet_zones": ["top-left"], "copy_zone": "top-left",
            "edge_density": 0.05, "duration_s": None, "cut_count": None, "avg_shot_s": None}
    return {**base, **over}


# ---------------------------------------------------------------- possibilities

def test_possibilities_cover_every_reference_port_and_carry_a_gate():
    rows = refs.possibilities(CAT)
    covered = {(r["node"], r["port"]) for r in rows}
    for n in CAT["nodes"]:
        for p in n["inputs"]:
            if p["id"] == "media" or p["type"] in ("image", "video", "audio"):
                assert (n["kind"], p["id"]) in covered, f"{n['kind']}.{p['id']} has no possibilities row"
    gates = {refs.GATE_DATA, refs.GATE_CONSENT, refs.GATE_INSPIRATION}
    assert all(r["gate"] in gates for r in rows)
    assert any(r["node"] == "" and r["gate"] == refs.GATE_INSPIRATION for r in rows), "the mood board row"
    consent_rows = {(r["node"], r["port"]) for r in rows if r["gate"] == refs.GATE_CONSENT}
    assert ("faceswap", "face") in consent_rows and ("refmod-create", "images") in consent_rows
    assert ("wardrobe", "clothes") not in consent_rows


def test_render_possibilities_matches_the_committed_doc():
    doc = refs.POSSIBILITIES_DOC
    assert doc.exists(), "run: uv run --with pyyaml packages/engine/references.py possibilities"
    assert refs.render_possibilities(CAT) == doc.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert refs.render_possibilities(CAT) == refs.render_possibilities(CAT)


# ---------------------------------------------------------------- the gate

def test_unclear_rights_never_feed_a_port():
    col = RefCollection(name="mood", use="data", rights="unclear", consent=True, count=40)
    for port in ("image", "video", "media"):
        ok, why = refs.gate(col, port, needs_consent=False)
        assert not ok and "inspire" in why


def test_consent_ports_need_a_release_and_owned_data_feeds():
    owned = RefCollection(name="avatar", use="data", rights="owned", consent=False, count=12)
    ok, why = refs.gate(owned, "image", needs_consent=True)
    assert not ok and "consent" in why
    assert refs.gate(owned, "image", needs_consent=False) == (True, "avatar: owned data")
    released = RefCollection(name="avatar", use="data", rights="licensed", consent=True, count=12)
    assert refs.gate(released, "image", needs_consent=True)[0]
    inspiration = RefCollection(name="board", use="inspiration", rights="owned")
    assert not refs.gate(inspiration, "image", needs_consent=False)[0]
    clip = RefCollection(name="clip", kind="video", use="data", rights="owned")
    assert refs.gate(clip, "media", False)[0] and not refs.gate(clip, "image", False)[0]


# ---------------------------------------------------------------- fragments

def test_features_to_fragments_is_deterministic_and_empty_on_an_empty_file(tmp_path):
    f = tmp_path / "vision.jsonl"
    f.write_text(json.dumps(_feature()) + "\n" +
                 json.dumps(_feature(kind="video", mean_luma=30.0, avg_shot_s=1.2, cut_count=10)) + "\n",
                 encoding="utf-8")
    a, b = refs.features_to_fragments(f), refs.features_to_fragments(f)
    assert a == b and a
    assert a[0].startswith("palette led by near-black (#150F0A)")
    assert "low-key, dark frames" in a and "soft contrast" in a and "warm cast" in a
    assert "subject placed bottom-left" in a and "keep the top-left quiet for copy" in a
    assert any(x.startswith("fast cut rhythm") for x in a)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert refs.features_to_fragments(empty) == []
    assert refs.features_to_fragments(f, min_samples=3) == []


# ---------------------------------------------------------------- collections on disk

def test_write_and_read_collection_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(refs, "BRANDS", tmp_path / "brands")
    doc = refs.write_collection("acme", "wardrobe-red", use="data", rights="owned", consent=False,
                               source="manual", notes=("6 phone photos",))
    folder = refs.collection_dir("acme", "wardrobe-red")
    assert (folder / refs.COLLECTION_FILE).exists() and doc["notes"] == ["6 phone photos"]
    (folder / "a.png").write_bytes(b"x")
    (folder / "sub").mkdir()
    (folder / "sub" / "b.JPG").write_bytes(b"x")
    (folder / "notes.txt").write_text("not media", encoding="utf-8")
    col = refs.read_collection("acme", "wardrobe-red")
    assert col == RefCollection(name="wardrobe-red", kind="image", use="data", rights="owned",
                                consent=False, path=col.path, count=2)
    assert col.may_feed()
    assert [c.name for c in refs.list_collections("acme")] == ["wardrobe-red"]
    with pytest.raises(refs.ReferenceError):
        refs.write_collection("acme", "bad", use="data", rights="stolen")
    with pytest.raises(refs.ReferenceError):
        refs.read_collection("acme", "missing")


def test_read_collection_tolerates_a_utf8_bom(tmp_path, monkeypatch):
    """PowerShell's `Set-Content -Encoding utf8` prefixes a BOM; a run must not fail on it
    (BLOCKERS 21). The two epalle fixtures are also asserted BOM-free."""
    monkeypatch.setattr(refs, "BRANDS", tmp_path / "brands")
    folder = refs.collection_dir("acme", "bom")
    folder.mkdir(parents=True)
    body = json.dumps({"name": "bom", "use": "data", "rights": "owned", "consent": True}, indent=2)
    (folder / refs.COLLECTION_FILE).write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    (folder / "a.png").write_bytes(b"x")
    col = refs.read_collection("acme", "bom")
    assert (col.use, col.rights, col.consent, col.count) == ("data", "owned", True, 1)
    for name in ("red-dress", "wardrobe-red-dress"):
        f = REPO / "brands" / "epalle" / "references" / name / refs.COLLECTION_FILE
        if f.exists():
            assert not f.read_bytes().startswith(b"\xef\xbb\xbf"), f"{f} starts with a BOM"


def test_search_terms_become_pinterest_urls_and_urls_pass_through():
    assert refs.search_url("neon street portrait") == "https://www.pinterest.com/search/pins/?q=neon+street+portrait"
    assert refs.search_url("https://www.pinterest.com/pin/1/") == "https://www.pinterest.com/pin/1/"


# ---------------------------------------------------------------- graph

@pytest.mark.skipif(not (REPO / "graph" / "graph.json").exists(), reason="graph/graph.json not built")
def test_graph_paths_and_can_feed_over_the_studio_layer():
    import graph_query as gq
    nodes, edges = gq.load()
    found = gq.find_paths(nodes, edges, "reference-images", "image-to-video")
    assert found and found[0] == ["reference-images", "image-to-video"]
    groups = gq.steps_accepting(nodes, "image")
    assert "step:wardrobe" in {s["id"] for steps in groups.values() for s in steps}
    assert "step:image-to-video" in nodes and nodes["step:image-to-video"].get("backend") == "comfy"
    assert any(e["rel"] == "backed_by" and e["src"] == "step:image-to-video" for e in edges)
