"use client";

import { useCallback, useEffect, useState } from "react";

const STATUS = { RUNNING: "completed", EXITED: "dry-run", TERMINATED: "error", PENDING: "waiting" };

// Live pod, volume and endpoint state from /api/runpod-status, refreshed every 20 seconds.
export default function PodStatus() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [auto, setAuto] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/runpod-status");
      const payload = await res.json();
      setData(payload);
      setError(payload.ok ? null : payload.error || "Status unavailable.");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    if (!auto) return () => clearTimeout(first);
    const timer = setInterval(load, 20000);
    return () => { clearTimeout(first); clearInterval(timer); };
  }, [load, auto]);

  return (
    <div className="jobs-grid">
      <section className="panel-card">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0 }}>Spend right now</h2>
          <label className="switch" style={{ marginLeft: "auto" }}><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /><span className="muted">auto-refresh</span></label>
          <button type="button" className="btn btn-sm" onClick={load}>Refresh</button>
        </div>
        <p className="muted">{data?.fetchedAt ? `Fetched ${new Date(data.fetchedAt).toLocaleTimeString()}` : error ? "" : "Connecting"}</p>
        {error && <p className="notice">{error}</p>}
        {data?.ok && (
          <>
            <div className="kv"><span>Running pods</span><b>{data.runningPods}</b></div>
            <div className="kv"><span>GPU cost</span><b style={{ color: data.runningCostPerHr ? "var(--setup)" : "var(--ready)" }}>${data.runningCostPerHr.toFixed(3)}/h</b>{data.runningCostPerHr ? <span className="muted">about ${(data.runningCostPerHr * 24).toFixed(2)} a day if left running</span> : null}</div>
          </>
        )}
      </section>
      {data?.ok && (
        <>
          <section className="panel-card">
            <h2>Pods</h2>
            {data.pods.length === 0 && <p className="muted">No pods.</p>}
            {data.pods.map((pod) => (
              <div key={pod.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 10, marginTop: 10 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}><b>{pod.name}</b><span className={`snode-status ${STATUS[pod.status] || ""}`}>{pod.status}</span><span className="muted">{pod.id}</span></div>
                <div className="kv"><span>GPU</span><b>{pod.gpu || "unassigned"}{pod.gpuCount ? ` x${pod.gpuCount}` : ""}</b></div>
                <div className="kv"><span>Cost</span><b>${pod.costPerHr}/h</b></div>
                {pod.publicIp && <div className="kv"><span>Public IP</span><b>{pod.publicIp}</b></div>}
                {pod.portMappings && <div className="kv"><span>Ports</span><b>{Object.entries(pod.portMappings).map(([f, t]) => `${f} to ${t}`).join(", ")}</b></div>}
                <div className="kv"><span>Volume</span><b>{pod.volume || "none"}</b></div>
              </div>
            ))}
          </section>
          <section className="panel-card">
            <h2>Volumes and endpoints</h2>
            {data.volumes.map((v) => (
              <div key={v.id} className="kv"><span>{v.name}</span><b>{v.size} GB</b><span className="muted">{v.dataCenterId} {v.id}</span>{v.isStudioVolume && <span className="chip chip-ready">studio volume</span>}</div>
            ))}
            {data.endpoints.map((e) => (
              <div key={e.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 10, marginTop: 10 }}>
                <b>{e.name}</b> <span className="muted">{e.id}</span>
                <div className="kv"><span>GPU types</span><b>{(e.gpuTypeIds || []).join(", ") || "any"}</b></div>
                <div className="kv"><span>Workers</span><b>min {e.workersMin}, max {e.workersMax}</b>{e.workersStandby ? <span style={{ color: "var(--setup)" }}>standby {e.workersStandby} (billed while idle)</span> : null}</div>
                <div className="kv"><span>Idle timeout</span><b>{e.idleTimeout}s</b></div>
              </div>
            ))}
            {data.endpointHealth ? (
              <>
                <div className="kv"><span>Workers now</span><b>{JSON.stringify(data.endpointHealth.workers || {})}</b></div>
                <div className="kv"><span>Jobs</span><b>{JSON.stringify(data.endpointHealth.jobs || {})}</b></div>
              </>
            ) : <p className="muted">Endpoint health not reported.</p>}
          </section>
        </>
      )}
    </div>
  );
}
