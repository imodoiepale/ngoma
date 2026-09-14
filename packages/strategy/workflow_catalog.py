"""Every workflow in the library: what it does, what it makes possible, and which ideas use it.

Joins four sources that already exist, so the table cannot drift from the code:
- workflows/manifest.json (every workflow, its node packs and models),
- packages/studio-ui/catalog/nodes.json (which canvas step runs which workflow),
- brands/_business/ideas.yaml via each idea's studio template (which ideas use that step),
- infra/runpod/download-plan.json (whether its models can be fetched).

Descriptions are written here once, per workflow. A new workflow without one fails the test.
Writes docs/workflows/WORKFLOWS.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "workflows" / "manifest.json"
CATALOG = REPO / "packages" / "studio-ui" / "catalog" / "nodes.json"
TEMPLATES = REPO / "brands" / "_templates" / "workflows"
PLAN = REPO / "infra" / "runpod" / "download-plan.json"
OUT = REPO / "docs" / "workflows" / "WORKFLOWS.md"

# canonical path -> (family, what it does, what it makes possible)
DESCRIPTIONS: dict[str, tuple[str, str, str]] = {
    # MiniMax H3 long-form and extension (Kijai / community examples)
    "workflows/1-KeyFrames/1-KEYFRAMES.json": ("H3 video", "Generates a clip that passes through chosen keyframe images.", "Storyboard-locked shots: hit exact poses or product frames at set times."),
    "workflows/3-Image-To-Long-Video/3-Image-To-Long-Video.json": ("H3 video", "Turns one image into a long video by chaining H3 extensions.", "30-second-plus reels and music-video scenes from a single still."),
    "workflows/4-Video-Extend-with-Reference-Image/4-Video-Extend-with-Reference-Image.json": ("H3 video", "Extends an existing clip while holding a reference image's identity.", "Longer takes without the character drifting."),
    "workflows/MiniMax-H3-Simple-WF/FLF-Workflow-With-Sol-Atten-_-Sage-Atten.json": ("H3 video", "First-and-last-frame video with SageAttention speed-ups.", "Controlled transitions between two stills, faster on supported GPUs."),
    "workflows/MiniMax-H3-Simple-WF/IMG-_-Audio-To-Video.json": ("H3 video", "Image plus audio to a talking or singing performance.", "Lip-synced spokespeople, greetings and music performances."),
    "workflows/MiniMax-H3-Simple-WF/Video-Character-Replace.json": ("H3 video", "Replaces the character in a source video with a reference character.", "Re-cast existing footage with a consented or fictional character."),
    "workflows/MiniMax-Long-Video-&-Extend-Video/2-Text-To-Long-Video.json": ("H3 video", "Text prompt to a long video through repeated extension.", "B-roll and loops with no source image."),
    "workflows/MiniMax-Long-Video-&-Extend-Video/5-Video-Extend-No-Reference-Image.json": ("H3 video", "Extends a clip from its last frames without a reference image.", "Quick continuations where identity is not critical."),
    "workflows/h3/NEW_-_2MP_De-Rope_Continuation_-_Working_Example.json": ("H3 video", "2-megapixel continuation with de-rope to avoid drift at high resolution.", "Sharper long takes for delivery masters."),
    "workflows/h3/NEW_-_AV_Extension.json": ("H3 video", "Extends a clip with its audio track kept in step.", "Longer performances where sound and picture must stay aligned."),
    "workflows/h3/NEW_-_Music_Video.json": ("H3 video", "Music-video graph: scenes driven by a song with extension between them.", "Full-length music videos from a song and references."),
    "workflows/h3/NEW_-_V2V_Latent_Motion_Transfer_with_upscale_and_de-rope_.json": ("H3 video", "Video-to-video latent motion transfer with upscaling and de-rope.", "Restyle or upscale footage while keeping its motion."),
    "workflows/h3/OLD_-_Hybrid_Extension.json": ("H3 video", "Earlier hybrid extension graph (kept for reference).", "Fallback when the newer extension graphs misbehave."),
    "workflows/h3/OLD_-_Motion_Context_-_Advanced.json": ("H3 video", "Earlier motion-context graph with advanced controls.", "Reference for tuning motion context by hand."),
    "workflows/h3/OLD_-_Motion_Context_-_Simple.json": ("H3 video", "Earlier motion-context graph, simple version.", "Reference for motion context basics."),
    "workflows/h3/UTILITY_-_AV_Bridge.json": ("H3 video", "Utility that bridges audio and video latents between graphs.", "Stitching audio-aware sections together."),
    "workflows/h3/UTILITY_-_Custom_Keyframes.json": ("H3 video", "Utility for placing custom keyframes on the timeline.", "Precise shot timing for edits and ads."),
    "workflows/h3-refmods/dainamo-refmod-generate.json": ("H3 RefMod", "Generates video from a saved RefMod character (Dainamo).", "Consistent characters across every clip with no LoRA training."),
    "workflows/h3-refmods/franckyb-refmod-create-from-folder.json": ("H3 RefMod", "Builds a RefMod character file from a folder of reference photos.", "A reusable character in seconds from owned or consented photos."),
    "workflows/h3-refmods/franckyb-refmod-picker-example.json": ("H3 RefMod", "Visual picker for choosing and applying saved RefMods.", "Switch characters quickly across a campaign."),
    # WAN / community workflows bundled with Matrix and earlier packs
    "workflows/Workflow-1/Workflow-1.json": ("Community", "Community image-and-video pipeline, first version (models linked in its notes).", "Reference build for combining image generation and animation."),
    "workflows/Workflow-1/Workflow-1-updated.json": ("Community", "Updated version of Workflow 1.", "Same as Workflow 1 with newer nodes."),
    "workflows/Workflow-2/Workflow-2.json": ("Community", "Community pipeline, second build (models linked in its notes).", "Reference build for a second generation-plus-edit chain."),
    "workflows/Workflow-2/Workflow-2-Updated.json": ("Community", "Updated version of Workflow 2.", "Same as Workflow 2 with newer nodes."),
    "workflows/matrix/EPALLE-Dataset-V1-safe.json": ("Dataset", "EPALLE's SFW adaptation of the Matrix power-nodes dataset builder.", "Training datasets for our own fictional characters."),
    "workflows/matrix/matrix-power-nodes-ai-dataset.json": ("Dataset", "MatrixLab's power-nodes AI dataset builder (original).", "Many consistent images of one character for LoRA training."),
    # Tests we wrote against the pod
    "workflows/api-tests/klein-t2i-test.json": ("Image", "Minimal Flux Klein text-to-image graph in API format.", "Bulk images on the pod: measured at 444 images per GPU-hour."),
    "workflows/api-tests/klein-t2i-sage-guard-test.json": ("Image", "Klein text-to-image with the SageAttention guard enabled.", "Checks the speed-up is safe before bulk runs."),
    "workflows/api-tests/klein-ishona-400.json": ("Image", "Klein test at 400 steps-equivalent quality for the Ishona look.", "Quality/speed comparison for brand renders."),
    "workflows/api-tests/klein-ishona-600.json": ("Image", "Klein test at the 600 setting for the Ishona look.", "Quality/speed comparison for brand renders."),
    # SCAIL 2 (Comfy-Org examples)
    "workflows/scail2/SCAIL-2_Animation.json": ("Motion", "SCAIL 2 character animation from a reference image and a driving video.", "Dance, walk and gesture clips for one character."),
    "workflows/scail2/SCAIL-2_Animation_WAN-Context-Windows.json": ("Motion", "SCAIL 2 animation using WAN context windows for longer clips.", "Longer motion-transfer takes on modest VRAM."),
    "workflows/scail2/SCAIL-2_Animation_multi-char.json": ("Motion", "SCAIL 2 animation with more than one character.", "Duets, group dances and two-person ads."),
    "workflows/scail2/SCAIL-2_Animation_multi-ref.json": ("Motion", "SCAIL 2 animation using several reference images of one character.", "Better identity when a single photo is not enough."),
    "workflows/scail2/SCAIL-2_Replacement.json": ("Motion", "SCAIL 2 replacement: swap the person in a video for the reference character.", "Re-cast a performance with a consented or fictional character."),
    # Icekiub (bought)
    "workflows/icekiub/Carousel_Pose_changer.json": ("Icekiub image", "Carousel pose changer, earlier copy.", "Same as V1.7; kept as the original download."),
    "workflows/icekiub/Carousel_Pose_changer_-_Icekiub_V1.7.json": ("Icekiub image", "Changes a person's pose by prompt while keeping the background (Klein KV).", "A 6-10 image Instagram carousel from one photo."),
    "workflows/icekiub/I2V_Infinite_extender_-_SUBS_-_Icekiub_v1.json": ("Icekiub video", "WAN 2.2 image-to-video that loops extensions past 15 seconds with one prompt.", "Long animated stills: reels, canvases, visualizers."),
    "workflows/icekiub/I2V_extender_with_Prompt_change_-_SUBS_-_Icekiub_v1.json": ("Icekiub video", "WAN 2.2 image-to-video extender that takes a new prompt per segment.", "Story beats within one long clip."),
    "workflows/icekiub/ICY_SCAIL_2.0_Subs_-_icekiub_v2.json": ("Icekiub motion", "Icekiub's SCAIL 2.0 motion control build (v2).", "Motion transfer with Klein first-frame prep."),
    "workflows/icekiub/ICY_SCAIL_2_0_Subs_-_icekiub_v2.json": ("Icekiub motion", "Docker-bundled copy of ICY SCAIL 2.0 v2 (different bytes).", "Same as ICY SCAIL 2.0 for the container build."),
    "workflows/icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-_Subs_-_Icekiub_v2.json": ("Icekiub dataset", "All-in-one influencer dataset with Klein plus Z-Image upscale.", "A 40-image LoRA dataset and character board from one reference."),
    "workflows/icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-no_base-_subs_-_Icekiub_v2.json": ("Icekiub dataset", "Dataset AIO starting from a loaded image instead of a generated base.", "Datasets for an existing character photo."),
    "workflows/icekiub/INFLUENCER_Dataset_AIO_-_Subs_-_Icekiub_v1.1.json": ("Icekiub dataset", "Qwen/Z-Image dataset AIO with SAM3 head swap, angles and Chroma.", "Datasets with varied angles on high-VRAM cards."),
    "workflows/icekiub/IcyMotion_Free_v3.json": ("Icekiub motion", "Free IcyMotion v3 motion-control graph.", "Try motion control before the subs builds."),
    "workflows/icekiub/KleinDataset_-_Icekiub_freelo.json": ("Icekiub dataset", "Free Klein dataset graph.", "Small datasets on lighter hardware."),
    "workflows/icekiub/LTX2-T2V_-_ICY.json": ("Icekiub video", "LTX 2 text-to-video.", "Shots from a prompt alone: VJ loops and B-roll."),
    "workflows/icekiub/LTX2.3KlingKiller_pose_depth_simplified_-_Icekiub_v2.json": ("Icekiub video", "LTX 2.3 video guided by pose and depth.", "Controlled camera and body motion without a character LoRA."),
    "workflows/icekiub/QWEN_ICY_Faceswap_-_SUBS_-_Icekiub_v1.json": ("Icekiub image", "Qwen Image Edit face swap with rotation matching and batch folders.", "Consented face swaps across a set of base images."),
    "workflows/icekiub/QWEN_IMAGE_UNLEASHED_ICEKIUB_SUBS_-_v1_.json": ("Icekiub image", "Qwen Image Edit AIO, v1: prompt-driven edits of any image.", "Relight, restyle, new room or outfit by instruction."),
    "workflows/icekiub/QWEN_Nsfw_Klein_faceswap_-_icekiub_v1.json": ("Icekiub 18+", "Klein face swap built for 18+ material.", "Fictional-adult line only; never on real people."),
    "workflows/icekiub/Krea_gen_+_scail_motion_control_subs.json": ("Icekiub motion", "Krea 2 generates the first frame, then SCAIL 2 animates it to a driving video.", "A new character performing a reference dance or gesture in one run."),
    "workflows/icekiub/Motion_Control_Icy_-SUBS.json": ("Icekiub motion", "Icekiub's SCAIL 2 motion-control subs workflow with SAM 3.1 masking.", "Clean motion transfer from TikTok-style reference clips."),
    "workflows/icekiub/ICY_WAN_ANIMATE_-_Face_Only_-prer-_Icekiub_V4.json": ("Icekiub motion", "WAN 2.2 Animate V4 that replaces only the face, with Klein first-frame swap.", "Keep the performer's body and clothes; change the face (consented)."),
    "workflows/icekiub/ICY_WAN_ANIMATE_-_Full_Body_Swap_-prer-_Icekiub_V4.json": ("Icekiub motion", "WAN 2.2 Animate V4 full-body swap onto a driving video, with relight LoRA.", "Put a character into any dance or talking clip."),
    "workflows/icekiub/WANT2VLora_Faceswap_-_Icekiub_v1.json": ("Icekiub motion", "WAN 2.2 T2V low-noise character LoRA over a source clip (with TikTok downloader).", "Video face swap when a character LoRA exists."),
    "workflows/icekiub/H3_Icy_image.json": ("Icekiub image", "MiniMax H3 hybrid image generation from face, body, outfit and room references with an LLM prompter.", "Consistent-character stills without a LoRA."),
    "workflows/icekiub/icy_ref_character_sheet_for_minimax.json": ("Icekiub image", "Klein four-view character sheet from one reference.", "Reference sheets that feed H3 and RefMods."),
    "workflows/icekiub/Krea2Icy_-Subs_1.1.json": ("Icekiub image", "Krea 2 turbo realism with Icy realism LoRA and optional depth control.", "Photoreal persona and lifestyle images."),
    "workflows/icekiub/Krea2icysubs-_with_Lm_prompting.json": ("Icekiub image", "Krea 2 realism with LM Studio writing the prompts from references.", "Hands-off prompt variety for large batches."),
    "workflows/icekiub/Consistent_Room_WF_v3.1-_Icekiub_Subs.json": ("Icekiub image", "Same room from new angles with Klein; room can come from Qwen Image 2512.", "Consistent sets for personas, interiors and product scenes."),
    "workflows/icekiub/zbase+zit+control_-_icekiub_v1.json": ("Icekiub image", "Z-Image base for composition, turbo to refine, optional ControlNet.", "Fast pose-controlled images with a second quality pass."),
    "workflows/icekiub/Image_to_image_Klein_edit_-_Icekiub_v1.5.json": ("Icekiub 18+", "Klein image-to-image that recreates a reference with your character.", "Recreate a composition with an owned character; 18+ gated."),
    "workflows/icekiub/Image_to_image_Klein_edit_-_batch_-_Icekiub_v1.5.json": ("Icekiub 18+", "Batch version of the Klein image-to-image recreate.", "Folder-scale recreations; 18+ gated."),
    "workflows/icekiub/I2I_no_lora_faceswap_subs.json": ("Icekiub image", "Klein head swap from one face reference, no LoRA.", "Consented head swaps for datasets and edits."),
    "workflows/icekiub/Any_Clothes_9B_-_Subs_-_Icekiub_V1.3.json": ("Icekiub image", "Klein 9B outfit swap from one or more clothing references.", "Every SKU on a model; virtual try-on."),
    "workflows/icekiub/NSFW_SURGERY_SUBS_-_ICEKIUB_v1.json": ("Icekiub 18+", "SDXL detection-and-inpaint repair of broken anatomy on images.", "Fictional-adult line only; needs detection models kept outside git."),
    "workflows/icekiub/NSFW_BATCH_SURGERY_SUBS_-_ICEKIUB_v1.json": ("Icekiub 18+", "Batch version of the SDXL anatomy repair.", "Fictional-adult line only."),
    "workflows/icekiub/AIO_-_Uncensored_captioning_workflow_-_subs_-_icekiub_v1.5.json": ("Icekiub dataset", "Local Qwen3-VL (abliterated) captions for image folders or video frames.", "Caption LoRA datasets offline, with focus instructions."),
    "workflows/icekiub/KLEIN_-_watermark_removal_-_ICEKIUB_V1.json": ("Icekiub image", "Klein watermark removal, single image.", "Clean our own or licensed assets only."),
    "workflows/icekiub/KLEIN_-_batch_watermark_removal_-_ICEKIUB_V1.json": ("Icekiub image", "Klein watermark removal over a folder.", "Clean our own or licensed archives only."),
    "workflows/icekiub/QWEN_IMAGE_UNLEASHED_ICEKIUB_SUBS_-_v2.json": ("Icekiub 18+", "Phr00t Rapid AIO Qwen edit (v2) with Z-turbo upscale and batch.", "Edits the standard Qwen edit refuses; 18+ gated."),
}


def load() -> dict[str, Any]:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["workflows"]
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))["nodes"]
    plan = json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {}
    status: dict[str, set[str]] = {}
    for bucket in ("resolved", "auto_download", "creator_private", "manual", "unresolved"):
        for r in plan.get(bucket, []):
            for u in r.get("used_by", []):
                status.setdefault(u, set()).add(bucket)
    ideas_by_kind: dict[str, set[str]] = {}
    for t in sorted(TEMPLATES.glob("*.studio.json")):
        wf = json.loads(t.read_text(encoding="utf-8"))
        idea = (wf.get("source") or {}).get("idea") or t.name.split("-", 1)[0].upper()
        for n in wf["nodes"]:
            ideas_by_kind.setdefault(n["kind"], set()).add(idea)
    rows = []
    for w in man:
        c = w["canonical"]
        steps = [n for n in cat if n["backend"].get("workflow") == c.removeprefix("workflows/")]
        ideas = sorted({i for n in steps for i in ideas_by_kind.get(n["kind"], set())})
        fam, does, enables = DESCRIPTIONS.get(c, ("Unsorted", "", ""))
        rows.append({"canonical": c, "family": fam, "does": does, "enables": enables, "steps": steps, "ideas": ideas,
                     "nodes": w["node_count"], "packs": [p for p in w["node_packs"] if p != "comfy-core"],
                     "models": status.get(c, set()), "skool": any(s.startswith("skool:") for s in w.get("sources", [])),
                     "adult": any(n.get("adult") for n in steps) or fam.endswith("18+"),
                     "consent": any(n.get("consent") for n in steps)})
    return {"rows": rows, "catalog": cat, "ideas_by_kind": ideas_by_kind}


def _models(s: set[str]) -> str:
    if not s:
        return "none named"
    if s <= {"resolved", "auto_download"}:
        return "all fetchable"
    parts = []
    if "creator_private" in s:
        parts.append("creator-private LoRA")
    if "manual" in s:
        parts.append("manual download")
    if "unresolved" in s:
        parts.append("some unresolved")
    return ", ".join(parts)


def render(data: dict[str, Any]) -> str:
    rows = data["rows"]
    wired = [r for r in rows if r["steps"]]
    L = ["# Workflow library", "",
         "Generated by `packages/strategy/workflow_catalog.py` from the manifest, the canvas catalogue, the 50 idea "
         "templates and the pod download plan. Do not edit by hand.", "",
         f"**{len(rows)} workflows.** {len(wired)} run a studio canvas step; the rest are library references, "
         "alternates or older versions kept for comparison. Gates: **Consent** = owned, consented or fictional "
         "likenesses only. **18+** = fictional-adult line only, separate entity.", "",
         "Models column: *all fetchable* means every model it names is in `infra/runpod/download-plan.json` with a "
         "source. Anything else says what is missing.", ""]
    families: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        families.setdefault(r["family"], []).append(r)
    L += ["## Summary", "", "| Family | Workflows | Run a studio step | Used by ideas |", "|---|---|---|---|"]
    for fam, rs in sorted(families.items()):
        ideas = sorted({i for r in rs for i in r["ideas"]})
        L.append(f"| {fam} | {len(rs)} | {sum(1 for r in rs if r['steps'])} | {', '.join(ideas) or '—'} |")
    L.append("")
    for fam, rs in sorted(families.items()):
        L += [f"## {fam}", "", "| Workflow | What it does | What it makes possible | Studio step | Ideas | Nodes | Models | Gate |",
              "|---|---|---|---|---|---|---|---|"]
        for r in sorted(rs, key=lambda r: r["canonical"]):
            gate = " ".join(g for g, on in (("18+", r["adult"]), ("Consent", r["consent"])) if on) or "—"
            step = ", ".join(f"`{n['kind']}`" for n in r["steps"]) or "library only"
            name = Path(r["canonical"]).stem.replace("_", " ")
            L.append(f"| [{name}](../../{r['canonical']}){' (bought)' if r['skool'] else ''} | {r['does']} | {r['enables']} | "
                     f"{step} | {', '.join(r['ideas']) or '—'} | {r['nodes']} | {_models(r['models'])} | {gate} |")
        L.append("")
    L += ["## Studio steps and the ideas that use them", "",
          "| Step | Runs on | Ideas |", "|---|---|---|"]
    for n in data["catalog"]:
        be = n["backend"]
        runs = {"comfy": f"ComfyUI `{be.get('workflow')}`", "python": f"studio code `{be.get('module')}`",
                "publish": f"publisher `{be.get('module')}`", "router": "hosted model (OpenRouter)", "input": "you provide it",
                "brand": "brand.yaml", "human": "a person decides", "gap": f"not runnable yet: {be.get('reason')}"}[be["kind"]]
        L.append(f"| **{n['label']}** (`{n['kind']}`) | {runs} | {', '.join(sorted(data['ideas_by_kind'].get(n['kind'], []))) or '—'} |")
    return "\n".join(L).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Write docs/workflows/WORKFLOWS.md from the manifest, catalogue and idea templates.")
    ap.add_argument("--check", action="store_true", help="fail if a workflow has no description")
    args = ap.parse_args()
    data = load()
    missing = [r["canonical"] for r in data["rows"] if not r["does"]]
    if missing:
        print("workflows with no description:\n  " + "\n  ".join(missing), file=sys.stderr)
        if args.check:
            return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {len(data['rows'])} workflows")
    return 1 if missing and args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
