"""packages/engine/lora_train.py: rights gate, ai-toolkit config, captions, launch command; never trains."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "engine"))
import lora_train as lt  # noqa: E402


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A fake brands/ root with one owned, fictional collection of 6 tiny images, one captioned."""
    from PIL import Image
    brands = tmp_path / "brands"
    col = brands / "demo" / "references" / "persona-x"
    col.mkdir(parents=True)
    for i in range(6):
        Image.new("RGB", (8, 8), (i * 30, 0, 0)).save(col / f"img{i}.png")
    (col / "img0.txt").write_text("a woman in a red dress, window light\n", encoding="utf-8")
    (col / "collection.json").write_text(json.dumps({"name": "persona-x", "use": "data", "rights": "owned",
                                                     "kind": "image", "consent": False, "fictional": True}), encoding="utf-8")
    monkeypatch.setattr(lt, "BRANDS", brands)
    return {"brands": brands, "col": col, "out": tmp_path / "out"}


def set_meta(col: Path, **meta) -> None:
    (col / "collection.json").write_text(json.dumps({"name": "persona-x", "kind": "image", **meta}), encoding="utf-8")


def test_dry_run_writes_config_and_launch_only(workspace):
    r = lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])
    assert r["status"] == "dry-run"
    assert (workspace["out"] / "config.yaml").exists() and (workspace["out"] / "launch.sh").exists()
    assert not (workspace["out"] / "dataset").exists() and not (workspace["out"] / "manifest.json").exists()
    assert r["images"] == 6 and r["captions"] == {"source": "sidecar", "captioned": 1,
                                                  "uncaptioned": [f"img{i}.png" for i in range(1, 6)]}
    assert r["rights"]["ok"] and r["rights"]["fictional"] and not r["rights"]["consent"]
    assert any("no caption" in n for n in r["needs_setup"]) and any("ai-toolkit" in n for n in r["needs_setup"])
    assert r["command"].startswith("bash ") and r["output"].endswith(".safetensors")


def test_config_is_a_valid_ai_toolkit_job(workspace):
    lt.plan_job("demo", "persona-x", "prsx", steps=1000, rank=32, dry_run=True, out=workspace["out"])
    cfg = yaml.safe_load((workspace["out"] / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["job"] == "extension"
    proc = cfg["config"]["process"][0]
    assert proc["type"] == "sd_trainer" and proc["trigger_word"] == "prsx"
    assert proc["network"] == {"type": "lora", "linear": 32, "linear_alpha": 32}
    assert proc["train"]["steps"] == 1000 and proc["train"]["noise_scheduler"] == "flowmatch"
    assert proc["model"]["name_or_path"] == lt.BASES["klein-9b"]["path"] and proc["model"]["arch"] == "flux2"
    assert proc["datasets"][0]["folder_path"].endswith("/dataset") and proc["datasets"][0]["resolution"] == [512, 768, 1024]
    assert proc["training_folder"].startswith(lt.POD_TRAINING)


def test_full_plan_stages_dataset_with_trigger_prefixed_captions(workspace):
    r = lt.plan_job("demo", "persona-x", "prsx", dry_run=False, allow_uncaptioned=True, out=workspace["out"])
    assert r["status"] == "planned"
    ds = workspace["out"] / "dataset"
    assert sorted(p.name for p in ds.iterdir()) == sorted([f"img{i}.png" for i in range(6)] + [f"img{i}.txt" for i in range(6)])
    assert (ds / "img0.txt").read_text(encoding="utf-8") == "prsx a woman in a red dress, window light\n"
    assert (ds / "img1.txt").read_text(encoding="utf-8") == "prsx\n"
    manifest = json.loads((workspace["out"] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "planned" and manifest["trigger"] == "prsx" and manifest["needs_setup"]
    launch = (workspace["out"] / "launch.sh").read_text(encoding="utf-8")
    assert "scp -i" in launch and "run.py" in launch and lt.POD_AI_TOOLKIT in launch and "\r" not in launch
    assert "WARNING: dataset has no captions" in launch


def test_captions_from_the_captioning_step_are_used(workspace):
    caps = workspace["brands"] / "caps.jsonl"
    caps.write_text("\n".join(json.dumps({"file": f"img{i}.png", "caption": f"caption {i}"}) for i in range(6)), encoding="utf-8")
    r = lt.plan_job("demo", "persona-x", "prsx", dry_run=False, captions=caps, out=workspace["out"])
    assert r["captions"] == {"source": "jsonl", "captioned": 6, "uncaptioned": []}
    assert not any("no caption" in n for n in r["needs_setup"])
    assert (workspace["out"] / "dataset" / "img3.txt").read_text(encoding="utf-8") == "prsx caption 3\n"
    assert not (workspace["out"] / "captions.txt").exists()


def test_captions_template_is_written_when_nothing_is_captioned(workspace):
    (workspace["col"] / "img0.txt").unlink()
    lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])
    template = (workspace["out"] / "captions.txt").read_text(encoding="utf-8")
    assert template.count("\tprsx ") == 6


def test_base_from_collection_and_krea_flags_arch_verification(workspace):
    set_meta(workspace["col"], use="data", rights="licensed", fictional=True, base="krea-2")
    r = lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])
    assert r["base"]["id"] == "krea-2" and any("arch" in n for n in r["needs_setup"])
    with pytest.raises(lt.LoraTrainError, match="base must be"):
        lt.plan_job("demo", "persona-x", "prsx", base="sdxl", dry_run=True, out=workspace["out"])


@pytest.mark.parametrize("meta, reason", [
    ({"use": "data", "rights": "unclear", "fictional": True}, "rights are 'unclear'"),
    ({"use": "inspiration", "rights": "owned", "fictional": True}, "mood board"),
    ({"use": "data", "rights": "owned"}, "consent"),                       # a real person, no release
    ({"use": "data", "rights": "owned", "consent": False, "notes": ["shot on a phone"]}, "consent"),
])
def test_bad_rights_are_refused_before_anything_is_written(workspace, meta, reason):
    set_meta(workspace["col"], **meta)
    with pytest.raises(lt.LoraTrainError, match=reason):
        lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])
    assert not workspace["out"].exists()


def test_consented_real_person_passes(workspace):
    set_meta(workspace["col"], use="data", rights="owned", consent=True)
    r = lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])
    assert r["rights"]["ok"] and "consent" in r["rights"]["why"]


def test_no_collection_json_means_unclear_rights(workspace):
    (workspace["col"] / "collection.json").unlink()
    with pytest.raises(lt.LoraTrainError, match="unclear"):
        lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])


def test_too_few_images_and_bad_trigger_are_refused(workspace):
    for i in range(3, 6):
        (workspace["col"] / f"img{i}.png").unlink()
    with pytest.raises(lt.LoraTrainError, match="at least 4"):
        lt.plan_job("demo", "persona-x", "prsx", dry_run=True, out=workspace["out"])
    with pytest.raises(lt.LoraTrainError, match="trigger"):
        lt.plan_job("demo", "persona-x", "Bad Trigger", dry_run=True, out=workspace["out"])


def test_yaml_writer_round_trips_the_config():
    cfg = lt.build_config("n", "trg", "klein-9b", 3000, 16, [512, 1024], "/workspace/epalle/training/n")
    assert yaml.safe_load(lt.to_yaml(cfg)) == cfg


def test_never_runs_anything(workspace, monkeypatch):
    import subprocess as sp
    monkeypatch.setattr(sp, "run", lambda *a, **k: pytest.fail("lora_train must not execute anything"))
    monkeypatch.setattr(sp, "Popen", lambda *a, **k: pytest.fail("lora_train must not execute anything"))
    lt.plan_job("demo", "persona-x", "prsx", dry_run=False, allow_uncaptioned=True, out=workspace["out"])


def test_cli_help_and_dry_run(workspace, capsys):
    r = subprocess.run([sys.executable, str(REPO / "packages" / "engine" / "lora_train.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    for flag in ("--client", "--collection", "--trigger", "--base", "--steps", "--rank", "--captions", "--dry-run"):
        assert flag in r.stdout, flag
    rc = lt.main(["--client", "demo", "--collection", "persona-x", "--trigger", "prsx", "--dry-run", "--out", str(workspace["out"])])
    assert rc == 0 and json.loads(capsys.readouterr().out)["status"] == "dry-run"
    rc = lt.main(["--client", "demo", "--collection", "nope", "--trigger", "prsx", "--dry-run"])
    assert rc == 1 and "no reference collection" in capsys.readouterr().err
