"""packages/video/motion_graphics.py: a JSON spec becomes a deterministic frame plan, and an MP4 when ffmpeg is there."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "video"))
import motion_graphics as mg  # noqa: E402

SPEC = {
    "aspect": "9:16", "width": 180, "fps": 8, "duration": 1.5, "client": "epalle",
    "background": {"color": "charcoal"},
    "lines": [
        {"text": "Pay in 3 taps", "in": 0.0, "out": 1.0, "style": "headline", "animation": "typed", "color": "ivory"},
        {"text": "Amina, Nairobi", "in": 0.25, "out": 1.5, "style": "lower-third", "color": "charcoal"},
        {"text": "No queue.", "in": 0.5, "out": 1.5, "style": "subhead", "animation": "slide-up"},
    ],
}


def test_plan_is_deterministic_and_sized_from_the_aspect():
    a, b = mg.plan(copy.deepcopy(SPEC)), mg.plan(copy.deepcopy(SPEC))
    assert a == b
    assert (a["width"], a["height"]) == (180, 320)
    assert a["fps"] == 8 and a["frame_count"] == 12
    assert a["background"]["color"] == "#1A1512"          # epalle kit charcoal
    assert a["lines"][0]["color"] == "#F2EBE0"             # epalle kit ivory
    assert a["lines"][1]["plate"]                          # a lower third sits on a plate


def test_typed_text_grows_and_fades_out():
    p = mg.plan(copy.deepcopy(SPEC))
    shown = [next((l["text"] for l in f["lines"] if l["line"] == 0), None) for f in p["frames"]]
    visible = [s for s in shown if s is not None]
    assert visible[0] == "P" and visible[-1] == "Pay in 3 taps"
    assert all(len(visible[i]) <= len(visible[i + 1]) for i in range(len(visible) - 1))
    assert shown[8:] == [None] * 4                         # out at 1.0 s = frame 8
    last = next(l for l in p["frames"][7]["lines"] if l["line"] == 0)
    assert last["opacity"] < 1.0                           # fading in the final FADE_S window


def test_slide_up_moves_and_fades_in():
    p = mg.plan(copy.deepcopy(SPEC))
    first = next(l for l in p["frames"][4]["lines"] if l["line"] == 2)      # in at 0.5 s = frame 4
    later = next(l for l in p["frames"][7]["lines"] if l["line"] == 2)
    assert first["opacity"] < later["opacity"] and first["dy"] > later["dy"] >= 0


@pytest.mark.parametrize("bad, message", [
    ({**SPEC, "lines": []}, "non-empty"),
    ({**SPEC, "aspect": "2:3", "width": None}, "aspect"),
    ({**SPEC, "lines": [{"text": "x", "in": 1, "out": 1}]}, "out must be after in"),
    ({**SPEC, "lines": [{"text": "x", "in": 0, "out": 1, "style": "banner"}]}, "style"),
    ({**SPEC, "lines": [{"text": "x", "in": 0, "out": 1, "color": "mauve"}]}, "colour"),
    ({**SPEC, "background": {"image": "does/not/exist.png"}}, "not found"),
])
def test_bad_specs_are_refused(bad, message):
    with pytest.raises(mg.MotionGraphicsError, match=message):
        mg.plan(bad)


def test_dry_run_writes_only_the_plan(tmp_path):
    out = tmp_path / "clip.mp4"
    r = mg.render(copy.deepcopy(SPEC), out, dry_run=True)
    assert r["status"] == "dry-run" and not out.exists()
    plan = json.loads(Path(r["plan_path"]).read_text(encoding="utf-8"))
    assert plan["frame_count"] == 12 and len(plan["frames"]) == 12
    assert plan["ffmpeg"][-1] == str(out) and "libx264" in plan["ffmpeg"]


def test_font_falls_back_to_pillow_without_downloading(monkeypatch):
    monkeypatch.setattr(mg, "SYSTEM_FONT_DIRS", [])
    monkeypatch.setattr(mg, "FONT_CANDIDATES", {k: ["nope.ttf"] for k in mg.FONT_CANDIDATES})
    path, fallback = mg.find_font(None, "headline", None)
    assert path is None and fallback is True
    assert mg._load_font(None, 20) is not None


def test_cli_dry_run_and_example(tmp_path, capsys):
    assert mg.main(["--example"]) == 0
    example = json.loads(capsys.readouterr().out)
    assert example["lines"]
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), encoding="utf-8")
    assert mg.main(["--spec", str(spec), "--out", str(tmp_path / "c.mp4"), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry-run"


def test_cli_help_exits_zero():
    r = subprocess.run([sys.executable, str(REPO / "packages" / "video" / "motion_graphics.py"), "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "--dry-run" in r.stdout and "--spec" in r.stdout


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="ffmpeg/ffprobe not on PATH; the plan tests above cover everything but the encode")
def test_tiny_render_produces_a_playable_h264(tmp_path):
    from PIL import Image
    screen = tmp_path / "screen.png"
    Image.new("RGB", (90, 160), (200, 220, 240)).save(screen)
    spec = copy.deepcopy(SPEC)
    spec["background"] = {"color": "charcoal", "phone": True, "screen": str(screen)}
    out = tmp_path / "clip.mp4"
    r = mg.render(spec, out)
    assert r["status"] == "completed" and out.exists() and out.stat().st_size > 500
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,nb_frames",
                            "-of", "json", str(out)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["codec_name"] == "h264" and (stream["width"], stream["height"]) == (180, 320)
    assert int(stream["nb_frames"]) == 12


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")
def test_render_over_a_background_video_overlays(tmp_path):
    bg = tmp_path / "bg.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=180x320:r=8", "-t", "1.5",
                    "-pix_fmt", "yuv420p", str(bg)], check=True)
    spec = copy.deepcopy(SPEC)
    spec["background"] = {"video": str(bg)}
    out = tmp_path / "over.mp4"
    r = mg.render(spec, out)
    assert r["status"] == "completed" and out.exists()
    assert "overlay" in " ".join(r["ffmpeg"])
