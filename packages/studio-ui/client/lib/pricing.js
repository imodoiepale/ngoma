// Reads the engine's spending model: brands/_presets/engine.yaml (budget cap, GPU, seconds per
// unit with their basis) and the GPU rate table in packages/strategy/unit_economics.py. Read
// only; a human edits those files. Server side.
import fs from "node:fs/promises";
import path from "node:path";
import { REPO } from "./studio";
import { parseYaml } from "./yaml-lite";

const FALLBACK_RATE = { key: "a100-80gb", name: "A100 80GB", usd_per_hour: 1.64, basis: "assumed", source: "planning figure" };

async function gpuRates() {
  try {
    const py = await fs.readFile(path.join(REPO, "packages/strategy/unit_economics.py"), "utf8");
    const rates = {};
    const re = /"([a-z0-9-]+)":\s*Rate\("([^"]+)",\s*([\d.]+),\s*"([^"]+)",\s*"([^"]*)"\)/g;
    let m;
    while ((m = re.exec(py))) rates[m[1]] = { key: m[1], name: m[2], usd_per_hour: Number(m[3]), basis: m[4], source: m[5] };
    return rates;
  } catch {
    return {};
  }
}

export async function loadPricing() {
  let cfg = {};
  try {
    cfg = parseYaml(await fs.readFile(path.join(REPO, "brands/_presets/engine.yaml"), "utf8")) || {};
  } catch {
    cfg = {};
  }
  const rates = await gpuRates();
  const gpu = typeof cfg.gpu === "string" ? cfg.gpu : FALLBACK_RATE.key;
  const perUnit = {};
  for (const [k, v] of Object.entries(cfg.seconds_per_unit || {})) {
    if (v && typeof v === "object" && Number(v.seconds) > 0) perUnit[k] = { seconds: Number(v.seconds), basis: v.basis || "assumed", per: v.per || "unit", source: v.source || null };
  }
  return {
    budget_usd: Number(cfg.budget_usd) || 0,
    gpu,
    rate: rates[gpu] || FALLBACK_RATE,
    max_items: Number(cfg.max_items) || 100,
    seconds_per_unit: perUnit,
    source: "brands/_presets/engine.yaml",
  };
}
