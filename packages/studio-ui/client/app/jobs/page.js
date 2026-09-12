"use client";

import { useCallback, useEffect, useState } from "react";

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
  padding: 22,
  background: "#10131a",
  marginBottom: 18,
};
const muted = { color: "#9ca3b5" };

const STATUS_COLOR = {
  RUNNING: "#5ddc9a",
  EXITED: "#8f96a8",
  TERMINATED: "#d97b7b",
  PENDING: "#e0c46a",
};

function Row({ label, children }) {
  return (
    <div style={{ display: "flex", gap: 10, padding: "5px 0", flexWrap: "wrap" }}>
      <span style={{ ...muted, minWidth: 150 }}>{label}</span>
      <span>{children}</span>
    </div>
  );
}

export default function Jobs() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [auto, setAuto] = useState(true);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/runpod-status");
      const payload = await response.json();
      setData(payload);
      setError(payload.ok ? null : payload.error || "status unavailable");
    } catch (exception) {
      setError(String(exception));
    }
  }, []);

  useEffect(() => {
    load();
    if (!auto) return undefined;
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
  }, [load, auto]);

  return (
    <main style={shell}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 26,
          flexWrap: "wrap",
          gap: 14,
        }}
      >
        <div>
          <small style={{ color: "#8f96a8" }}>EPALLE STUDIO</small>
          <h1 style={{ fontSize: 32, margin: "8px 0" }}>RunPod jobs</h1>
          <p style={muted}>
            {data?.fetchedAt
              ? `live · fetched ${new Date(data.fetchedAt).toLocaleTimeString()}`
              : "connecting…"}
          </p>
        </div>
        <nav style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <label style={{ ...muted, fontSize: 14 }}>
            <input
              type="checkbox"
              checked={auto}
              onChange={(event) => setAuto(event.target.checked)}
              style={{ marginRight: 6 }}
            />
            auto-refresh
          </label>
          <button
            onClick={load}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              border: "1px solid #413678",
              background: "#2b2350",
              color: "#cfc6ff",
              cursor: "pointer",
            }}
          >
            Refresh
          </button>
          <a href="/" style={{ color: "#d9deea" }}>
            Canvas
          </a>
          <a href="/library" style={{ color: "#d9deea" }}>
            Library
          </a>
        </nav>
      </header>

      {error ? (
        <section style={{ ...card, borderColor: "#6b2b2b", background: "#1a1113" }}>
          <h2 style={{ fontSize: 18, marginTop: 0 }}>Status unavailable</h2>
          <p style={{ color: "#e2b4b4", whiteSpace: "pre-wrap" }}>{error}</p>
        </section>
      ) : null}

      {data?.ok ? (
        <>
          <section
            style={{
              ...card,
              borderColor: data.runningPods ? "#3d5c46" : "#242936",
              background: data.runningPods ? "#101a14" : "#10131a",
            }}
          >
            <h2 style={{ fontSize: 18, marginTop: 0 }}>Spend right now</h2>
            <Row label="Running pods">
              <b>{data.runningPods}</b>
            </Row>
            <Row label="GPU cost">
              <b style={{ color: data.runningCostPerHr ? "#e0c46a" : "#5ddc9a" }}>
                ${data.runningCostPerHr.toFixed(3)}/hr
              </b>
              {data.runningCostPerHr ? (
                <span style={{ ...muted, marginLeft: 10 }}>
                  ≈ ${(data.runningCostPerHr * 24).toFixed(2)}/day if left running
                </span>
              ) : null}
            </Row>
            <p style={{ ...muted, marginBottom: 0, fontSize: 14 }}>
              Network volume storage bills continuously and is not included above.
            </p>
          </section>

          <section style={card}>
            <h2 style={{ fontSize: 18, marginTop: 0 }}>Pods</h2>
            {data.pods.length === 0 ? (
              <p style={muted}>No pods.</p>
            ) : (
              data.pods.map((pod) => (
                <div
                  key={pod.id}
                  style={{
                    borderTop: "1px solid #1c212c",
                    paddingTop: 12,
                    marginTop: 12,
                  }}
                >
                  <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
                    <b>{pod.name}</b>
                    <span
                      style={{
                        color: STATUS_COLOR[pod.status] || "#9ca3b5",
                        fontSize: 13,
                        border: "1px solid #242936",
                        borderRadius: 999,
                        padding: "2px 10px",
                      }}
                    >
                      {pod.status}
                    </span>
                    <span style={{ ...muted, fontSize: 13 }}>{pod.id}</span>
                  </div>
                  <Row label="GPU">
                    {pod.gpu || "unassigned"}
                    {pod.gpuCount ? ` ×${pod.gpuCount}` : ""}
                  </Row>
                  <Row label="Cost">${pod.costPerHr}/hr</Row>
                  {pod.publicIp ? <Row label="Public IP">{pod.publicIp}</Row> : null}
                  {pod.portMappings ? (
                    <Row label="Ports">
                      {Object.entries(pod.portMappings)
                        .map(([from, to]) => `${from}→${to}`)
                        .join("  ")}
                    </Row>
                  ) : null}
                  <Row label="Volume">{pod.volume || "none"}</Row>
                </div>
              ))
            )}
          </section>

          <section style={card}>
            <h2 style={{ fontSize: 18, marginTop: 0 }}>Network volumes</h2>
            {data.volumes.map((volume) => (
              <Row key={volume.id} label={volume.name}>
                {volume.size} GB · {volume.dataCenterId} · {volume.id}
                {volume.isEpalle ? (
                  <span style={{ color: "#5ddc9a", marginLeft: 8 }}>EPALLE</span>
                ) : null}
              </Row>
            ))}
          </section>

          <section style={card}>
            <h2 style={{ fontSize: 18, marginTop: 0 }}>Serverless endpoints</h2>
            {data.endpoints.map((endpoint) => (
              <div key={endpoint.id} style={{ marginBottom: 12 }}>
                <b>{endpoint.name}</b>{" "}
                <span style={{ ...muted, fontSize: 13 }}>{endpoint.id}</span>
                <Row label="GPU types">
                  {(endpoint.gpuTypeIds || []).join(", ") || "any"}
                </Row>
                <Row label="Workers">
                  min {endpoint.workersMin} · max {endpoint.workersMax}
                  {endpoint.workersStandby ? (
                    <span style={{ color: "#e0c46a", marginLeft: 8 }}>
                      standby {endpoint.workersStandby} (billed while idle)
                    </span>
                  ) : null}
                </Row>
                <Row label="Idle timeout">{endpoint.idleTimeout}s</Row>
                <Row label="Volume">{endpoint.networkVolumeId || "none"}</Row>
              </div>
            ))}
            {data.endpointHealth ? (
              <>
                <Row label="Workers now">
                  {JSON.stringify(data.endpointHealth.workers || {})}
                </Row>
                <Row label="Jobs">
                  {JSON.stringify(data.endpointHealth.jobs || {})}
                </Row>
              </>
            ) : (
              <p style={{ ...muted, fontSize: 14 }}>
                Endpoint health not reported.
              </p>
            )}
          </section>

          <section style={{ ...card, borderColor: "#413678", background: "#151126" }}>
            <h2 style={{ fontSize: 18, marginTop: 0 }}>Safety posture</h2>
            <Row label="Dataset graph">live=false until deliberately enabled</Row>
            <Row label="Serverless default">dry_run=true</Row>
            <Row label="Paid provider nodes">rejected by the API handler</Row>
            <Row label="Concurrency">one admitted operation at a time</Row>
          </section>
        </>
      ) : null}
    </main>
  );
}
