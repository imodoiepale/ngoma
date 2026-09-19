// Server-side access to the studio's workspaces and workflows. The files in the repo are the
// database: brands/<workspace>/workflows/*.studio.json, written by this app and by
// packages/strategy/workflow_author.py alike. Validation here mirrors the Python author's,
// so a workflow saved from the canvas is one the author can also read.
//
// "client" and "workspace" name the same thing (a folder under brands/ with a brand.yaml);
// the older name survives in function names the API routes depend on.
import fs from "node:fs/promises";
import path from "node:path";
import { parseYaml, dig } from "./yaml-lite";
import { isEach, validateWorkflow, computeGaps } from "./graph";

export const REPO = process.env.STUDIO_REPO || path.resolve(process.cwd(), "../../..");
const BRANDS = path.join(REPO, "brands");
export const TEMPLATES = "_templates";
const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;
const IMAGE = /\.(png|jpe?g|webp)$/i;
const VIDEO = /\.(mp4|webm|mov)$/i;
const DEFAULT_ACCENT = "#C9A45C";

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

// Pure graph logic (the validation mirror, gaps, plan, tool inputs) lives in ./graph so the
// canvas can run it in the browser too.
export { RUN_MODES, EACH_BACKENDS, EACH_SUFFIX, splitEach, isEach, iteratedPort, canEach, pendingPicks, validateWorkflow, computeGaps, toolInputs, runPlan, continuationsFor } from "./graph";

// ---------------------------------------------------------------- workspaces

function relLuminance(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return 0;
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(m[1].slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function pickAccent(brand) {
  const flat = [];
  const walk = (o, keyPath) => {
    if (!o || typeof o !== "object") return;
    for (const [k, v] of Object.entries(o)) {
      if (typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v)) flat.push([`${keyPath}${k}`.toLowerCase(), v]);
      else if (v && typeof v === "object" && !Array.isArray(v)) walk(v, `${keyPath}${k}.`);
    }
  };
  walk(brand.palette || {}, "");
  const byKey = (re) => flat.find(([k]) => re.test(k.split(".").pop()))?.[1];
  const usable = (hex) => hex && relLuminance(hex) > 0.09 && relLuminance(hex) < 0.85;
  const cands = [byKey(/^(ui_)?accent$/), byKey(/^primary$/), byKey(/gold|emerald|mint|cyan|accent/)].filter(usable);
  return cands[0] || DEFAULT_ACCENT;
}

function brandInfo(yamlText, id) {
  let brand = {};
  try { brand = parseYaml(yamlText) || {}; } catch { brand = {}; }
  const name = brand.display_name || brand.name || dig(brand, "brand.name");
  const accent = pickAccent(brand);
  const palette = [];
  const measured = dig(brand, "palette.measured");
  if (measured && typeof measured === "object") {
    for (const [k, v] of Object.entries(measured)) if (typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v)) palette.push({ key: k, hex: v });
  }
  const langs = dig(brand, "languages.supported");
  return {
    name: typeof name === "string" && name ? name : id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    accent,
    accentInk: relLuminance(accent) > 0.35 ? "#15120b" : "#f7f4ee",
    kind: typeof brand.kind === "string" ? brand.kind : (brand.product ? "product" : "brand"),
    tagline: dig(brand, "positioning.tagline") || dig(brand, "positioning.premise") || brand.product || "",
    logo: dig(brand, "logo.master") || null,
    logoRule: dig(brand, "logo.rule") || null,
    palette: palette.slice(0, 8),
    languages: Array.isArray(langs) ? langs.map(String) : [],
    disclosure: dig(brand, "claim_safety.disclosure") || null,
    // The 18+ gate: a workspace opts in explicitly in its brand.yaml. Nothing else enables it.
    adult: brand.adult === true || brand.allow_adult === true || brand.eighteen_plus === true,
  };
}

export async function workflowDir(client) {
  if (client === TEMPLATES) return path.join(BRANDS, TEMPLATES, "workflows");
  if (!ID.test(client || "")) throw new StudioError("That workspace id is not valid.");
  try {
    await fs.access(path.join(BRANDS, client, "brand.yaml"));
  } catch {
    throw new StudioError(`There is no workspace called ${client}.`, 404);
  }
  return path.join(BRANDS, client, "workflows");
}

export async function getClient(client) {
  if (client === TEMPLATES) {
    return { id: TEMPLATES, name: "Templates", accent: DEFAULT_ACCENT, accentInk: "#15120b", templates: true, adult: false, palette: [], languages: [] };
  }
  await workflowDir(client);
  const yamlText = await fs.readFile(path.join(BRANDS, client, "brand.yaml"), "utf8");
  return { id: client, ...brandInfo(yamlText, client) };
}

export const getWorkspace = getClient;

export async function listClients() {
  const entries = await fs.readdir(BRANDS, { withFileTypes: true });
  const out = [];
  for (const e of entries) {
    if (!e.isDirectory() || e.name.startsWith("_")) continue;
    try {
      const c = await getClient(e.name);
      out.push({ ...c, workflows: await listWorkflows(e.name) });
    } catch {
      // folders without brand.yaml are not workspaces
    }
  }
  return out;
}

export const listWorkspaces = listClients;

// Reference collections: brands/<ws>/references/<name>/ with a collection.json that states
// use, rights and consent. A folder without one is listed as unverified.
export async function listReferences(client) {
  if (client === TEMPLATES) return [];
  await workflowDir(client);
  const root = path.join(BRANDS, client, "references");
  let dirs = [];
  try { dirs = (await fs.readdir(root, { withFileTypes: true })).filter((d) => d.isDirectory()); } catch { return []; }
  const out = [];
  for (const d of dirs) {
    const folder = path.join(root, d.name);
    let meta = null;
    try { meta = JSON.parse(await fs.readFile(path.join(folder, "collection.json"), "utf8")); } catch { meta = null; }
    let files = [];
    try { files = (await fs.readdir(folder)).filter((f) => IMAGE.test(f) || VIDEO.test(f)).sort(); } catch { files = []; }
    out.push({
      name: d.name,
      folder: `brands/${client}/references/${d.name}`,
      count: files.length,
      files: files.slice(0, 6).map((f) => `brands/${client}/references/${d.name}/${f}`),
      kind: meta?.kind || (files.some((f) => VIDEO.test(f)) ? "video" : "image"),
      use: meta?.use || null,
      rights: meta?.rights || null,
      consent: meta?.consent === true,
      verified: !!meta,
      notes: Array.isArray(meta?.notes) ? meta.notes : [],
    });
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
        adult: wf.family === "adult" || !!wf.source?.engine?.adult,
        kinds: wf.nodes.map((n) => n.kind),
        each: wf.nodes.filter((n) => isEach(n)).length,
        combined: !!(wf.source && wf.source.combined),
        tool: wf.tool?.enabled ? { title: wf.tool.title || wf.title, inputs: (wf.tool.inputs || []).length } : null,
        updated: wf.updated || wf.created || null,
      });
    } catch {
      out.push({ id: f.replace(/\.studio\.json$/, ""), title: f, broken: true, kinds: [], nodes: 0, gaps: 0, each: 0 });
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

export async function writeWorkflow(client, id, wf) {
  if (!ID.test(id || "")) throw new StudioError("That workflow id is not valid.");
  const dir = await workflowDir(client);
  const catalog = await loadCatalog();
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const clean = {
    ...wf,
    id,
    client,
    version: wf.version === 2 ? 2 : 1,
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
