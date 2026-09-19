// Readiness of every catalogue capability, derived from what is on disk rather than declared:
//
//   ready        the step can run now: a ComfyUI workflow with a port map and no missing
//                model, a python step the engine runs, a hosted model with a key, an input.
//   needs-setup  bound to a backend but something is missing: no .ports.json, a model that
//                needs a manual or creator-private download, an engine that does not run the
//                step yet, a missing API key.
//   gap          no backend at all.
//
// Sources: packages/studio-ui/catalog/nodes.json, workflows/manifest.json, workflows/**/
// *.ports.json, infra/runpod/download-plan.json, packages/engine/runner.py (LOCAL_STEPS) and
// brands/_presets/engine.yaml. All read only.
import fs from "node:fs/promises";
import path from "node:path";
import { REPO, loadCatalog } from "./studio";
import { loadPricing } from "./pricing";

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function readJson(p, fallback) {
  try { return JSON.parse(await fs.readFile(p, "utf8")); } catch { return fallback; }
}

async function localSteps() {
  try {
    const py = await fs.readFile(path.join(REPO, "packages/engine/runner.py"), "utf8");
    const m = py.match(/LOCAL_STEPS\s*=\s*\{([^}]*)\}/);
    if (!m) return new Set();
    return new Set([...m[1].matchAll(/"([a-z0-9-]+)"/g)].map((x) => x[1]));
  } catch {
    return new Set();
  }
}

function modelBlockers(plan, workflowRel) {
  const key = `workflows/${workflowRel}`;
  const out = [];
  for (const [bucket, label] of [["manual", "manual download"], ["creator_private", "creator-private file"], ["unresolved", "unresolved model"]]) {
    for (const entry of plan?.[bucket] || []) {
      if ((entry.used_by || []).includes(key)) out.push({ file: entry.file, folder: entry.folder, why: label, look_at: entry.look_at || null });
    }
  }
  return out;
}

const RUNS_ON = { input: "You provide it", brand: "Read from brand.yaml", comfy: "ComfyUI on the pod", router: "Hosted model", python: "Studio code", publish: "Draft for a person to publish", human: "Your decision", gap: "No backend yet" };

export async function loadCapabilities() {
  const [catalog, pricing, plan, manifest, steps] = await Promise.all([
    loadCatalog(),
    loadPricing(),
    readJson(path.join(REPO, "infra/runpod/download-plan.json"), null),
    readJson(path.join(REPO, "workflows/manifest.json"), { workflows: [] }),
    localSteps(),
  ]);
  const inManifest = new Set((manifest.workflows || []).map((w) => String(w.canonical || "").replace(/^workflows\//, "")));
  const hostedKey = !!(process.env.OPENROUTER_API_KEY || process.env.OPENAI_API_KEY);

  const caps = [];
  for (const n of catalog.nodes) {
    const be = n.backend || {};
    const reasons = [];
    let status = "ready";
    let variants = 1;
    if (be.kind === "gap") {
      status = "gap";
      reasons.push(be.reason || "No backend yet.");
    } else if (be.kind === "comfy") {
      const rel = be.workflow;
      if (!inManifest.has(rel)) reasons.push("The ComfyUI workflow is not in workflows/manifest.json.");
      if (!(await exists(path.join(REPO, "workflows", rel.replace(/\.json$/, ".ports.json"))))) reasons.push("No port map (.ports.json), so the runner cannot bind inputs.");
      const blockers = modelBlockers(plan, rel);
      if (blockers.length) reasons.push(`${blockers.length} model file(s) need attention: ${blockers.map((b) => `${b.file} (${b.why})`).join(", ")}.`);
      if (reasons.length) status = "needs-setup";
      variants = blockers.length;
    } else if (be.kind === "python") {
      if (!steps.has(n.kind)) { status = "needs-setup"; reasons.push("The engine does not run this step yet; a dry run records it and moves on."); }
      else if (!(await exists(path.join(REPO, be.module || "")))) { status = "needs-setup"; reasons.push(`${be.module} is missing.`); }
    } else if (be.kind === "router") {
      if (!hostedKey) { status = "needs-setup"; reasons.push("No hosted-model key on the server (OPENROUTER_API_KEY)."); }
    } else if (be.kind === "publish") {
      if (!(await exists(path.join(REPO, be.module || "")))) { status = "needs-setup"; reasons.push(`${be.module} is missing.`); }
      else reasons.push("Creates a draft; a person publishes.");
    }
    const unit = pricing.seconds_per_unit[n.kind] || null;
    caps.push({
      kind: n.kind,
      label: n.label,
      category: n.category,
      blurb: n.blurb,
      inputs: n.inputs,
      outputs: n.outputs,
      params: n.params || [],
      backend: be,
      consent: !!n.consent,
      adult: !!n.adult,
      steps: n.steps || [],
      status,
      reasons,
      runsOn: RUNS_ON[be.kind] || be.kind,
      estimate: unit ? { seconds: unit.seconds, basis: unit.basis, per: unit.per, usd: Math.round((unit.seconds / 3600) * pricing.rate.usd_per_hour * 10000) / 10000 } : null,
      canEach: ["comfy", "router", "python", "gap"].includes(be.kind) && n.inputs.some((p) => !p.optional && (p.type === "image" || p.type === "video" || p.id === "media")),
      modelBlockers: variants,
    });
  }

  // Alternatives (Higgsfield's side-by-side model choice): same category, same required input
  // types, same output type.
  const sig = (c) => `${c.category}|${c.inputs.filter((p) => !p.optional).map((p) => p.type).sort().join(",")}|${c.outputs[0]?.type}`;
  for (const c of caps) {
    if (c.category === "inputs" || c.category === "decide") continue;
    c.alternatives = caps.filter((o) => o !== c && sig(o) === sig(c) && !o.adult).map((o) => ({ kind: o.kind, label: o.label, status: o.status, estimate: o.estimate })).slice(0, 4);
  }

  return {
    categories: catalog.categories,
    types: catalog.types,
    media_ports: catalog.media_ports,
    pricing,
    capabilities: caps,
    counts: {
      ready: caps.filter((c) => c.status === "ready").length,
      needsSetup: caps.filter((c) => c.status === "needs-setup").length,
      gap: caps.filter((c) => c.status === "gap").length,
    },
  };
}

// The status map the canvas paints on nodes: kind -> {status, reasons}.
export function readinessByKind(caps) {
  return Object.fromEntries(caps.capabilities.map((c) => [c.kind, { status: c.status, reasons: c.reasons, estimate: c.estimate }]));
}
