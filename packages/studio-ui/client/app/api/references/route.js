import fs from "node:fs/promises";
import { StudioError } from "../../../lib/studio";
import {
  MAX_FILES, PURPOSES, RIGHTS_CHOICES, buildMeta, checkName, collectionDir, describeCollection, listCollections,
  readMeta, refRoot, saveFiles, saveRelease, writeMeta,
} from "../../../lib/references";

export const dynamic = "force-dynamic";

function fail(e) {
  const status = e instanceof StudioError ? e.status : 400;
  return Response.json({ error: e.message || "Could not do that." }, { status });
}

// GET ?ws=<workspace>              every collection with thumbnails and counts
// GET ?ws=<workspace>&name=<name>  one collection; &hashes=1 adds sha256 per file for dedupe
export async function GET(request) {
  const q = new URL(request.url).searchParams;
  try {
    const ws = q.get("ws") || "";
    await refRoot(ws);
    if (q.get("name")) return Response.json({ collection: await describeCollection(ws, checkName(q.get("name")), { hashes: q.get("hashes") === "1" }) });
    return Response.json({ collections: await listCollections(ws), purposes: PURPOSES, choices: Object.fromEntries(Object.entries(RIGHTS_CHOICES).map(([k, v]) => [k, v.label])) });
  } catch (e) {
    return fail(e);
  }
}

// POST multipart/form-data: ws, name (purpose-name), files[] (png jpg webp mp4 mov), and for a
// new collection or a rights change: choice (own|licensed|fictional|study|unsure),
// real_person (true|false), release (file, optional), release_note, notes (one per line).
// Adding files to an existing collection keeps its collection.json unless a choice is sent.
// Nothing is overwritten; identical files are skipped; names get a numbered suffix.
export async function POST(request) {
  try {
    const form = await request.formData();
    const ws = String(form.get("ws") || "");
    const name = checkName(String(form.get("name") || "").trim().toLowerCase());
    await refRoot(ws);
    const dir = collectionDir(ws, name);
    const files = form.getAll("files").filter((f) => typeof f === "object" && f && "arrayBuffer" in f);
    if (files.length > MAX_FILES) throw new StudioError(`At most ${MAX_FILES} files in one upload.`);
    const { meta: existing } = await readMeta(dir);
    const choice = String(form.get("choice") || "");
    if (!existing && !choice) throw new StudioError("Say how these may be used before the collection is created.");
    if (!existing && !files.length) throw new StudioError("Add at least one image or clip.");

    const saved = files.length ? await saveFiles(dir, files) : { saved: [], skipped: [], rejected: [] };
    if (!existing && !saved.saved.length) {
      // nothing usable landed: do not leave an empty folder behind
      try { await fs.rm(dir, { recursive: true, force: true }); } catch { /* fine */ }
      throw new StudioError(saved.rejected[0]?.why || "None of those files could be added.");
    }
    let meta = existing;
    if (choice || !existing) {
      const realPerson = String(form.get("real_person") || "") === "true";
      const release = form.get("release");
      const releaseFile = realPerson ? await saveRelease(dir, typeof release === "object" ? release : null, name) : null;
      const current = await describeCollection(ws, name);
      meta = buildMeta({
        name, choice: choice || "unsure", realPerson, releaseFile, releaseNote: String(form.get("release_note") || "").trim(),
        kind: current.videos && current.videos === current.count ? "video" : "image",
        extraNotes: String(form.get("notes") || "").split(/\r?\n/), existing,
      });
      await writeMeta(dir, meta);
    }
    const collection = await describeCollection(ws, name);
    return Response.json({ ok: true, collection, ...saved, created: !existing }, { status: existing ? 200 : 201 });
  } catch (e) {
    return fail(e);
  }
}

// PATCH JSON { ws, name, choice, real_person, release_note, notes[] }: rewrite the rights of a
// collection (the "unclear" chip on a node opens this). Files are untouched.
export async function PATCH(request) {
  try {
    const body = await request.json().catch(() => ({}));
    const ws = String(body.ws || "");
    const name = checkName(String(body.name || ""));
    await refRoot(ws);
    const dir = collectionDir(ws, name);
    const { meta: existing } = await readMeta(dir);
    const current = await describeCollection(ws, name);
    if (!current.count && !existing) throw new StudioError("There is no collection by that name.");
    const meta = buildMeta({
      name, choice: body.choice, realPerson: body.real_person === true, releaseFile: null,
      releaseNote: String(body.release_note || "").trim(), kind: current.videos && current.videos === current.count ? "video" : "image",
      extraNotes: Array.isArray(body.notes) ? body.notes : [], existing,
    });
    await writeMeta(dir, meta);
    return Response.json({ ok: true, collection: await describeCollection(ws, name) });
  } catch (e) {
    return fail(e);
  }
}
