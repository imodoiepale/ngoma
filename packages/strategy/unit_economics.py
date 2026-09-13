"""Unit economics for the studio's offers: what a deliverable costs to make, and what it earns.

Every money figure in docs/business/ comes from these functions, so a price change is one
edit, not fifty. Inputs are either MEASURED (we ran it), CONTRACT (a published price
formula, see packages/image-router/pricing.py) or ASSUMED (a planning number that must be
replaced by a live figure before anyone budgets against it). Each result says which.

The anchor that started this: "1,000 images a day for a social media manager, in under six
hours". On the pod, the Klein text-to-image workflow made 45 images in 364.87 s
(infra/runpod/verification-summary.md). That is ~444 images per GPU-hour, so 1,000 images
take ~2.3 GPU-hours plus model load — well inside six hours on one card.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "image-router"))

Basis = str  # "measured" | "contract" | "assumed"


@dataclass(frozen=True)
class Rate:
    name: str
    usd_per_hour: float
    basis: Basis
    source: str


# ASSUMED on-demand GPU prices, 2026-09-13. Replace with `runpod_api.py gpu-types` output
# before budgeting; community-cloud and spot prices are lower, secure cloud higher.
GPU_RATES: dict[str, Rate] = {
    "a100-80gb": Rate("A100 80GB", 1.64, "assumed", "RunPod on-demand planning figure, verify live"),
    "rtx-4090": Rate("RTX 4090 24GB", 0.69, "assumed", "RunPod on-demand planning figure, verify live"),
    "h100-80gb": Rate("H100 80GB", 2.49, "assumed", "RunPod on-demand planning figure, verify live"),
}


@dataclass(frozen=True)
class Throughput:
    workflow: str
    units: int
    seconds: float
    gpu: str
    basis: Basis
    source: str

    @property
    def per_hour(self) -> float:
        return self.units / self.seconds * 3600


# MEASURED on the pod. Everything else is flagged when used.
KLEIN_T2I_POD = Throughput("klein-t2i (45-image batch)", 45, 364.87, "a100-80gb", "measured",
                           "infra/runpod/verification-summary.md")


@dataclass
class Cost:
    usd: float
    gpu_hours: float = 0.0
    basis: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"${self.usd:,.2f} ({self.gpu_hours:.2f} GPU-h; {'; '.join(self.basis)})"


def gpu_batch_cost(units: int, tp: Throughput = KLEIN_T2I_POD, gpu: str | None = None,
                   overhead_hours: float = 0.25) -> Cost:
    """GPU cost for `units` outputs: run time at measured throughput plus model load/cold start."""
    if units < 0:
        raise ValueError("units must be >= 0")
    rate = GPU_RATES[gpu or tp.gpu]
    hours = units / tp.per_hour + (overhead_hours if units else 0.0)
    return Cost(round(hours * rate.usd_per_hour, 2), round(hours, 3),
                [f"throughput {tp.basis}: {tp.per_hour:.0f}/h ({tp.source})",
                 f"rate {rate.basis}: ${rate.usd_per_hour}/h {rate.name}"])


def hosted_batch_cost(units: int, model: str = "google/gemini-3.1-flash-image",
                      resolution: str = "1k") -> Cost:
    """API cost for `units` hosted images from the dated route contract."""
    from pricing import quote
    q = quote(model, resolution)
    if q is None:
        raise ValueError(f"no contract price for {model} @ {resolution}")
    return Cost(round(units * q.usd, 2), 0.0,
                [f"contract: {q.basis} x {units}" + ("" if q.exact else " (cross-provider inference)")])


def hours_for(units: int, tp: Throughput = KLEIN_T2I_POD, overhead_hours: float = 0.25) -> float:
    return units / tp.per_hour + (overhead_hours if units else 0.0)


@dataclass(frozen=True)
class Scenario:
    clients: int
    price_per_client_month: float
    cost_per_client_month: float

    @property
    def mrr(self) -> float:
        return round(self.clients * self.price_per_client_month, 2)

    @property
    def gross_margin(self) -> float:
        if not self.mrr:
            return 0.0
        return round(1 - (self.clients * self.cost_per_client_month) / self.mrr, 3)


def mrr_range(price: float, cost: float, clients: tuple[int, int, int]) -> dict[str, Scenario]:
    low, base, high = clients
    if not (0 <= low <= base <= high):
        raise ValueError("clients must satisfy 0 <= low <= base <= high")
    return {k: Scenario(n, price, cost) for k, n in zip(("low", "base", "high"), clients)}


def social_manager_daily_pack(images_per_day: int = 1000, days: int = 22,
                              gpu: str = "a100-80gb") -> dict[str, object]:
    """The anchor offer, costed both ways so the cheaper backend is visible, not assumed."""
    per_day_gpu = gpu_batch_cost(images_per_day, gpu=gpu)
    per_day_api = hosted_batch_cost(images_per_day)
    return {
        "images_per_day": images_per_day,
        "hours_per_day": round(hours_for(images_per_day), 2),
        "fits_six_hours": hours_for(images_per_day) <= 6,
        "gpu_cost_per_day": per_day_gpu,
        "hosted_cost_per_day": per_day_api,
        "gpu_cost_per_month": round(per_day_gpu.usd * days, 2),
        "hosted_cost_per_month": round(per_day_api.usd * days, 2),
    }


if __name__ == "__main__":
    pack = social_manager_daily_pack()
    for k, v in pack.items():
        print(f"{k:<24} {v}")
