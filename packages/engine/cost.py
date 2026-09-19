"""What a step would cost before it runs. Every figure says whether it was measured or assumed.

    estimate = seconds_per_unit x units x items

`units` is variants (one image), variants x seconds for video steps (`per: second_of_video`),
or variants x slides for the carousel (`per: slide`, one pose line = one output image).
`items` is how many times a fan-out node runs (`data.each`): the files that reach its
iterated port. A plain node has items = 1. docs/engine/BATCHES.md
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
from unit_economics import GPU_RATES  # noqa: E402

CONFIG = REPO / "brands" / "_presets" / "engine.yaml"
DEFAULT_MAX_ITEMS = 100


@lru_cache(maxsize=1)
def config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def budget_usd() -> float:
    return float(config().get("budget_usd") or 0)


def worker_name() -> str:
    return str(config().get("worker") or "engine")


def max_items() -> int:
    """Most items one fan-out node may run over; `max_items` in engine.yaml (default 100)."""
    try:
        return max(1, int(config().get("max_items") or DEFAULT_MAX_ITEMS))
    except (TypeError, ValueError):
        return DEFAULT_MAX_ITEMS


def estimate(kind: str, variants: int = 1, seconds_of_video: int | None = None,
             items: int = 1, slides: int | None = None) -> dict[str, Any]:
    """USD for one node run. Zero, and says so, for steps that use no GPU.

    `items` multiplies everything (a fan-out runs once per item); `slides` counts for kinds
    whose unit is a slide. The result carries the per-item figure so a manifest can show
    "N items x S s".
    """
    cfg = config()
    rate = GPU_RATES[cfg.get("gpu", "a100-80gb")]
    spec = cfg["seconds_per_unit"].get(kind)
    items = max(1, int(items or 1))
    variants = max(1, int(variants or 1))
    if not spec:
        return {"usd": 0.0, "gpu_seconds": 0, "basis": "none", "items": items,
                "note": f"{kind} uses no GPU time in this model"}
    per = spec.get("per", "image")
    if per == "second_of_video":
        units = variants * (seconds_of_video or 1)
    elif per == "slide":
        units = variants * max(1, int(slides or 1))
    else:
        units = variants
    per_item = float(spec["seconds"]) * units
    gpu_s = per_item * items
    out = {"usd": round(gpu_s / 3600 * rate.usd_per_hour, 4), "gpu_seconds": round(gpu_s, 1),
           "basis": spec["basis"], "rate": f"{rate.name} ${rate.usd_per_hour}/h ({rate.basis})",
           "items": items, "per_item_gpu_seconds": round(per_item, 1), "per": per,
           "formula": f"{spec['seconds']} s x {units} unit(s) x {items} item(s)"}
    if per == "slide":
        out["slides"] = max(1, int(slides or 1))
    return out


def estimate_node(node: dict[str, Any], items: int = 1) -> dict[str, Any]:
    """The estimate for one workflow node given how many items reach it."""
    d = node.get("data") or {}
    params = d.get("params") or {}
    return estimate(node["kind"], int(d.get("variant_count") or 1), params.get("seconds"),
                    items=items, slides=params.get("slides"))


def estimate_nodes(nodes: list[dict[str, Any]], items: dict[str, int] | None = None) -> dict[str, Any]:
    """Total for a set of nodes. `items` maps node id -> item count for fan-out nodes."""
    total, gpu, basis, n_items = 0.0, 0.0, set(), 0
    for n in nodes:
        e = estimate_node(n, (items or {}).get(n["id"], 1))
        total += e["usd"]
        gpu += e["gpu_seconds"]
        basis.add(e["basis"])
        n_items += e.get("items", 1) if e["basis"] != "none" else 0
    return {"usd": round(total, 4), "gpu_seconds": round(gpu, 1), "items": n_items,
            "basis": "measured" if basis <= {"measured", "none"} else "assumed"}
