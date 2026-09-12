"""Real provider pricing, transcribed from a dated route contract.

Source: `work/matrix-power-nodes/NODES.md`, generated from the WaveSpeed route contract
fetched 2026-07-29T03:28:03+02:00. Those are published price *formulas*, not guesses, so
they are implemented here as formulas rather than flattened to a single number per tier.

This file exists because the first version of the router carried invented per-tier costs
($0.01 / $0.04 / $0.12) which understated the flagship path by roughly half. A cost
estimate that is quietly wrong is worse than no estimate: it gets budgeted against.

Prices are USD. The contract expresses sub-dollar amounts in micro-dollars (70000 =
$0.07); that is normalised here.

CAVEAT: these are WaveSpeed's prices for the same underlying models. When calling through
OpenRouter the figures will differ. Treat them as an order-of-magnitude planning number
and reconcile against the live `/models` endpoint before relying on a budget.
"""
from __future__ import annotations

from dataclasses import dataclass

CONTRACT_FETCHED = "2026-07-29T03:28:03+02:00"
CONTRACT_SOURCE = "work/matrix-power-nodes/NODES.md (WaveSpeed route contract)"
MAX_CONTRACT_COST = 0.886  # the contract's own declared ceiling for a single call

MICRO = 1_000_000


@dataclass(frozen=True)
class Quote:
    usd: float
    model: str
    basis: str
    exact: bool          # False when the figure is cross-provider inference, not contract


def nano_banana_pro(resolution: str = "1k") -> Quote:
    """google/nano-banana-pro/edit — base $0.14, 4k multiplies by 12/7."""
    base = 0.14
    mult = {"4k": 12 / 7}.get(resolution.lower(), 1.0)
    return Quote(round(base * mult, 4), "nano-banana-pro",
                 f"base $0.14 x {mult:.3g} ({resolution})", True)


def nano_banana_2(resolution: str = "1k", web_search: bool = False,
                  image_search: bool = False) -> Quote:
    """google/nano-banana-2/edit — 0.5k is a flat $0.045; searches add $0.014 each."""
    r = resolution.lower()
    if r == "0.5k":
        total = 45000 / MICRO
        basis = "flat $0.045 (0.5k)"
    else:
        mult = {"2k": 1.5, "4k": 2.0}.get(r, 1.0)
        total = 0.07 * mult
        basis = f"base $0.07 x {mult:.3g} ({resolution})"
    extra = 0.0
    if web_search:
        extra += 14000 / MICRO
    if image_search:
        extra += 14000 / MICRO
    if extra:
        basis += f" + ${extra:.3f} search"
    return Quote(round(total + extra, 4), "nano-banana-2", basis, True)


def gpt_image_2(resolution: str = "1k", quality: str = "medium", images: int = 1) -> Quote:
    """openai/gpt-image-2/edit — a quality x resolution table, plus $0.012 per extra
    reference image. High 4k is $0.73, which is 6x the figure the router used to assume."""
    table = {
        "low":    {"1k": 20000, "2k": 30000, "4k": 40000},
        "medium": {"1k": 70000, "2k": 110000, "4k": 190000},
        "high":   {"1k": 230000, "2k": 410000, "4k": 730000},
    }
    q = quality.lower() if quality.lower() in table else "medium"
    r = resolution.lower() if resolution.lower() in table[q] else "1k"
    total = table[q][r] + max(0, images - 1) * 12000
    return Quote(round(total / MICRO, 4), "gpt-image-2",
                 f"{q} quality @ {r}" + (f" + {images-1} ref image(s)" if images > 1 else ""),
                 True)


# Router model id -> quoting function. Anything absent is quoted as unknown rather than
# assumed cheap.
QUOTERS = {
    "google/gemini-3-pro-image": lambda res, **kw: nano_banana_pro(res),
    "google/gemini-3.1-flash-image": lambda res, **kw: nano_banana_2(res, **kw),
    "google/gemini-3.1-flash-lite-image": lambda res, **kw: nano_banana_2("0.5k"),
    "openai/gpt-image-2": lambda res, **kw: gpt_image_2(res, kw.get("quality", "medium"),
                                                        kw.get("images", 1)),
}


def quote(model: str, resolution: str = "1k", **kw) -> Quote | None:
    """None means 'we do not have a contract price', which callers must surface as
    unknown — never as zero."""
    fn = QUOTERS.get(model)
    if fn is None:
        return None
    return fn(resolution, **kw)


if __name__ == "__main__":
    print(f"contract fetched {CONTRACT_FETCHED}\nsource {CONTRACT_SOURCE}")
    print(f"declared max single-call cost ${MAX_CONTRACT_COST}\n")
    for m in QUOTERS:
        for res in ("1k", "2k", "4k"):
            q = quote(m, res)
            print(f"  {m:<36} {res:<4} ${q.usd:<8.4f} {q.basis}")
    print(f"\n  gpt-image-2 high 4k -> ${quote('openai/gpt-image-2','4k',quality='high').usd}")
