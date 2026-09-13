// Server-side access to the studio's clients and workflows. The files in the repo are the
// database: brands/<client>/workflows/*.studio.json, written by this app and by
// packages/strategy/workflow_author.py alike. Validation here mirrors the Python author's,
// so a workflow saved from the canvas is one the author can also read.
import fs from "node:fs/promises";
import path from "node:path";

export const REPO = process.env.STUDIO_REPO || path.resolve(process.cwd(), "../../..");
const BRANDS = path.join(REPO, "brands");
export const TEMPLATES = "_templates";
const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;

export class StudioError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

export async function loadCatalog() {
  const raw = await fs.readFile(path.join(REPO, "packages/studio-ui/catalog/nodes.json"), "utf8");
  return JSON.parse(raw);
}

function brandInfo(yamlText, id) {
  const lines = yamlText.split(/\r?\n/);
  let name = lines.find((l) => /^(name|display_name):\s*\S/.test(l));
  if (!name) {
    const b = lines.findIndex((l) => /^brand:\s*$/.test(l));
    if (b >= 0) name = lines.slice(b + 1).find((l) => /^\s+name:\s*\S/.test(l));
  }
  const clean = name ? name.split(":").slice(1).join(":").split("#")[0].trim().replace(/^["']|["']$/g, "") : "";
  const accent = (yamlText.match(/accent[a-z_]*:\s*["']?(#[0-9A-Fa-f]{6})/) || [])[1];
  return {
    name: clean || id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    accent: accent || "#C9A45C",
  };
}

export async function workflowDir(client) {
  if (client === TEMPLATES) return path.join(BRANDS, TEMPLATES, "workflows");
  if (!ID.test(client || "")) throw new StudioError("That client id is not valid.");
  try {
    await fs.access(path.join(BRANDS, client, "brand.yaml"));
  } catch {
    throw new StudioError(`There is no client called ${client}.`, 404);
  }
  return path.join(BRANDS, client, "workflows");
}

export async function getClient(client) {
  if (client === TEMPLATES) return { id: TEMPLATES, name: "Idea templates", accent: "#C9A45C", templates: true };
  await workflowDir(client);
  const yamlText = await fs.readFile(path.join(BRANDS, client, "brand.yaml"), "utf8");
  return { id: client, ...brandInfo(yamlText, client) };
}

export async function listClients() {
  const entries = await fs.readdir(BRANDS, { withFileTypes: true });
  const out = [];
  for (const e of entries) {
    if (!e.isDirectory() || e.name.startsWith("_")) continue;
    try {
      const c = await getClient(e.name);
      out.push({ ...c, workflows: await listWorkflows(e.name) });
    } catch {
      // folders without brand.yaml are not clients
    }
  }
  return out;
}

export async function listWorkflows(client) {
  const dir = await workflowDir(client);
  let files = [];
  try {
    files = (await fs.readdir(dir)).filter((f) => f.endsWith(".studio.json")).sort();
  } catch {
    return [];
  }
  const out = [];
  for (const f of files) {
    try {
      const wf = JSON.parse(await fs.readFile(path.join(dir, f), "utf8"));
      out.push({
        id: f.replace(/\.studio\.json$/, ""),
        title: wf.title,
        family: wf.family || null,
        source: wf.source || {},
        nodes: wf.nodes.length,
        gaps: (wf.gaps || []).length,
        consent: !!wf.consent_required,
        kinds: wf.nodes.map((n) => n.kind),
        combined: !!(wf.source && wf.source.combined),
      });
    } catch {
      out.push({ id: f.replace(/\.studio\.json$/, ""), title: f, broken: true, kinds: [], nodes: 0, gaps: 0 });
    }
  }
  return out;
}

export async function readWorkflow(client, id) {
  if (!ID.test(id || "")) throw new StudioError("That workflow id is not valid.");
  const dir = await workflowDir(client);
  try {
    return JSON.parse(await fs.readFile(path.join(dir, `${id}.studio.json`), "utf8"));
  } catch {
    throw new StudioError(`There is no workflow called ${id} for ${client}.`, 404);
  }
}

function accepts(port, outType, catalog) {
  if (port.id === "media") return catalog.media_ports.accepts.includes(outType);
  return port.type === outType;
}

export function validateWorkflow(wf, catalog) {
  const problems = [];
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  if (!wf || !Array.isArray(wf.nodes) || !Array.isArray(wf.edges)) return ["A workflow needs nodes and links."];
  const ids = new Map(wf.nodes.map((n) => [n.id, n]));
  if (ids.size !== wf.nodes.length) problems.push("Two nodes share an id.");
  const declared = new Set((wf.gaps || []).map((g) => g.node));
  for (const n of wf.nodes) {
    if (n.kind === "unmapped") {
      if (!declared.has(n.id)) problems.push(`${n.id}: an unmapped step must be listed as a gap.`);
      continue;
    }
    const spec = byKind[n.kind];
    if (!spec) problems.push(`${n.id}: unknown node type ${n.kind}.`);
    else if (spec.backend.kind === "gap" && !declared.has(n.id)) problems.push(`${n.id}: ${spec.label} cannot run yet and must be listed as a gap.`);
  }
  for (const e of wf.edges) {
    const s = ids.get(e.source), t = ids.get(e.target);
    if (!s || !t) { problems.push(`${e.id}: a link points at a missing node.`); continue; }
    const ss = byKind[s.kind], ts = byKind[t.kind];
    if (!ss || !ts) continue;
    const out = ss.outputs.find((o) => o.id === e.sourceHandle);
    const port = ts.inputs.find((p) => p.id === e.targetHandle);
    if (!out || !port) problems.push(`${e.id}: a link uses a port that does not exist.`);
    else if (!accepts(port, out.type, catalog)) problems.push(`${e.id}: ${out.type} cannot feed ${ts.label} ${port.id}.`);
  }
  return problems;
}

// Gaps are recomputed on save so the file always states what cannot run.
export function computeGaps(wf, catalog) {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const gaps = [];
  for (const n of wf.nodes) {
    if (n.kind === "unmapped") {
      gaps.push({ node: n.id, step: n.data?.step || "unmapped", reason: `No catalogue node runs '${n.data?.step}' yet.` });
      continue;
    }
    const spec = byKind[n.kind];
    if (!spec) continue;
    if (spec.backend.kind === "gap") gaps.push({ node: n.id, step: n.kind, reason: spec.backend.reason });
    for (const p of spec.inputs) {
      if (p.optional) continue;
      if (!wf.edges.some((e) => e.target === n.id && e.targetHandle === p.id)) {
        gaps.push({ node: n.id, step: n.kind, reason: `Needs a ${p.id === "media" ? "image or video" : p.type} input.` });
      }
    }
  }
  return gaps;
}

export async function writeWorkflow(client, id, wf) {
  if (!ID.test(id || "")) throw new StudioError("That workflow id is not valid.");
  const dir = await workflowDir(client);
  const catalog = await loadCatalog();
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const clean = {
    ...wf,
    id,
    client,
    version: 1,
    gaps: computeGaps(wf, catalog),
    consent_required: wf.nodes.some((n) => byKind[n.kind]?.consent),
    updated: new Date().toISOString().slice(0, 10),
  };
  const problems = validateWorkflow(clean, catalog);
  if (problems.length) throw new StudioError(problems.join(" "));
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(dir, `${id}.studio.json`), JSON.stringify(clean, null, 2) + "\n", "utf8");
  return clean;
}

// What would happen if this ran. Nothing is executed and nothing is spent.
export function runPlan(wf, catalog) {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const gaps = computeGaps(wf, catalog);
  const steps = wf.nodes.map((n) => {
    const spec = byKind[n.kind];
    const nodeGaps = gaps.filter((g) => g.node === n.id).map((g) => g.reason);
    if (!spec) return { id: n.id, label: n.data?.step || n.kind, status: "blocked", detail: nodeGaps.join(" ") };
    const be = spec.backend;
    const runs = {
      input: "You provide this.",
      brand: "Read from brand.yaml.",
      comfy: `ComfyUI: workflows/${be.workflow}`,
      router: `Hosted model, profile ${n.data?.params?.profile || be.profile}.`,
      python: `Runs ${be.module}.`,
      publish: `Creates a draft through ${be.module}.`,
      gap: be.reason,
    }[be.kind];
    const status = nodeGaps.length ? "blocked" : be.kind === "input" ? "input" : "ready";
    return { id: n.id, label: spec.label, status, detail: nodeGaps.length ? nodeGaps.join(" ") : runs, consent: !!spec.consent, backend: be.kind };
  });
  return {
    steps,
    ready: steps.filter((s) => s.status === "ready").length,
    blocked: steps.filter((s) => s.status === "blocked").length,
    consent: steps.some((s) => s.consent),
    note: "Check only. Nothing runs, spends money or publishes from this screen.",
  };
}
