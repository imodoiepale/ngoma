// Reference collections: brands/<ws>/references/<name>/ with media files and a collection.json
// the engine reads before it binds a file to any port (packages/engine/references.py,
// packages/engine/brief.py). This module writes that JSON with the exact field names and
// order of brands/_kit/collection.json.example, UTF-8 without a BOM, and never overwrites a
// file. Plain-language rights choices from the intake map onto the engine's three values.
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { REPO, StudioError, TEMPLATES, workflowDir } from "./studio";

const BRANDS = path.join(REPO, "brands");
export const NAME = /^[a-z0-9][a-z0-9-]{1,60}$/;
export const MEDIA_EXT = new Set([".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"]);
export const VIDEO_EXT = new Set([".mp4", ".mov"]);
export const MAX_FILES = 400;
export const MAX_BYTES = 400 * 1024 * 1024;
export const PURPOSES = { persona: "Persona", wardrobe: "Wardrobe", location: "Location", motion: "Motion clip", product: "Product", other: "Other" };

// What the intake asks in plain words, and what the engine reads.
export const RIGHTS_CHOICES = {
  own: { label: "I own these", use: "data", rights: "owned", note: null },
  licensed: { label: "Licensed to this workspace", use: "data", rights: "licensed", note: "licensed: note the licence and whether it covers AI editing or training" },
  fictional: { label: "Fictional character built from owned images", use: "data", rights: "owned", note: "fictional persona built from owned images, no real-person likeness" },
  study: { label: "Study only, never fed to a model", use: "inspiration", rights: "unclear", note: "study only: shapes prompts, never fed to a node port" },
  unsure: { label: "Not sure", use: "inspiration", rights: "unclear", note: "rights not confirmed; inspiration only until a person confirms them" },
};

export function purposeOf(name) {
  const p = String(name).split("-")[0];
  return PURPOSES[p] ? p : "other";
}

export function checkName(name) {
  if (!NAME.test(name || "") || name.includes("..")) throw new StudioError("A collection name is kebab-case: letters, digits and dashes, like persona-amina.");
  return name;
}

export async function refRoot(ws) {
  if (ws === TEMPLATES) throw new StudioError("Templates hold no references.");
  await workflowDir(ws);
  return path.join(BRANDS, ws, "references");
}

export function collectionDir(ws, name) {
  const dir = path.resolve(BRANDS, ws, "references", checkName(name));
  if (!dir.startsWith(path.resolve(BRANDS, ws, "references") + path.sep)) throw new StudioError("That path is not inside the workspace.");
  return dir;
}

async function mediaFiles(dir) {
  try {
    return (await fs.readdir(dir, { withFileTypes: true }))
      .filter((d) => d.isFile() && MEDIA_EXT.has(path.extname(d.name).toLowerCase()))
      .map((d) => d.name).sort();
  } catch {
    return [];
  }
}

export async function readMeta(dir) {
  try {
    const raw = await fs.readFile(path.join(dir, "collection.json"));
    const text = raw.toString("utf8").replace(/^\uFEFF/, "");
    return { meta: JSON.parse(text), bom: raw[0] === 0xef && raw[1] === 0xbb && raw[2] === 0xbf };
  } catch {
    return { meta: null, bom: false };
  }
}

export function thumbUrl(ws, name, file) {
  return `/api/references/thumb?ws=${encodeURIComponent(ws)}&name=${encodeURIComponent(name)}&file=${encodeURIComponent(file)}`;
}

// One collection as the UI shows it. `hashes` adds sha256 of every media file for dedupe.
export async function describeCollection(ws, name, { hashes = false } = {}) {
  const dir = collectionDir(ws, name);
  const files = await mediaFiles(dir);
  const { meta, bom } = await readMeta(dir);
  let bytes = 0;
  const sizes = await Promise.all(files.map((f) => fs.stat(path.join(dir, f)).then((s) => s.size).catch(() => 0)));
  for (const s of sizes) bytes += s;
  const videos = files.filter((f) => VIDEO_EXT.has(path.extname(f).toLowerCase())).length;
  const rights = meta?.rights || "unclear";
  const use = meta?.use || "inspiration";
  const out = {
    name,
    folder: `brands/${ws}/references/${name}`,
    purpose: purposeOf(name),
    kind: meta?.kind || (files.length && videos === files.length ? "video" : "image"),
    use,
    rights,
    consent: meta?.consent === true,
    verified: !!meta,
    bom,
    source: meta?.source || null,
    created: meta?.created || null,
    notes: Array.isArray(meta?.notes) ? meta.notes : [],
    count: files.length,
    images: files.length - videos,
    videos,
    bytes,
    files: files.map((f) => `brands/${ws}/references/${name}/${f}`),
    thumbs: files.slice(0, 6).map((f) => thumbUrl(ws, name, f)),
    // What the engine's gate will say: data with owned/licensed rights feeds ports; else inspiration.
    feeds: use === "data" && (rights === "owned" || rights === "licensed"),
    warning: !meta ? "No collection.json: inspiration only until it has one." : rights === "unclear" ? "Rights unclear: this can shape prompts but cannot feed a step." : (use === "data" && rights === "unclear") ? "use: data with unclear rights is invalid." : null,
  };
  if (hashes) {
    out.hashes = {};
    for (const f of files) {
      try { out.hashes[createHash("sha256").update(await fs.readFile(path.join(dir, f))).digest("hex")] = f; } catch { /* unreadable */ }
    }
  }
  return out;
}

export async function listCollections(ws) {
  const root = await refRoot(ws);
  let dirs = [];
  try { dirs = (await fs.readdir(root, { withFileTypes: true })).filter((d) => d.isDirectory() && NAME.test(d.name)).map((d) => d.name).sort(); } catch { return []; }
  return Promise.all(dirs.map((n) => describeCollection(ws, n)));
}

// The collection.json the engine reads. Field order follows brands/_kit/collection.json.example.
export function buildMeta({ name, choice, realPerson, releaseFile, releaseNote, kind, extraNotes = [], existing = null }) {
  const c = RIGHTS_CHOICES[choice];
  if (!c) throw new StudioError("Pick how these may be used.");
  const notes = [];
  if (c.note) notes.push(c.note);
  let consent = false;
  if (realPerson) {
    if (releaseFile || releaseNote) {
      consent = true;
      notes.push(`release: ${releaseFile ? `kept at references/${name}/${releaseFile}` : releaseNote}`);
    } else {
      notes.push("a real person is shown and no written release is on file yet; cannot feed a face or character port");
    }
  } else if (choice === "own" || choice === "licensed") {
    notes.push("no real-person likeness");
  }
  for (const n of extraNotes) if (typeof n === "string" && n.trim()) notes.push(n.trim().slice(0, 300));
  return {
    name,
    use: c.use,
    rights: c.rights,
    kind,
    consent,
    source: existing?.source || "studio-intake",
    created: existing?.created || new Date().toLocaleDateString("sv-SE"),
    notes,
  };
}

export async function writeMeta(dir, meta) {
  // JSON.stringify never emits a BOM; writing a string with utf8 keeps it that way.
  await fs.writeFile(path.join(dir, "collection.json"), JSON.stringify(meta, null, 2) + "\n", { encoding: "utf8" });
}

function safeBase(original) {
  const ext = path.extname(original).toLowerCase();
  const stem = path.basename(original, path.extname(original)).toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "file";
  return { stem, ext };
}

// Save uploaded files into a collection folder. Existing files are never overwritten: a byte-
// identical upload is skipped, a same-named different file gets a numbered suffix.
export async function saveFiles(dir, files) {
  await fs.mkdir(dir, { recursive: true });
  const existing = new Set();
  for (const f of await mediaFiles(dir)) {
    try { existing.add(createHash("sha256").update(await fs.readFile(path.join(dir, f))).digest("hex")); } catch { /* skip */ }
  }
  const saved = [], skipped = [], rejected = [];
  let total = 0;
  for (const file of files) {
    const { stem, ext } = safeBase(file.name || "file");
    if (!MEDIA_EXT.has(ext)) { rejected.push({ name: file.name, why: `${ext || "no extension"} is not an image or video the engine reads (png, jpg, webp, mp4, mov)` }); continue; }
    const buf = Buffer.from(await file.arrayBuffer());
    if (!buf.length) { rejected.push({ name: file.name, why: "empty file" }); continue; }
    total += buf.length;
    if (total > MAX_BYTES) { rejected.push({ name: file.name, why: `over the ${Math.round(MAX_BYTES / 1024 / 1024)} MB cap for one upload` }); continue; }
    const hash = createHash("sha256").update(buf).digest("hex");
    if (existing.has(hash)) { skipped.push({ name: file.name, why: "already in the collection (same content)" }); continue; }
    let target = `${stem}${ext}`;
    for (let i = 2; i < 1000; i++) {
      try { await fs.access(path.join(dir, target)); target = `${stem}-${i}${ext}`; } catch { break; }
    }
    await fs.writeFile(path.join(dir, target), buf, { flag: "wx" });
    existing.add(hash);
    saved.push(target);
  }
  return { saved, skipped, rejected };
}

export async function saveRelease(dir, file, name) {
  if (!file || !file.size) return null;
  const ext = path.extname(file.name || "").toLowerCase().replace(/[^a-z0-9.]/g, "") || ".pdf";
  if (![".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md"].includes(ext)) throw new StudioError("A release is a PDF, image or text file.");
  if (file.size > 25 * 1024 * 1024) throw new StudioError("A release file is under 25 MB.");
  const target = `RELEASE-${name}${ext}`;
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(dir, target), Buffer.from(await file.arrayBuffer()), { flag: "w" });
  return target;
}
