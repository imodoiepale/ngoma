"""The bought Icekiub Skool classroom: every file is held, attributed, gated and safe to load."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "library" / "tools"))
import import_skool_pack as isp  # noqa: E402

LESSONS = json.loads((REPO / "workflows" / "icekiub" / "skool" / "lessons.json").read_text(encoding="utf-8"))["lessons"]
MANIFEST = json.loads((REPO / "workflows" / "manifest.json").read_text(encoding="utf-8"))["workflows"]
CATALOG = json.loads((REPO / "packages" / "studio-ui" / "catalog" / "nodes.json").read_text(encoding="utf-8"))["nodes"]


def test_every_lesson_has_a_staging_folder_mapping():
    titles = {les["title"] for les in LESSONS if not les.get("section")}
    assert titles == set(isp.LESSON_DIR), titles ^ set(isp.LESSON_DIR)
    assert isp.ADULT <= titles and isp.CONSENT <= titles


def test_imported_workflows_name_their_skool_lesson():
    skool = [w for w in MANIFEST if any(s.startswith("skool:") for s in w.get("sources", []))]
    assert len(skool) >= 20
    urls = {les.get("lesson_url") for les in LESSONS}
    for w in skool:
        lesson = next(s for s in w["sources"] if s.startswith("skool:")).removeprefix("skool:")
        assert lesson in urls, w["canonical"]


def test_icekiub_node_types_are_attributed_not_left_unknown():
    for w in MANIFEST:
        unknown = set(w.get("unattributed_node_types", []))
        assert not unknown & {"ICYLMStudioMultimodalPrompt", "IcyMultiRefLoader", "IcyMegapixelResize",
                              "IcyQwen3AllInOne", "IcyTikTokDownloader"}, w["canonical"]


def test_no_model_weights_or_torch_load_patch_enter_the_repo():
    held = REPO / "workflows" / "icekiub"
    weights = [p for p in held.rglob("*") if p.suffix.lower() in isp.MODEL_EXT]
    assert not weights, weights
    assert not (held / "nodes" / "comfyui-unsafe-torch").exists()
    patched = [p for p in held.rglob("*.py") if "weights_only'] = False" in p.read_text(encoding="utf-8", errors="replace")]
    assert not patched, patched


def test_adult_steps_are_flagged_and_briefs_never_reach_them():
    sys.path.insert(0, str(REPO / "packages" / "strategy"))
    import workflow_author as wa
    adult = {n["kind"] for n in CATALOG if n.get("adult")}
    assert {"nsfw-surgery", "edit-anything", "klein-i2i"} <= adult
    for brief in ("Sheng WhatsApp status ad for a mama mboga", "carousel from one product photo",
                  "music video with motion transfer and lip sync", "character dataset for a fictional persona"):
        kinds = {n["kind"] for n in wa.from_brief(brief, "ongea-pesa")["nodes"]}
        assert not kinds & adult, (brief, kinds & adult)


def test_face_and_character_steps_from_skool_require_consent():
    by_kind = {n["kind"]: n for n in CATALOG}
    for kind in ("h3-reference-image", "character-sheet", "klein-headswap", "wan-animate",
                 "motion-control", "wan-lora-faceswap"):
        assert by_kind[kind].get("consent") is True, kind


def test_safe_name_matches_existing_repo_style():
    assert isp.safe_name("Motion Control Icy -SUBS.json") == "Motion_Control_Icy_-SUBS.json"
    assert isp.safe_name("KLEIN - watermark removal - ICEKIUB V1 (1).json") == "KLEIN_-_watermark_removal_-_ICEKIUB_V1.json"
    assert isp.safe_name("Image to image Klein edit  - Icekiub v1.5.json") == "Image_to_image_Klein_edit_-_Icekiub_v1.5.json"
