"""What a step would cost before it runs. Every figure says whether it was measured or assumed."""
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


@lru_cache(maxsize=1)
def config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def budget_usd() -> float:
    return float(config().get("budget_usd") or 0)


def worker_name() -> str:
    return str(config().get("worker") or "engine")


def estimate(kind: str, variants: int = 1, seconds_of_video: int | None = None) -> dict[str, Any]:
    """USD for one node run. Zero, and says so, for steps that use no GPU."""
    cfg = config()
    rate = GPU_RATES[cfg.get("gpu", "a100-80gb")]
    spec = cfg["seconds_per_unit"].get(kind)
    if not spec:
        return {"usd": 0.0, "gpu_seconds": 0, "basis": "none", "note": f"{kind} uses no GPU time in this model"}
    units = variants * (seconds_of_video or 1) if spec.get("per") == "second_of_video" else variants
    gpu_s = float(spec["seconds"]) * units
    return {"usd": round(gpu_s / 3600 * rate.usd_per_hour, 4), "gpu_seconds": round(gpu_s, 1),
            "basis": spec["basis"], "rate": f"{rate.name} ${rate.usd_per_hour}/h ({rate.basis})"}


def estimate_nodes(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    total, basis = 0.0, set()
    for n in nodes:
        d = n.get("data") or {}
        e = estimate(n["kind"], int(d.get("variant_count") or 1), d.get("params", {}).get("seconds"))
        total += e["usd"]
        basis.add(e["basis"])
    return {"usd": round(total, 4), "basis": "measured" if basis <= {"measured", "none"} else "assumed"}
