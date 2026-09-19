"use client";

import { useEffect, useState } from "react";

function bytes(value) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
}

export default function LibraryBrowser() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async (term) => {
    setBusy(true); setError(null);
    try {
      const res = await fetch(term ? `/api/library?q=${encodeURIComponent(term)}` : "/api/library");
      const payload = await res.json();
      setData(payload);
      if (!payload.ok) setError(payload.error || "Library unavailable.");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { const t = setTimeout(() => load(""), 0); return () => clearTimeout(t); }, []);
  const stats = data?.stats;

  return (
    <>
      <form className="create-form" style={{ gridTemplateColumns: "minmax(0,1fr) auto auto", marginBottom: 20 }} onSubmit={(e) => { e.preventDefault(); load(query); }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search transcripts, descriptions and workflow graphs" aria-label="Search the library" />
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Searching" : "Search"}</button>
        {data?.query ? <button type="button" className="btn btn-quiet" onClick={() => { setQuery(""); load(""); }}>Clear</button> : <span />}
      </form>
      <p className="muted">{stats ? `${stats.assets.toLocaleString()} indexed assets, ${bytes(stats.bytes)}, ${stats.sources} tracked sources.` : error ? "" : "Reading the archive index."}</p>
      {error && <p className="notice">{error}</p>}
      {data?.query && (
        <section className="panel-card" style={{ marginBottom: 20 }}>
          <h2>{data.results.length} result{data.results.length === 1 ? "" : "s"} for {data.query}</h2>
          {data.results.length === 0 ? <p className="muted">No match in the indexed text.</p> : (
            <ol style={{ paddingLeft: 20, lineHeight: 1.6 }}>
              {data.results.map((r) => (
                <li key={r.path} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600 }}>{r.title}</div>
                  <div className="muted" style={{ wordBreak: "break-all", fontSize: 12 }}>{r.path}</div>
                  <div style={{ fontSize: 14 }}>{r.snippet}</div>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
      <div className="jobs-grid">
        {(data?.workflows || []).map((g) => (
          <article key={g.group} className="panel-card">
            <h2>{g.group} <span className="muted" style={{ fontWeight: 400 }}>({g.count})</span></h2>
            <ul style={{ paddingLeft: 18, lineHeight: 1.8, margin: 0, fontSize: 13.5 }}>
              {g.items.map((it) => <li key={it.relPath} title={it.relPath}>{it.name}</li>)}
            </ul>
          </article>
        ))}
      </div>
      {stats && (
        <section className="panel-card" style={{ marginTop: 20 }}>
          <h2>Index composition</h2>
          <div className="pick-list">{stats.kinds.map((k) => <span key={k.kind} className="chip">{k.kind} {k.c}</span>)}</div>
        </section>
      )}
      <section className="panel-card" style={{ marginTop: 20 }}>
        <h2>Model access</h2>
        <p className="muted">FLUX.2 Klein 9B FP8 is accepted and token access verified. Klein 9B KV still requires manual Hugging Face licence acceptance before its workflows can run; the steps that need it show Needs setup in Explore.</p>
        <div className="pick-list">
          <a className="btn btn-sm" href="https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-kv" target="_blank" rel="noreferrer">Accept Klein KV licence</a>
          <a className="btn btn-sm btn-quiet" href="https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8" target="_blank" rel="noreferrer">View Klein FP8</a>
        </div>
      </section>
    </>
  );
}
