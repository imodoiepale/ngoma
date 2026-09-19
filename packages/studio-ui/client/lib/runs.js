// Run manifests are the studio's record of what happened: brands/<ws>/runs/<workflow>/<node>/
// <run>/manifest.json, written by packages/engine/runner.py. This module only reads them.
//
// Consumed from the runner's contract (W3): run_id, workflow, node, kind, status, files[],
// bindings, seeds, cost_estimate {usd, gpu_seconds, basis, rate}, started, finished, and for
// fan-out nodes items[] of {index, group, input, files, sha256, prompt_ids, status,
// gpu_seconds_actual}; node status "partial" when some items failed; gpu_seconds_actual and
// cost_actual when a run measured itself.
import fs from "node:fs/promises";
import path from "node:path";
import { REPO, TEMPLATES } from "./studio";

const BRANDS = path.join(REPO, "brands");
const MEDIA = /\.(png|jpe?g|webp|mp4|webm|mov)$/i;
const VIDEO = /\.(mp4|webm|mov)$/i;

export function mediaUrl(rel) {
  return `/api/media?path=${encodeURIComponent(String(rel).replace(/\\/g, "/"))}`;
}
export function isVideo(f) {
  return VIDEO.test(String(f));
}

async function readDirSafe(p) {
  try { return await fs.readdir(p, { withFileTypes: true }); } catch { return []; }
}

// Files the manifest names are repo-relative; anything else is looked for next to it.
function normFiles(files, runDir) {
  return (files || []).map((f) => {
    const s = String(f).replace(/\\/g, "/");
    if (s.startsWith("brands/")) return s;
    if (path.isAbsolute(s)) return path.relative(REPO, s).replace(/\\/g, "/");
    return path.relative(REPO, path.join(runDir, s)).replace(/\\/g, "/");
  }).filter((f) => MEDIA.test(f));
}

function normalise(m, ws, workflow, node, runId, runDir) {
  const files = normFiles(m.files, runDir);
  const items = Array.isArray(m.items) ? m.items.map((it, i) => ({
    index: Number.isInteger(it.index) ? it.index : i,
    group: it.group ?? null,
    input: it.input ? String(it.input).replace(/\\/g, "/") : null,
    files: normFiles(it.files, runDir),
    status: it.status || m.status || "unknown",
    gpu_seconds_actual: it.gpu_seconds_actual ?? null,
  })) : null;
  return {
    workspace: ws,
    workflow,
    node,
    run_id: m.run_id || runId,
    kind: m.kind || node.split(".").pop(),
    status: m.status || "unknown",
    backend: m.backend || null,
    comfy_workflow: m.workflow || null,
    files,
    items,
    itemCount: items ? items.length : 0,
    itemsDone: items ? items.filter((i) => i.status === "completed").length : 0,
    itemsFailed: items ? items.filter((i) => ["error", "failed", "blocked", "timeout"].includes(i.status)).length : 0,
    bindings: m.bindings || {},
    seeds: m.seeds || [],
    prompt: m.prompt || m.params?.prompt || null,
    cost_estimate: m.cost_estimate || null,
    cost_actual: m.cost_actual || (m.gpu_seconds_actual != null && m.cost_estimate?.usd != null
      ? { usd: null, gpu_seconds: m.gpu_seconds_actual, basis: "measured" } : null),
    gpu_seconds_actual: m.gpu_seconds_actual ?? null,
    note: m.note || null,
    started: m.started || null,
    finished: m.finished || null,
    canvas: `/w/${ws}/f/${workflow}`,
  };
}

async function runsForWorkflow(ws, workflow) {
  const root = path.join(BRANDS, ws, "runs", workflow);
  const out = [];
  for (const node of await readDirSafe(root)) {
    if (!node.isDirectory()) continue;
    for (const r of await readDirSafe(path.join(root, node.name))) {
      if (!r.isDirectory()) continue;
      const runDir = path.join(root, node.name, r.name);
      try {
        const m = JSON.parse(await fs.readFile(path.join(runDir, "manifest.json"), "utf8"));
        out.push(normalise(m, ws, workflow, node.name, r.name, runDir));
      } catch { /* a run without a manifest is not a run */ }
    }
  }
  return out;
}

// Every run, newest first. Scope by workspace and workflow when given.
export async function listRuns({ workspace, workflow } = {}) {
  const spaces = workspace ? [workspace] : (await readDirSafe(BRANDS)).filter((d) => d.isDirectory() && !d.name.startsWith("_")).map((d) => d.name);
  const out = [];
  for (const ws of spaces) {
    if (ws === TEMPLATES) continue;
    const wfs = workflow ? [workflow] : (await readDirSafe(path.join(BRANDS, ws, "runs"))).filter((d) => d.isDirectory()).map((d) => d.name);
    for (const wf of wfs) out.push(...(await runsForWorkflow(ws, wf)));
  }
  out.sort((a, b) => String(b.finished || b.started || "").localeCompare(String(a.finished || a.started || "")));
  return out;
}

// Runs that produced something to look at.
export async function recentResults(limit = 12, scope = {}) {
  const runs = await listRuns(scope);
  return runs.filter((r) => r.files.length || (r.items || []).some((i) => i.files.length)).slice(0, limit);
}

// Fan-out runs: anything the runner recorded items[] for.
export async function listBatches(scope = {}) {
  return (await listRuns(scope)).filter((r) => Array.isArray(r.items));
}

// Latest media per capability kind, so a capability card can show a real output. A kind that
// never ran gets nothing, never a stock image.
export async function previewsByKind() {
  const runs = await listRuns();
  const out = {};
  for (const r of runs) {
    const files = r.files.length ? r.files : (r.items || []).flatMap((i) => i.files);
    if (!files.length || out[r.kind]) continue;
    out[r.kind] = { files: files.slice(0, 4), workspace: r.workspace, workflow: r.workflow, run_id: r.run_id, finished: r.finished };
  }
  return out;
}

// Spend to date from manifests. Estimated figures are what the engine planned; measured ones
// are what a run reported. Dry runs planned but spent nothing.
export async function spendSummary() {
  const runs = await listRuns();
  const sum = { estimated_usd: 0, measured_gpu_seconds: 0, live_runs: 0, dry_runs: 0, partial: 0, by_workspace: {} };
  for (const r of runs) {
    const ws = (sum.by_workspace[r.workspace] ||= { estimated_usd: 0, live_runs: 0, dry_runs: 0 });
    if (r.status === "dry-run") { sum.dry_runs++; ws.dry_runs++; continue; }
    if (r.status === "partial") sum.partial++;
    const usd = Number(r.cost_actual?.usd ?? r.cost_estimate?.usd ?? 0);
    sum.estimated_usd += usd; ws.estimated_usd += usd;
    sum.live_runs++; ws.live_runs++;
    if (r.gpu_seconds_actual != null) sum.measured_gpu_seconds += Number(r.gpu_seconds_actual);
  }
  sum.estimated_usd = Math.round(sum.estimated_usd * 10000) / 10000;
  return sum;
}
