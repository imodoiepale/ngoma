"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ReferenceIntake, { rightsChip, fmtBytes } from "./ReferenceIntake";

const VIDEO = /\.(mp4|mov)$/i;
const PURPOSE = { persona: "Persona", wardrobe: "Wardrobe", location: "Location", motion: "Motion clip", product: "Product", other: "Other" };

// The workspace's reference collections as cards, with the intake for adding a new one, adding
// files to one, or fixing rights that are unclear. Refreshes the page after a change.
export default function ReferencesPanel({ workspace, collections, openOnLoad = null }) {
  const router = useRouter();
  const [intake, setIntake] = useState(openOnLoad ? { mode: openOnLoad } : null); // ?add=references deep-links into the intake
  const [over, setOver] = useState(false);
  const done = () => { setIntake(null); router.refresh(); };

  return (
    <>
      <div className={`dropzone slim${over ? " is-over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); setIntake({ mode: "new", files: e.dataTransfer.files }); }}>
        <span><b>Drop images, clips or a folder</b> <span className="muted">to start a collection, or</span></span>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setIntake({ mode: "new" })}>Add references</button>
      </div>
      {collections.length ? (
        <div className="cards cards-wide" style={{ marginTop: 12 }}>
          {collections.map((c) => {
            const chip = rightsChip(c);
            return (
              <article key={c.name} className="card ref-card-lg">
                <div className="card-media" style={{ gridTemplateColumns: "repeat(3, 1fr)", aspectRatio: "3 / 1.4" }}>
                  {c.thumbs.slice(0, 3).map((t, i) => (VIDEO.test(t) ? <video key={i} src={t} muted preload="metadata" /> : <img key={i} src={t} alt="" loading="lazy" />))}
                  {!c.thumbs.length && <div className="io" style={{ gridColumn: "1 / -1" }}><span>Empty folder</span></div>}
                  <div className="card-badges">
                    <span className="chip">{PURPOSE[c.purpose]}</span>
                    {chip.warn ? <button type="button" className={`chip ${chip.cls} chip-btn`} onClick={() => setIntake({ mode: "fix", collection: c.name })}>{chip.text}: fix</button> : <span className={`chip ${chip.cls}`}>{chip.text}</span>}
                  </div>
                  <span className="count-badge" style={{ position: "absolute", right: 8, bottom: 8 }}>{c.count}</span>
                </div>
                <div className="card-body">
                  <span className="card-title">{c.name}</span>
                  <span className="card-sub">{c.images ? `${c.images} images` : ""}{c.images && c.videos ? ", " : ""}{c.videos ? `${c.videos} clips` : ""}{c.count ? `, ${fmtBytes(c.bytes)}` : ""}{c.use === "data" ? ". May feed a step." : ". Shapes prompts only."}</span>
                  {c.warning && <span className="card-sub" style={{ color: "var(--setup)" }}>{c.warning}</span>}
                  {c.notes[0] && <span className="card-sub">{c.notes[0]}</span>}
                  <span className="pick-list" style={{ marginTop: 4 }}>
                    <button type="button" className="btn btn-sm btn-quiet" onClick={() => setIntake({ mode: "add", collection: c.name })}>Add files</button>
                    <button type="button" className="btn btn-sm btn-quiet" onClick={() => setIntake({ mode: "fix", collection: c.name })}>Rights</button>
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty" style={{ marginTop: 12 }}><b>No reference collections.</b>Drop a folder of photos above. You will name it by purpose and say who owns it; the studio writes the folder and its rights file.</div>
      )}
      {intake && <ReferenceIntake workspace={workspace} initial={intake} onClose={() => setIntake(null)} onDone={done} />}
    </>
  );
}
