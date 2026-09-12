"""Image router: one GenRequest -> the right backend.

Two peer families, chosen by policy rather than hierarchy:

  hosted  — OpenRouter image models (Nano Banana 2 / Pro, GPT-Image-2). No GPU, fast,
            per-call cost. Good for concept passes and for flagship stills.
  comfy   — open-source models through ComfyUI (FLUX.2 Klein, Qwen-Image / Edit, Z-Image
            Turbo, WAN, LTX) on local / RunPod pod / RunPod serverless. No per-image cost,
            full control, LoRA + character consistency, and the only path to video.

Neither is a "backup". `--backend auto` picks using the style's declared capability needs;
anything that needs a character LoRA, an image edit, identity preservation or motion goes
to comfy because hosted endpoints cannot do those reproducibly.

Every call is dry-run by default. Nothing is spent without --live.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Literal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "brandkit"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brandkit import GenRequest, load_brand, build_request  # noqa: E402
from pricing import quote  # noqa: E402

Backend = Literal["hosted", "comfy", "auto"]

# ---------------------------------------------------------------- hosted profiles

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

HOSTED_PROFILES: dict[str, dict[str, Any]] = {
    "concept_draft": {
        "chain": ["google/gemini-3.1-flash-lite-image", "google/gemini-3.1-flash-image"],
        "resolution": "1K",
        "purpose": "cheap high-volume exploration; never published",
    },
    "daily_premium": {
        "chain": ["google/gemini-3.1-flash-image", "openai/gpt-image-2", "google/gemini-3-pro-image"],
        "resolution": "2K",
        "purpose": "the default publishable still",
    },
    "brand_master_4k": {
        "chain": ["google/gemini-3-pro-image", "openai/gpt-image-2", "google/gemini-3.1-flash-image"],
        "resolution": "4K",
        "purpose": "flagship campaign masters",
    },
}

# ---------------------------------------------------------------- comfy profiles
# Templates resolve against workflows/manifest.json (50 deduped graphs).

COMFY_PROFILES: dict[str, dict[str, Any]] = {
    "klein_t2i": {
        "workflow": "workflows/api-tests/klein-t2i-test.json",
        "models": ["flux-2-klein-9b-fp8", "flux2-vae", "qwen_3_8b_fp8mixed"],
        "capabilities": ["text_to_image"],
        "purpose": "open-source still from a prompt; the workhorse",
    },
    "klein_dataset": {
        "workflow": "workflows/icekiub/KleinDataset_-_Icekiub_freelo.json",
        "models": ["flux-2-klein-9b-fp8", "flux2-vae", "qwen_3_8b_fp8mixed"],
        "capabilities": ["text_to_image", "batch", "character_consistency"],
        "prompt_driver": "CR Prompt List",
        "purpose": "one-shot character dataset from a reference image",
    },
    "carousel_pose": {
        "workflow": "workflows/icekiub/Carousel_Pose_changer.json",
        "models": ["flux-2-klein-9b-kv", "flux2-vae", "qwen_3_8b_fp8mixed"],
        "capabilities": ["image_edit", "pose_change", "character_consistency", "batch"],
        "prompt_driver": "CR Prompt List",
        "purpose": "re-pose one subject across carousel slides, background held",
        "blocked_by": "flux-2-klein-9b-kv is HF-gated; accept the licence or use the fp8 variant",
    },
    "qwen_edit": {
        "workflow": "workflows/icekiub/QWEN_IMAGE_UNLEASHED_ICEKIUB_SUBS_-_v1_.json",
        "models": ["Qwen-Rapid-AIO-NSFW-v18", "z_image_turbo_bf16", "qwen_3_4b"],
        "capabilities": ["image_edit", "batch"],
        "purpose": "instruction-driven edit of an existing image",
    },
    "faceswap": {
        "workflow": "workflows/icekiub/QWEN_ICY_Faceswap_-_SUBS_-_Icekiub_v1.json",
        "models": ["qwen_image_edit_2509_fp8_e4m3fn", "qwen_image_vae", "qwen_2.5_vl_7b_fp8_scaled"],
        "capabilities": ["faceswap", "identity_preservation", "upscale"],
        "purpose": "identity-locked face replacement with detailer + upscale",
    },
    "i2v_infinite": {
        "workflow": "workflows/icekiub/I2V_Infinite_extender_-_SUBS_-_Icekiub_v1.json",
        "models": ["wan2.2_i2v_high_noise_14B_fp8_scaled", "wan2.2_i2v_low_noise_14B_fp8_scaled", "wan_2.1_vae"],
        "capabilities": ["image_to_video", "long_form"],
        "purpose": "still -> chained long video",
    },
    "ltx_t2v": {
        "workflow": "workflows/icekiub/LTX2-T2V_-_ICY.json",
        "models": ["ltx-2-19b-dev-fp8", "ltx-2-19b-distilled-lora-384"],
        "capabilities": ["text_to_video", "audio"],
        "purpose": "text -> video with audio, up to 20s",
    },
    "scail_motion": {
        "workflow": "workflows/icekiub/ICY_SCAIL_2.0_Subs_-_icekiub_v2.json",
        "models": ["Wan21-14B-SCAIL-preview_fp8_scaled_mixed", "flux-2-klein-9b-fp8"],
        "capabilities": ["motion_transfer", "pose_retarget", "video"],
        "purpose": "drive a subject with reference motion",
    },
}

# Capability -> the family that can actually deliver it reproducibly.
COMFY_ONLY = {
    "character_consistency", "image_edit", "pose_change", "faceswap",
    "identity_preservation", "image_to_video", "text_to_video",
    "motion_transfer", "pose_retarget", "video", "long_form", "batch",
}


class RouterError(RuntimeError):
    pass


@dataclass
class Plan:
    backend: str
    profile: str
    target: str
    reason: str
    estimated_cost_usd: float | None
    request: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def required_capabilities(fmt: str | None, style_key: str) -> set[str]:
    caps: set[str] = set()
    if fmt == "reel":
        caps |= {"image_to_video"}
    if fmt == "carousel":
        caps |= {"batch", "character_consistency"}
    if style_key == "product_ui_showcase":
        caps |= {"image_edit"}
    return caps


def choose(req: GenRequest, backend: Backend = "auto", profile: str | None = None) -> Plan:
    notes: list[str] = []
    caps = required_capabilities(req.meta.get("format"), req.style_key)
    needs_comfy = bool(caps & COMFY_ONLY)

    if backend == "auto":
        backend = "comfy" if needs_comfy else "hosted"
        reason = (
            f"format={req.meta.get('format')} needs {sorted(caps & COMFY_ONLY)} "
            f"-> only open-source ComfyUI graphs do this reproducibly"
            if needs_comfy else
            "a single still with no edit/identity/motion requirement -> hosted is faster and needs no GPU"
        )
    else:
        reason = f"backend forced to {backend}"
        if backend == "hosted" and needs_comfy:
            notes.append(
                f"WARNING: this item needs {sorted(caps & COMFY_ONLY)}, which hosted endpoints "
                f"cannot guarantee. Expect drift across slides/frames."
            )

    if backend == "hosted":
        prof = profile or ("brand_master_4k" if req.width >= 3840 else "daily_premium")
        if prof not in HOSTED_PROFILES:
            raise RouterError(f"unknown hosted profile {prof!r}; have {sorted(HOSTED_PROFILES)}")
        spec = HOSTED_PROFILES[prof]
        target = spec["chain"][0]
        if not os.environ.get("OPENROUTER_API_KEY"):
            notes.append("OPENROUTER_API_KEY not set — dry-run only until it is in the secret store.")
        # Real contract prices, not guesses. See packages/image-router/pricing.py.
        q = quote(target, spec["resolution"].lower())
        if q is None:
            cost = None
            notes.append(f"no contract price for {target} — cost UNKNOWN, not zero")
        else:
            cost = q.usd
            notes.append(f"price basis: {q.basis} (WaveSpeed contract 2026-07-29; "
                         f"OpenRouter may differ)")
    else:
        prof = profile or _pick_comfy_profile(caps, req)
        if prof not in COMFY_PROFILES:
            raise RouterError(f"unknown comfy profile {prof!r}; have {sorted(COMFY_PROFILES)}")
        spec = COMFY_PROFILES[prof]
        target = spec["workflow"]
        wf = REPO / spec["workflow"]
        if not wf.exists():
            notes.append(f"workflow template missing on disk: {spec['workflow']}")
        if spec.get("blocked_by"):
            notes.append(f"BLOCKED: {spec['blocked_by']}")
        cost = 0.0
        notes.append(f"models required: {', '.join(spec['models'])}")

    return Plan(
        backend=backend, profile=prof, target=target, reason=reason,
        estimated_cost_usd=cost, request=req.to_dict(), notes=notes,
    )


def _pick_comfy_profile(caps: set[str], req: GenRequest) -> str:
    if "image_to_video" in caps or "text_to_video" in caps:
        return "i2v_infinite"
    if "pose_change" in caps or ("batch" in caps and "character_consistency" in caps):
        return "carousel_pose"
    if "faceswap" in caps:
        return "faceswap"
    if "image_edit" in caps:
        return "qwen_edit"
    return "klein_t2i"


def execute(plan: Plan, live: bool = False, out_dir: Path | None = None) -> dict[str, Any]:
    """Dry-run by default. Live execution is deliberately gated."""
    if not live:
        return {"status": "DRY_RUN", "would_call": plan.target, "backend": plan.backend,
                "estimated_cost_usd": plan.estimated_cost_usd, "notes": plan.notes}
    if plan.request["requires_human_approval"]:
        return {"status": "BLOCKED_PENDING_APPROVAL",
                "reason": f"claim_class={plan.request['claim_class']} requires a human decision",
                "backend": plan.backend}
    if plan.backend == "hosted":
        return _execute_hosted(plan, out_dir or REPO / "out")
    raise RouterError(
        "live comfy execution is not wired yet — it lands with packages/comfy-client "
        "(template injection + 4-backend submit/poll). Use --backend hosted or stay in dry-run."
    )


def _execute_hosted(plan: Plan, out_dir: Path) -> dict[str, Any]:
    import urllib.request

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RouterError("OPENROUTER_API_KEY is not set; refusing to call a paid endpoint.")
    req = plan.request
    body = json.dumps({
        "model": plan.target,
        "messages": [{"role": "user", "content": req["prompt"]}],
        "modalities": ["image", "text"],
    }).encode()
    r = urllib.request.Request(
        f"{OPENROUTER_BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://ongeapesa.nsait.co.ke", "X-Title": "epalle-studio"},
    )
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=300) as resp:
        payload = json.loads(resp.read())
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{req['semantic_key']}.response.json"
    raw.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"status": "OK", "model": plan.target, "elapsed_s": round(time.time() - t0, 2),
            "response": str(raw)}


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Route a brand generation request to a backend.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--idea", type=int)
    ap.add_argument("--style")
    ap.add_argument("--ratio")
    ap.add_argument("--backend", choices=["auto", "hosted", "comfy"], default="auto")
    ap.add_argument("--profile")
    ap.add_argument("--live", action="store_true", help="actually call the backend (spends money)")
    ap.add_argument("--plan-all", action="store_true", help="plan every calendar item and summarise")
    a = ap.parse_args()

    b = load_brand(a.brand)

    if a.plan_all:
        rows, by_backend, cost, unknown = [], {}, 0.0, 0
        for it in b.calendar["items"]:
            req = build_request(b, it["id"])
            p = choose(req, a.backend, a.profile)
            by_backend[p.backend] = by_backend.get(p.backend, 0) + 1
            if p.estimated_cost_usd is None:
                unknown += 1
            else:
                cost += p.estimated_cost_usd
            flag = "!" if req.requires_human_approval else " "
            rows.append(f"{it['id']:>3}{flag} {it['idea']:<24} {p.backend:<7} {p.profile:<16} {Path(p.target).name}")
        print("\n".join(rows))
        approve = sum(1 for i in b.calendar["items"] if i["claim_class"] != "standard")
        print()
        print(f"backends: {by_backend}")
        print(f"hosted cost: ${cost:.2f} for ONE image each"
              + (f"  ({unknown} without a contract price)" if unknown else ""))
        print("  a carousel is 5-10 slides, so real hosted spend is 5-10x that line;")
        print("  comfy items cost GPU time, not per-image fees.")
        print(f"needs human approval: {approve}")
        print("prices: WaveSpeed route contract 2026-07-29 (see pricing.py).")
        print("        OpenRouter's own rates differ - reconcile before budgeting.")
        return

    if a.idea is None and not a.style:
        ap.error("pass --idea N or --style KEY (or --plan-all)")
    req = build_request(b, a.idea, a.style, a.ratio)
    plan = choose(req, a.backend, a.profile)
    print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
    print("\n--- execute ---")
    print(json.dumps(execute(plan, live=a.live), indent=2))


if __name__ == "__main__":
    _cli()
