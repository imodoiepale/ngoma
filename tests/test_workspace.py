"""The workspace scaffold: one command creates a workspace the studio can see, `check`
accepts what `new` writes, reserved keys are refused, and the two existing workspaces
still pass. Nothing here writes into brands/; every scaffold lands in tmp_path."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import workspace as ws  # noqa: E402
import workflow_author as wa  # noqa: E402

SCRIPT = REPO / "packages" / "strategy" / "workspace.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120)


# ------------------------------------------------------------------ the kit

def test_kit_examples_exist_and_carry_only_known_placeholders():
    for name in ("brand.yaml.example", "collection.json.example", "references.README.md", "README.md"):
        assert (ws.KIT / name).exists(), name
    import re
    known = {"key", "name", "name_upper", "accent", "kind", "date"}
    for name in ("brand.yaml.example", "references.README.md", "collection.json.example"):
        used = set(re.findall(r"\{\{(\w+)\}\}", (ws.KIT / name).read_text(encoding="utf-8")))
        assert used <= known, f"{name} uses unknown placeholders {used - known}"


def test_kit_example_names_every_required_key():
    doc = yaml.safe_load(ws._fill((ws.KIT / "brand.yaml.example").read_text(encoding="utf-8"),
                                  {"key": "k", "name": "N", "name_upper": "N", "accent": "#112233",
                                   "kind": "other", "date": "2026-01-01"}))
    for spec, _ in ws.REQUIRED + ws.RECOMMENDED:
        assert ws._has(doc, spec), f"brand.yaml.example lacks {spec}"


# ------------------------------------------------------------------ new

def test_dry_run_prints_the_plan_and_writes_nothing(tmp_path: Path):
    r = run("new", "demo-brand", "--name", "Demo Brand", "--dry-run", "--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "would write" in r.stdout and "brand.yaml" in r.stdout and "references/README.md" in r.stdout
    assert not (tmp_path / "demo-brand").exists()
    assert list(tmp_path.iterdir()) == []


def test_new_scaffolds_a_workspace_that_check_accepts(tmp_path: Path):
    r = run("new", "demo-brand", "--name", "Demo Brand", "--accent", "#30E0A8", "--kind", "fashion",
            "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    root = tmp_path / "demo-brand"
    for rel in ("brand.yaml", "references/README.md", "workflows", "runs", "assets/logo"):
        assert (root / rel).exists(), rel

    doc = yaml.safe_load((root / "brand.yaml").read_text(encoding="utf-8"))
    assert doc["brand"] == "demo-brand" and doc["display_name"] == "Demo Brand" and doc["kind"] == "fashion"
    assert doc["palette"]["measured"]["accent"] == "#30E0A8"
    assert doc["logo"]["rule"] == "COMPOSITE_ONLY" and doc["logo"]["master"].startswith("assets/logo/")
    assert doc["claim_safety"]["disclosure"]
    assert doc["voice"] and doc["languages"]["primary"]
    assert "{{" not in (root / "brand.yaml").read_text(encoding="utf-8")
    assert "written release" in (root / "references/README.md").read_text(encoding="utf-8")

    rep = ws.check("demo-brand", tmp_path)
    assert rep.ok, rep.errors
    # the scaffold cannot invent a logo, and says so
    assert any("logo master declared but absent" in w for w in rep.warnings)

    c = run("check", "demo-brand", "--root", str(tmp_path), "--json")
    assert c.returncode == 0 and json.loads(c.stdout)["ok"] is True


def test_the_scaffolded_kit_is_what_the_author_and_the_ui_read(tmp_path: Path):
    """workflow_author._brand_name and studio.js brandInfo both key on display_name and a
    top-level accent; the kit must satisfy both without either being told about it."""
    ws.create(ws.plan_new("acme", "Acme Co", "#123456", "product", None, tmp_path))
    assert wa._brand_name(tmp_path / "acme") == "Acme Co"
    text = (tmp_path / "acme" / "brand.yaml").read_text(encoding="utf-8")
    import re
    assert re.search(r'accent[a-z_]*:\s*["\']?#123456', text)


def test_from_copies_the_source_kit_and_styles_with_key_and_name_rewritten(tmp_path: Path):
    plan = ws.plan_new("second", "Second Act", "#000000", "music", "epalle", tmp_path)
    assert plan["source"] == "epalle" and any(k.startswith("styles/") for k in plan["files"])
    ws.create(plan)
    doc = yaml.safe_load((tmp_path / "second" / "brand.yaml").read_text(encoding="utf-8"))
    assert doc["brand"] == "second" and doc["display_name"] == "Second Act"
    assert doc["arc"]["name"] == "ASALI"          # inherited on purpose, flagged in the header
    head = (tmp_path / "second" / "brand.yaml").read_text(encoding="utf-8").splitlines()[0]
    assert "started from brands/epalle/brand.yaml" in head
    assert ws.check("second", tmp_path).ok


@pytest.mark.parametrize("key", sorted(ws.RESERVED) + ["_anything", "Has Space", "UPPER", "-lead", ""])
def test_reserved_and_malformed_keys_are_refused(key: str, tmp_path: Path):
    with pytest.raises(ws.WorkspaceError):
        ws.plan_new(key, "X", root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_reserved_key_is_refused_from_the_cli(tmp_path: Path):
    r = run("new", "_kit", "--name", "X", "--root", str(tmp_path))
    assert r.returncode == 2 and "reserved" in r.stderr
    assert not (tmp_path / "_kit").exists()
    for key in ("_presets", "_templates", "_business"):
        assert "reserved" in run("new", key, "--name", "X", "--root", str(tmp_path)).stderr


def test_an_existing_key_is_refused(tmp_path: Path):
    ws.create(ws.plan_new("dup", "Dup", root=tmp_path))
    with pytest.raises(ws.WorkspaceError, match="already exists"):
        ws.plan_new("dup", "Dup", root=tmp_path)


def test_bad_accent_and_kind_are_refused(tmp_path: Path):
    with pytest.raises(ws.WorkspaceError, match="RRGGBB"):
        ws.plan_new("a", "A", accent="green", root=tmp_path)
    with pytest.raises(ws.WorkspaceError, match="kind"):
        ws.plan_new("a", "A", kind="bank", root=tmp_path)


# ------------------------------------------------------------------ check

def test_check_fails_on_a_kit_missing_required_fields(tmp_path: Path):
    (tmp_path / "thin").mkdir()
    (tmp_path / "thin" / "brand.yaml").write_text("brand: thin\ndisplay_name: Thin\n", encoding="utf-8")
    rep = ws.check("thin", tmp_path)
    assert not rep.ok
    missing = " ".join(rep.errors)
    for spec in ("palette.measured", "logo.master", "logo.rule", "claim_safety.disclosure"):
        assert spec in missing, spec


def test_check_catches_key_mismatch_bad_hex_and_bad_logo_rule(tmp_path: Path):
    ws.create(ws.plan_new("real", "Real", root=tmp_path))
    p = tmp_path / "real" / "brand.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    doc["brand"] = "other"
    doc["palette"]["measured"]["accent"] = "red"
    doc["logo"]["rule"] = "DRAW_IT"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    rep = ws.check("real", tmp_path)
    text = " ".join(rep.errors)
    assert "folder is 'real'" in text and "non-#RRGGBB" in text and "COMPOSITE_ONLY" in text


def test_check_validates_reference_collections(tmp_path: Path):
    ws.create(ws.plan_new("refs", "Refs", root=tmp_path))
    refs = tmp_path / "refs" / "references"
    good = refs / "persona"
    good.mkdir()
    (good / "a.png").write_bytes(b"\x89PNG")
    (good / "collection.json").write_text(json.dumps(
        {"name": "persona", "use": "data", "rights": "owned", "kind": "image", "consent": False}), encoding="utf-8")
    bad = refs / "pins"
    bad.mkdir()
    (bad / "collection.json").write_text(json.dumps(
        {"name": "pins", "use": "data", "rights": "unclear", "consent": "yes"}), encoding="utf-8")
    silent = refs / "moodboard"
    silent.mkdir()
    (silent / "b.jpg").write_bytes(b"\xff\xd8")

    rep = ws.check("refs", tmp_path)
    errors = " ".join(rep.errors)
    assert "pins: use: data needs rights owned or licensed" in errors
    assert "pins: consent must be true or false" in errors
    assert any("moodboard" in w and "inspiration only" in w for w in rep.warnings)
    assert not any("persona" in e for e in rep.errors)


def test_check_refuses_studio_folders_and_missing_workspaces(tmp_path: Path):
    assert not ws.check("_kit").ok
    assert not ws.check("_presets").ok
    assert not ws.check("nope", tmp_path).ok


def test_the_first_two_workspaces_pass_check():
    for key in ("epalle", "ongea-pesa"):
        rep = ws.check(key)
        assert rep.ok, (key, rep.errors)


def test_runs_stay_out_of_git():
    assert ws.RUNS_IGNORE in (REPO / ".gitignore").read_text(encoding="utf-8")


# ------------------------------------------------------------------ list

def test_list_shows_the_existing_workspaces_and_a_scaffolded_one(tmp_path: Path):
    keys = {r["key"] for r in ws.list_workspaces()}
    assert {"epalle", "ongea-pesa"} <= keys
    assert not any(k.startswith("_") for k in keys)

    ws.create(ws.plan_new("new-one", "New One", "#ABCDEF", "agency", None, tmp_path))
    r = run("list", "--root", str(tmp_path), "--json")
    assert r.returncode == 0
    rows = json.loads(r.stdout)
    assert rows == [{"key": "new-one", "name": "New One", "kind": "agency", "accent": "#ABCDEF",
                     "workflows": 0, "collections": 0, "ok": True,
                     "errors": 0, "warnings": rows[0]["warnings"]}]


def test_list_matches_what_the_author_discovers():
    assert [r["key"] for r in ws.list_workspaces()] == [c["id"] for c in wa.clients()]
