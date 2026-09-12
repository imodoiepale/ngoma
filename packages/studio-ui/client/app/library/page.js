"use client";

import { useEffect, useState } from "react";

const shell = {
  minHeight: "100vh",
  background: "#090b10",
  color: "#eef1f7",
  padding: "36px",
  fontFamily: "Inter, sans-serif",
};
const card = {
  border: "1px solid #242936",
  borderRadius: 18,
  padding: 20,
  background: "#10131a",
};
const muted = { color: "#9ca3b5" };

function bytes(value) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

export default function Library() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async (searchTerm) => {
    setBusy(true);
    setError(null);
    try {
      const url = searchTerm
        ? `/api/library?q=${encodeURIComponent(searchTerm)}`
        : "/api/library";
      const response = await fetch(url);
      const payload = await response.json();
      setData(payload);
      if (!payload.ok) setError(payload.error || "library unavailable");
    } catch (exception) {
      setError(String(exception));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load("");
  }, []);

  const stats = data?.stats;

  return (
    <main style={shell}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 28,
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <small style={{ color: "#8f96a8" }}>EPALLE STUDIO</small>
          <h1 style={{ fontSize: 34, margin: "8px 0" }}>Workflow library</h1>
          <p style={muted}>
            {stats
              ? `${stats.assets.toLocaleString()} indexed assets · ${bytes(
                  stats.bytes,
                )} · ${stats.sources} tracked sources`
              : "reading the archive index…"}
          </p>
        </div>
        <nav style={{ display: "flex", gap: 14 }}>
          <a href="/" style={{ color: "#d9deea" }}>
            Canvas
          </a>
          <a href="/jobs" style={{ color: "#d9deea" }}>
            Jobs
          </a>
          <a href="/workflow" style={{ color: "#8e7dff" }}>
            Node editor
          </a>
        </nav>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          load(query);
        }}
        style={{ display: "flex", gap: 10, marginBottom: 24, maxWidth: 720 }}
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search transcripts, descriptions and workflow graphs…"
          style={{
            flex: 1,
            padding: "12px 14px",
            borderRadius: 12,
            border: "1px solid #242936",
            background: "#0d1017",
            color: "#eef1f7",
            fontSize: 15,
          }}
        />
        <button
          type="submit"
          disabled={busy}
          style={{
            padding: "12px 20px",
            borderRadius: 12,
            border: "1px solid #413678",
            background: busy ? "#241f3a" : "#2b2350",
            color: "#cfc6ff",
            cursor: busy ? "wait" : "pointer",
            fontSize: 15,
          }}
        >
          {busy ? "…" : "Search"}
        </button>
        {data?.query ? (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              load("");
            }}
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid #242936",
              background: "transparent",
              color: "#9ca3b5",
              cursor: "pointer",
            }}
          >
            Clear
          </button>
        ) : null}
      </form>

      {error ? (
        <section
          style={{ ...card, borderColor: "#6b2b2b", background: "#1a1113", marginBottom: 24 }}
        >
          <h2 style={{ fontSize: 18, marginTop: 0 }}>Library index unavailable</h2>
          <p style={{ color: "#e2b4b4", whiteSpace: "pre-wrap" }}>{error}</p>
        </section>
      ) : null}

      {data?.query ? (
        <section style={{ ...card, marginBottom: 24 }}>
          <h2 style={{ fontSize: 18, marginTop: 0 }}>
            {data.results.length} result{data.results.length === 1 ? "" : "s"} for{" "}
            <span style={{ color: "#aa9cff" }}>{data.query}</span>
          </h2>
          {data.results.length === 0 ? (
            <p style={muted}>No match in the indexed text.</p>
          ) : (
            <ol style={{ paddingLeft: 22, lineHeight: 1.6 }}>
              {data.results.map((result) => (
                <li key={result.path} style={{ marginBottom: 14 }}>
                  <div style={{ color: "#eef1f7", fontWeight: 600 }}>{result.title}</div>
                  <div style={{ color: "#7f879a", fontSize: 13, wordBreak: "break-all" }}>
                    {result.path}
                  </div>
                  <div style={{ color: "#b8bfce", fontSize: 14 }}>{result.snippet}</div>
                </li>
              ))}
            </ol>
          )}
        </section>
      ) : null}

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))",
          gap: 18,
        }}
      >
        {(data?.workflows || []).map((group) => (
          <article key={group.group} style={card}>
            <h2 style={{ fontSize: 18, marginTop: 0 }}>
              {group.group}{" "}
              <span style={{ ...muted, fontSize: 14, fontWeight: 400 }}>
                ({group.count})
              </span>
            </h2>
            <ul style={{ paddingLeft: 20, color: "#b8bfce", lineHeight: 1.8 }}>
              {group.items.map((item) => (
                <li key={item.relPath} title={item.relPath}>
                  {item.name}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      {stats ? (
        <section style={{ ...card, marginTop: 22 }}>
          <h2 style={{ fontSize: 18, marginTop: 0 }}>Index composition</h2>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {stats.kinds.map((kind) => (
              <span
                key={kind.kind}
                style={{
                  border: "1px solid #242936",
                  borderRadius: 999,
                  padding: "5px 12px",
                  color: "#b8bfce",
                  fontSize: 13,
                }}
              >
                {kind.kind} · {kind.c}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section
        style={{
          ...card,
          marginTop: 22,
          borderColor: "#413678",
          background: "#151126",
        }}
      >
        <h2 style={{ fontSize: 18, marginTop: 0 }}>Model access</h2>
        <p style={{ color: "#bbb5d5" }}>
          FLUX.2 Klein 9B FP8 is accepted and token access verified. Klein 9B KV still
          requires manual Hugging Face licence acceptance before its workflows can run.
        </p>
        <a
          href="https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-kv"
          target="_blank"
          rel="noreferrer"
          style={{ color: "#aa9cff", marginRight: 20 }}
        >
          Accept Klein KV ↗
        </a>
        <a
          href="https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8"
          target="_blank"
          rel="noreferrer"
          style={{ color: "#aa9cff" }}
        >
          View Klein FP8 ↗
        </a>
      </section>
    </main>
  );
}
