"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export const PURPOSES = [["persona", "Persona"], ["wardrobe", "Wardrobe"], ["location", "Location"], ["motion", "Motion clip"], ["product", "Product"], ["other", "Other"]];
export const CHOICES = [
  ["own", "I own these", "Photos or clips this workspace shot or made. They may feed any step."],
  ["licensed", "Licensed to this workspace", "Bought or downloaded under a licence that covers AI editing. They may feed any step."],
  ["fictional", "Fictional character built from owned images", "A generated persona or mascot. Nobody real is shown, so no release is needed."],
  ["study", "Study only, never fed to a model", "Other people's work you learn from. It shapes prompts and never reaches a step."],
  ["unsure", "Not sure", "Kept as inspiration until someone confirms the rights."],
];
const MEDIA = /\.(png|jpe?g|webp|mp4|mov)$/i;
const VIDEO = /\.(mp4|mov)$/i;
const RIGHTS_LABEL = { owned: "Owned", licensed: "Licensed", unclear: "Rights unclear" };

export function rightsChip(col) {
  if (!col) return null;
  if (!col.verified) return { cls: "chip-gap", text: "Unverified", warn: true };
  if (col.rights === "unclear") return { cls: "chip-needs-setup", text: "Rights unclear", warn: true };
  return { cls: col.consent ? "chip-ready" : "chip-ready", text: `${RIGHTS_LABEL[col.rights]}${col.consent ? ", consent" : ""}`, warn: false };
}

export function fmtBytes(n) {
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  return `${(n / 1024 / 1024).toFixed(n > 100 * 1024 * 1024 ? 0 : 1)} MB`;
}

function slug(s) {
  return String(s).toLowerCase().replace(/\.[a-z0-9]+$/, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}

async function sha256(file) {
  const buf = await file.arrayBuffer();
  const h = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Files out of a drop that may include whole folders (webkitGetAsEntry) or a directory handle
// from showDirectoryPicker. Returns [{file, folder}] with only media the engine reads.
async function filesFromDrop(dt) {
  const out = [];
  const items = dt.items ? [...dt.items] : [];
  const entries = items.map((it) => (it.webkitGetAsEntry ? it.webkitGetAsEntry() : null));
  if (entries.some(Boolean)) {
    const walk = (entry, folder) => new Promise((resolve) => {
      if (entry.isFile) entry.file((f) => { if (MEDIA.test(f.name)) out.push({ file: f, folder }); resolve(); }, () => resolve());
      else if (entry.isDirectory) {
        const reader = entry.createReader();
        const all = [];
        const read = () => reader.readEntries(async (batch) => {
          if (!batch.length) { for (const e of all) await walk(e, folder || entry.name); resolve(); return; }
          all.push(...batch); read();
        }, () => resolve());
        read();
      } else resolve();
    });
    for (const e of entries) if (e) await walk(e, null);
    return out;
  }
  for (const f of dt.files || []) if (MEDIA.test(f.name)) out.push({ file: f, folder: null });
  return out;
}

async function filesFromHandle(dir, folder = dir.name, out = []) {
  for await (const [, h] of dir.entries()) {
    if (h.kind === "file") { const f = await h.getFile(); if (MEDIA.test(f.name)) out.push({ file: f, folder }); }
    else if (h.kind === "directory") await filesFromHandle(h, folder, out);
  }
  return out;
}

// The reference intake. Pick an existing collection from a grid, or drop files and a folder,
// name it by purpose, say who owns it, and save. Writes brands/<ws>/references/<name>/ with a
// collection.json through /api/references; nobody edits JSON or types a path.
export default function ReferenceIntake({ workspace, initial = {}, onClose, onDone }) {
  const [tab, setTab] = useState(initial.mode === "new" || initial.files?.length ? "new" : initial.mode === "fix" ? "fix" : "pick");
  const [cols, setCols] = useState(null);
  const [selected, setSelected] = useState(initial.collection || null);
  const [target, setTarget] = useState(initial.mode === "add" || initial.mode === "fix" ? initial.collection : null); // adding to an existing one
  const [existingHashes, setExistingHashes] = useState({});
  const [files, setFiles] = useState([]);
  const [hashing, setHashing] = useState(0);
  const [purpose, setPurpose] = useState(initial.purpose || "persona");
  const [stem, setStem] = useState(initial.name || "");
  const [choice, setChoice] = useState(initial.mode === "fix" ? "" : (initial.purpose === "motion" ? "own" : ""));
  const [realPerson, setRealPerson] = useState(false);
  const [release, setRelease] = useState(null);
  const [releaseNote, setReleaseNote] = useState("");
  const [notes, setNotes] = useState("");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const fileInput = useRef(null), dirInput = useRef(null);

  const addFilesRef = useRef(null);
  const seeded = useRef(false);

  useEffect(() => {
    let alive = true;
    fetch(`/api/references?ws=${encodeURIComponent(workspace)}`)
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!alive) return;
        setCols(res.ok ? data.collections : []);
        if (!res.ok) setError(data.error || "Could not list the references.");
        // files dropped on a node or panel before the dialog opened
        if (initial.files?.length && !seeded.current) {
          seeded.current = true;
          addFilesRef.current?.([...initial.files].filter((f) => MEDIA.test(f.name)).map((file) => ({ file, folder: null })));
        }
      })
      .catch(() => { if (alive) setError("Could not reach the studio."); });
    return () => { alive = false; };
  }, [workspace, initial.files]);

  // Adding to an existing collection: its file hashes, so duplicates show before upload.
  const chooseTarget = (name) => { setTarget(name); setExistingHashes({}); };
  useEffect(() => {
    if (!target) return undefined;
    let alive = true;
    fetch(`/api/references?ws=${encodeURIComponent(workspace)}&name=${encodeURIComponent(target)}&hashes=1`).then((r) => r.json()).then((d) => { if (alive) setExistingHashes(d.collection?.hashes || {}); }).catch(() => {});
    return () => { alive = false; };
  }, [target, workspace]);

  const addFiles = useCallback(async (list) => {
    if (!list.length) return;
    const folder = list.find((x) => x.folder)?.folder;
    if (folder && !stem) setStem(slug(folder));
    setHashing((h) => h + list.length);
    const seen = new Set(files.map((f) => f.hash).filter(Boolean));
    const next = [];
    for (const { file } of list) {
      let hash = null;
      try { hash = await sha256(file); } catch { hash = null; }
      const dup = hash ? seen.has(hash) || !!existingHashes[hash] : false;
      if (hash) seen.add(hash);
      next.push({ file, hash, dup, video: VIDEO.test(file.name), size: file.size, url: file.type.startsWith("image/") ? URL.createObjectURL(file) : null });
      setHashing((h) => h - 1);
    }
    setFiles((f) => f.concat(next));
  }, [files, stem, existingHashes]);
  useEffect(() => { addFilesRef.current = addFiles; }, [addFiles]);

  async function pickDirectory() {
    if (window.showDirectoryPicker) {
      try { const dir = await window.showDirectoryPicker({ mode: "read" }); addFiles(await filesFromHandle(dir)); return; } catch (e) { if (e?.name === "AbortError") return; }
    }
    dirInput.current?.click();
  }

  const fresh = files.filter((f) => !f.dup);
  const counts = useMemo(() => ({
    images: fresh.filter((f) => !f.video).length, videos: fresh.filter((f) => f.video).length,
    bytes: fresh.reduce((s, f) => s + f.size, 0), dups: files.length - fresh.length,
  }), [files, fresh]);
  const name = target || (purpose === "other" ? slug(stem) : `${purpose}-${slug(stem)}`);
  const nameOk = /^[a-z0-9][a-z0-9-]{1,60}$/.test(name) && !name.endsWith("-");
  const existsByName = !!cols?.some((c) => c.name === name);
  const needChoice = tab === "fix" || (!target && !existsByName);
  const canSave = !busy && nameOk && (tab === "fix" ? !!choice : fresh.length > 0 && (!needChoice || !!choice)) && hashing === 0;

  function submit() {
    setBusy(true); setError(""); setProgress(0);
    const fd = new FormData();
    fd.set("ws", workspace); fd.set("name", name);
    for (const f of fresh) fd.append("files", f.file, f.file.name);
    if (needChoice) {
      fd.set("choice", choice); fd.set("real_person", String(realPerson));
      if (release) fd.set("release", release, release.name);
      fd.set("release_note", releaseNote); fd.set("notes", notes);
    }
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/references");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => {
      setBusy(false);
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { data = {}; }
      if (xhr.status >= 400) { setError(data.error || "Could not save the collection."); return; }
      setResult(data);
      onDone?.(data.collection, data);
    };
    xhr.onerror = () => { setBusy(false); setError("The upload failed. Check the dev server is running."); };
    xhr.send(fd);
  }

  const expected = initial.expected;
  const chosen = cols?.find((c) => c.name === selected) || null;

  return (
    <div className="cmdk-backdrop" onMouseDown={onClose} role="presentation">
      <div className="cmdk intake" role="dialog" aria-modal="true" aria-label="References" onMouseDown={(e) => e.stopPropagation()}>
        <div className="intake-head">
          <div>
            <h3>{tab === "fix" ? `Fix rights for ${target}` : target ? `Add to ${target}` : "References"}</h3>
            {expected && <p className="muted">{expected.prompt || "This step needs references."}{expected.count ? ` About ${expected.count} ${expected.kind === "video" ? "clips" : "images"}.` : ""}</p>}
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">x</button>
        </div>
        {tab !== "fix" && !target && (
          <div className="intake-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === "pick"} className={tab === "pick" ? "is-on" : ""} onClick={() => setTab("pick")}>Pick a collection{cols ? ` (${cols.length})` : ""}</button>
            <button type="button" role="tab" aria-selected={tab === "new"} className={tab === "new" ? "is-on" : ""} onClick={() => setTab("new")}>New collection</button>
          </div>
        )}

        <div className="intake-body">
          {tab === "pick" && !target && (
            <>
              {cols === null && <p className="muted">Reading the references folder.</p>}
              {cols?.length === 0 && <div className="empty"><b>No collections yet.</b>Start a new one: drop a folder of photos and say who owns them.</div>}
              <div className="ref-grid">
                {(cols || []).map((c) => {
                  const chip = rightsChip(c);
                  return (
                    <button key={c.name} type="button" className={`ref-card${selected === c.name ? " is-on" : ""}`} onClick={() => setSelected(c.name)} aria-pressed={selected === c.name}>
                      <span className="ref-stack">
                        {c.thumbs.slice(0, 3).map((t, i) => (VIDEO.test(t) ? <video key={i} src={t} muted preload="metadata" /> : <img key={i} src={t} alt="" loading="lazy" />))}
                        {!c.thumbs.length && <span className="ref-empty">empty</span>}
                        <span className="count-badge">{c.count}</span>
                      </span>
                      <span className="ref-title">{c.name}</span>
                      <span className="ref-sub">{c.images ? `${c.images} images` : ""}{c.images && c.videos ? ", " : ""}{c.videos ? `${c.videos} clips` : ""}{c.count ? `, ${fmtBytes(c.bytes)}` : ""}</span>
                      <span className={`chip ${chip.cls}`}>{chip.text}</span>
                    </button>
                  );
                })}
              </div>
              {chosen && (
                <div className="intake-chosen">
                  <div>
                    <b>{chosen.name}</b> <span className="muted">{chosen.use === "data" ? "may feed a step" : "shapes prompts only"}{chosen.notes[0] ? `. ${chosen.notes[0]}` : ""}</span>
                    {chosen.warning && <p className="notice">{chosen.warning}</p>}
                  </div>
                  <div className="creator-actions" style={{ marginTop: 0 }}>
                    {rightsChip(chosen).warn && <button type="button" className="btn btn-quiet btn-sm" onClick={() => { chooseTarget(chosen.name); setTab("fix"); }}>Fix rights</button>}
                    <button type="button" className="btn btn-sm" onClick={() => { chooseTarget(chosen.name); setTab("new"); }}>Add files</button>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => { onDone?.(chosen, { picked: true }); }}>Use this collection</button>
                  </div>
                </div>
              )}
            </>
          )}

          {(tab === "new") && (
            <>
              <div className={`dropzone${over ? " is-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                onDrop={async (e) => { e.preventDefault(); setOver(false); addFiles(await filesFromDrop(e.dataTransfer)); }}>
                <p><b>Drop images, clips or a whole folder here</b></p>
                <p className="muted">png, jpg, webp, mp4, mov. Duplicates are skipped by content, so dropping the same folder twice adds nothing.</p>
                <div className="pick-list" style={{ justifyContent: "center" }}>
                  <button type="button" className="btn btn-sm" onClick={pickDirectory}>Choose a folder</button>
                  <button type="button" className="btn btn-sm btn-quiet" onClick={() => fileInput.current?.click()}>Choose files</button>
                </div>
                <input ref={fileInput} type="file" multiple accept=".png,.jpg,.jpeg,.webp,.mp4,.mov,image/*,video/mp4,video/quicktime" hidden onChange={(e) => addFiles([...e.target.files].map((file) => ({ file, folder: null })))} />
                <input ref={dirInput} type="file" multiple webkitdirectory="" hidden onChange={(e) => { const list = [...e.target.files]; const folder = list[0]?.webkitRelativePath?.split("/")[0] || null; addFiles(list.map((file) => ({ file, folder }))); }} />
              </div>
              {files.length > 0 && (
                <div className="intake-files">
                  <div className="count-line">
                    <span className="count-badge big">{counts.images ? `${counts.images} image${counts.images === 1 ? "" : "s"}` : ""}{counts.images && counts.videos ? ", " : ""}{counts.videos ? `${counts.videos} clip${counts.videos === 1 ? "" : "s"}` : ""}{fresh.length ? `, ${fmtBytes(counts.bytes)}` : "nothing new"}</span>
                    {counts.dups > 0 && <span className="chip chip-needs-setup">{counts.dups} duplicate{counts.dups === 1 ? "" : "s"} skipped</span>}
                    {hashing > 0 && <span className="muted">checking {hashing}</span>}
                    <button type="button" className="btn btn-quiet btn-sm" style={{ marginLeft: "auto" }} onClick={() => { files.forEach((f) => f.url && URL.revokeObjectURL(f.url)); setFiles([]); }}>Clear</button>
                  </div>
                  <div className="file-grid">
                    {files.slice(0, 60).map((f, i) => (
                      <figure key={`${f.file.name}-${i}`} className={f.dup ? "is-dup" : ""} title={`${f.file.name}${f.dup ? " (duplicate)" : ""}`}>
                        {f.url ? <img src={f.url} alt="" /> : <span className="file-ph">{f.video ? "clip" : "img"}</span>}
                        <figcaption>{f.dup ? "dup" : fmtBytes(f.size)}</figcaption>
                      </figure>
                    ))}
                    {files.length > 60 && <figure><span className="file-ph">+{files.length - 60}</span></figure>}
                  </div>
                </div>
              )}

              {!target && (
                <fieldset className="intake-name">
                  <legend>Name by purpose</legend>
                  <div className="seg seg-purpose" role="radiogroup" aria-label="Purpose">
                    {PURPOSES.map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={purpose === k} className={purpose === k ? "is-on" : ""} onClick={() => setPurpose(k)}>{l}</button>)}
                  </div>
                  <label className="field" style={{ marginTop: 10 }}>
                    <span>Name <small className="muted">saved as <code>{nameOk ? name : "purpose-name"}</code></small></span>
                    <input value={stem} onChange={(e) => setStem(e.target.value)} placeholder={purpose === "persona" ? "amina" : purpose === "wardrobe" ? "red-dress" : purpose === "motion" ? "runway-walk" : "name"} />
                  </label>
                  {cols?.some((c) => c.name === name) && <p className="notice">A collection called {name} exists. Files will be added to it and its rights kept.</p>}
                </fieldset>
              )}
            </>
          )}

          {(tab === "fix" || (tab === "new" && needChoice)) && (
            <fieldset className="intake-rights">
              <legend>Who owns these, and how may they be used?</legend>
              <div className="rights-list" role="radiogroup">
                {CHOICES.map(([k, l, hint]) => (
                  <label key={k} className={`rights-opt${choice === k ? " is-on" : ""}`}>
                    <input type="radio" name="choice" value={k} checked={choice === k} onChange={() => setChoice(k)} />
                    <span><b>{l}</b><small>{hint}</small></span>
                  </label>
                ))}
              </div>
              {(choice === "own" || choice === "licensed") && (
                <div className="real-person">
                  <label className="switch"><input type="checkbox" checked={realPerson} onChange={(e) => setRealPerson(e.target.checked)} /><span>A real person appears in these</span></label>
                  {realPerson && (
                    <div className="release">
                      <p className="muted">A face may be swapped, dressed, animated or trained on only with a written release from that person. Without one the collection can still shape prompts but no face or character step will accept it.</p>
                      <label className="field"><span>Release file (PDF, image or text)</span><input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md" onChange={(e) => setRelease(e.target.files?.[0] || null)} /></label>
                      <label className="field"><span>Or where the signed release is kept</span><input value={releaseNote} onChange={(e) => setReleaseNote(e.target.value)} placeholder="e.g. Drive: Releases/amina-2026.pdf" /></label>
                    </div>
                  )}
                </div>
              )}
              <label className="field"><span>Notes <small className="muted">optional, one per line</small></span><textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="licence name, shoot date, who is in the photos" /></label>
            </fieldset>
          )}

          {result && (
            <div className="intake-result">
              <p><b>{result.created ? "Created" : "Updated"} {result.collection.name}</b>: {result.saved?.length || 0} added{result.skipped?.length ? `, ${result.skipped.length} already there` : ""}{result.rejected?.length ? `, ${result.rejected.length} rejected` : ""}. {result.collection.count} files, {fmtBytes(result.collection.bytes)}.</p>
              {result.rejected?.slice(0, 3).map((r, i) => <small key={i} className="muted">{r.name}: {r.why}</small>)}
            </div>
          )}
          {error && <p className="error" role="alert">{error}</p>}
        </div>

        {(tab === "new" || tab === "fix") && (
          <div className="intake-foot">
            {busy && <span className="progress" style={{ flex: 1 }}><i style={{ width: `${progress}%` }} /></span>}
            {!busy && tab === "new" && <span className="muted">{fresh.length ? `${fresh.length} file${fresh.length === 1 ? "" : "s"} to ${target ? target : nameOk ? name : "a new collection"}` : "Nothing to add yet"}</span>}
            <button type="button" className="btn btn-quiet" onClick={onClose}>Cancel</button>
            <button type="button" className="btn btn-primary" disabled={!canSave} onClick={tab === "fix" ? async () => {
              setBusy(true); setError("");
              const res = await fetch("/api/references", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ws: workspace, name: target, choice, real_person: realPerson, release_note: releaseNote, notes: notes.split(/\r?\n/) }) });
              const data = await res.json().catch(() => ({}));
              setBusy(false);
              if (!res.ok) { setError(data.error || "Could not update the rights."); return; }
              onDone?.(data.collection, data);
            } : submit}>
              {busy ? `Saving ${progress}%` : tab === "fix" ? "Save rights" : target ? "Add files" : "Save collection"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
