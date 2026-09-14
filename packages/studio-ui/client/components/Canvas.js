"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import ReactFlow, {
  Background, BackgroundVariant, MiniMap, ReactFlowProvider, addEdge,
  useEdgesState, useNodesState, useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import StudioNode from "./StudioNode";
import DirectorChat from "./DirectorChat";
import PickGrid from "./PickGrid";

const RUN_MODES = [["dry-run", "Dry run", "Nothing runs or spends"], ["stage-approval", "Approve", "You approve each stage's cost before it runs"], ["auto", "Auto", "One approval; pauses at your picks and before publishing"]];

// A stage label drawn on the canvas, one per lane. It never receives clicks.
function LaneLabel({ data }) {
  return <div className="lane-label">{data.label}</div>;
}
const nodeTypes = { studio: StudioNode, lane: LaneLabel };

function laneNodes(wf) {
  if (!wf.stages?.length) return [];
  const byStage = {};
  for (const n of wf.nodes) {
    const s = n.data?.stage;
    if (!s) continue;
    byStage[s] = Math.min(byStage[s] ?? Infinity, n.position.y);
  }
  return wf.stages.filter((s) => byStage[s.id] != null).map((s) => ({
    id: `lane:${s.id}`, type: "lane", position: { x: 20, y: byStage[s.id] - 34 }, draggable: false, selectable: false, connectable: false,
    data: { label: s.label }, style: { zIndex: -1 },
  }));
}

// What a pick step can choose from: every result of every step feeding it.
function candidatesFor(wf, byKind, pickId) {
  const out = [];
  for (const e of wf.edges) {
    if (e.target !== pickId) continue;
    const src = wf.nodes.find((n) => n.id === e.source);
    if (!src) continue;
    const label = [byKind[src.kind]?.label, src.data?.camera].filter(Boolean).join(" · ");
    const done = (src.data?.results || []).filter((r) => r.status === "completed");
    if (done.length) {
      for (const r of done) r.files.forEach((f, i) => out.push({ id: `${src.id}#${r.run_id}#${i}`, file: f, video: /\.(mp4|webm|mov)$/i.test(f), label: `${label} #${i + 1}` }));
    } else {
      const n = Number(src.data?.variant_count || 1);
      for (let i = 0; i < n; i++) out.push({ id: `${src.id}#pending#${i}`, file: null, label: `${label} (not made yet)` });
    }
  }
  return out;
}

function toFlow(wf, byKind, types) {
  const gapNodes = new Set((wf.gaps || []).map((g) => g.node));
  const nodes = wf.nodes.map((n) => ({
    id: n.id,
    type: "studio",
    position: n.position,
    // Everything the engine wrote on a node (scene, shot, variant_count, results, picked, why...)
    // rides along untouched so a save from the canvas never loses it.
    data: { ...(n.data || {}), kind: n.kind, params: n.data?.params || {}, spec: byKind[n.kind] || null, types, gap: gapNodes.has(n.id) },
  }));
  const edges = wf.edges.map((e) => ({
    id: e.id, source: e.source, sourceHandle: e.sourceHandle, target: e.target, targetHandle: e.targetHandle,
    data: { type: e.type, married: !!e.married },
    animated: !!e.married,
    style: { stroke: types[e.type]?.color || "#777", strokeWidth: e.married ? 2.4 : 1.6 },
  }));
  return { nodes: nodes.concat(laneNodes(wf)), edges };
}

function fromFlow(initial, nodes, edges) {
  return {
    ...initial,
    nodes: nodes.filter((n) => n.type === "studio").map((n) => {
      const { kind, spec, types, gap, ...rest } = n.data;
      return { id: n.id, kind, position: { x: Math.round(n.position.x), y: Math.round(n.position.y) }, data: { ...rest, params: n.data.params } };
    }),
    edges: edges.map((e) => ({
      id: e.id, source: e.source, sourceHandle: e.sourceHandle, target: e.target, targetHandle: e.targetHandle,
      type: e.data?.type, ...(e.data?.married ? { married: true } : {}),
    })),
  };
}

function Library({ catalog, onPick }) {
  const [q, setQ] = useState("");
  const shown = catalog.nodes.filter((n) => (n.label + " " + n.blurb).toLowerCase().includes(q.toLowerCase()));
  return (
    <aside className="panel library" aria-label="Node library">
      <input className="search" placeholder="Search steps" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="library-scroll">
        {catalog.categories.map((c) => {
          const items = shown.filter((n) => n.category === c.id);
          if (!items.length) return null;
          return (
            <div key={c.id} className="lib-group">
              <h4>{c.label}</h4>
              {items.map((n) => (
                <button key={n.kind} className={`lib-item${n.backend.kind === "gap" ? " is-gap" : ""}`} draggable
                  onDragStart={(e) => { e.dataTransfer.setData("application/studio-node", n.kind); e.dataTransfer.effectAllowed = "move"; }}
                  onClick={() => onPick(n.kind)} title={n.blurb}>
                  <span className="lib-dot" style={{ background: catalog.types[n.outputs[0]?.type]?.color }} />
                  <span>
                    <b>{n.label}</b>
                    <small>{n.backend.kind === "gap" ? "Not runnable yet" : n.blurb}</small>
                  </span>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </aside>
  );
}

function Inspector({ node, catalog, onParam, onDelete, onClose }) {
  if (!node) return null;
  const spec = node.data.spec;
  const be = spec?.backend;
  const runs = !spec ? `No catalogue node runs '${node.data.step}' yet.`
    : { input: "You provide this.", brand: "Read from the client's brand.yaml.", comfy: `ComfyUI workflow: ${be.workflow}`,
        router: "Hosted image model through OpenRouter.", python: `Runs ${be.module}`, publish: `Creates a draft through ${be.module}`,
        human: "Waits for you to choose. Nothing downstream runs until you do.", gap: be.reason }[be.kind];
  return (
    <aside className="panel inspector" aria-label="Step settings">
      <div className="inspector-head">
        <h3>{spec?.label || node.data.step}</h3>
        <button className="icon-btn" onClick={onClose} aria-label="Close settings">×</button>
      </div>
      {spec?.blurb && <p className="muted">{spec.blurb}</p>}
      <dl className="facts">
        <dt>Runs on</dt><dd className={be?.kind === "gap" || !spec ? "gap-text" : ""}>{runs}</dd>
        {node.data.part && (<><dt>From</dt><dd>{node.data.part}</dd></>)}
      </dl>
      {spec?.adult && <p className="notice">18+ line only: fictional adults, a separate entity, never on Ongea Pesa or EPALLE work.</p>}
      {spec?.consent && <p className="notice">Only owned or consented likenesses may go into this step.</p>}
      {spec?.params?.map((p) => (
        <label key={p.key} className="field">
          <span>{p.label}</span>
          {p.type === "textarea" ? (
            <textarea rows={4} value={node.data.params[p.key] ?? ""} onChange={(e) => onParam(p.key, e.target.value)} />
          ) : p.type === "select" ? (
            <select value={node.data.params[p.key] ?? p.default} onChange={(e) => onParam(p.key, e.target.value)}>
              {p.options.map((o) => <option key={o}>{o}</option>)}
            </select>
          ) : (
            <input type={p.type === "number" ? "number" : "text"} value={node.data.params[p.key] ?? ""}
              onChange={(e) => onParam(p.key, p.type === "number" ? Number(e.target.value) : e.target.value)} />
          )}
        </label>
      ))}
      <button className="btn btn-danger" onClick={onDelete}>Delete step</button>
    </aside>
  );
}

function Editor({ client, initial, catalog }) {
  const byKind = useMemo(() => Object.fromEntries(catalog.nodes.map((n) => [n.kind, n])), [catalog]);
  const start = useMemo(() => toFlow(initial, byKind, catalog.types), [initial, byKind, catalog.types]);
  const [nodes, setNodes, onNodesChange] = useNodesState(start.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(start.edges);
  const [selected, setSelected] = useState(null);
  const [title, setTitle] = useState(initial.title);
  const [plan, setPlan] = useState(null);
  const [toast, setToast] = useState("");
  const [wf, setWf] = useState(initial);
  const [mode, setMode] = useState(initial.run_mode || "dry-run");
  const [director, setDirector] = useState(!!initial.source?.engine);
  const [stage, setStage] = useState("next");
  const [running, setRunning] = useState(false);
  const [picking, setPicking] = useState(null);
  const wrap = useRef(null);
  const flow = useReactFlow();
  const readOnly = !!client.templates;
  const sessionId = initial.source?.engine?.session || initial.id;

  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(""), 2600); };

  // The director or the runner rewrote the file: redraw everything from it.
  const replace = useCallback((next) => {
    setWf(next);
    setTitle(next.title);
    setMode(next.run_mode || "dry-run");
    const f = toFlow(next, byKind, catalog.types);
    setNodes(f.nodes);
    setEdges(f.edges);
    setTimeout(() => flow.fitView({ padding: 0.2 }), 50);
  }, [byKind, catalog.types, setNodes, setEdges, flow]);

  async function reload() {
    const res = await fetch(`/api/workflows/${client.id}/${initial.id}`);
    if (res.ok) replace(await res.json());
  }

  // Returns what happened in words, so the voice director can say it back.
  async function runStage(which = stage) {
    setRunning(true);
    try {
      const res = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client: client.id, workflow: initial.id, stage: which, mode, approveAs: mode === "dry-run" ? undefined : "human" }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { const msg = data.error || "The stage did not run."; flash(msg); return msg; }
      const done = (data.results || []).filter((r) => r.status === "completed").length;
      const msg = data.note || `${data.stage || "stage"}: ${data.results?.length || 0} step(s), ${done} completed under ${data.mode}.${data.pending_picks?.length ? ` ${data.pending_picks.length} pick(s) waiting for you.` : ""}`;
      flash(msg);
      await reload();
      return msg;
    } finally {
      setRunning(false);
    }
  }

  const workflowStatus = () => ({
    title: wf.title, run_mode: mode, look: wf.preset || wf.source?.engine?.preset, kind: wf.source?.engine?.profile,
    stages: (wf.stages || []).map((s) => s.id),
    pending_picks: (wf.nodes || []).filter((n) => ["pick", "pick-video"].includes(n.kind) && !n.data?.picked?.length).map((n) => n.id),
    gaps: (wf.gaps || []).map((g) => g.reason || g.note || g.id).slice(0, 12),
  });

  const portType = useCallback((nodeId, handle, dir) => {
    const n = nodes.find((x) => x.id === nodeId);
    const spec = n && byKind[n.data.kind];
    if (!spec) return null;
    return (dir === "out" ? spec.outputs : spec.inputs).find((p) => p.id === handle) || null;
  }, [nodes, byKind]);

  const isValidConnection = useCallback((c) => {
    const out = portType(c.source, c.sourceHandle, "out");
    const inp = portType(c.target, c.targetHandle, "in");
    if (!out || !inp || c.source === c.target) return false;
    return inp.id === "media" ? catalog.media_ports.accepts.includes(out.type) : inp.type === out.type;
  }, [portType, catalog]);

  const onConnect = useCallback((c) => {
    const out = portType(c.source, c.sourceHandle, "out");
    setEdges((eds) => addEdge({
      ...c, id: `e${Date.now()}`, data: { type: out.type },
      style: { stroke: catalog.types[out.type]?.color, strokeWidth: 1.6 },
    }, eds.filter((e) => !(e.target === c.target && e.targetHandle === c.targetHandle))));
  }, [portType, setEdges, catalog]);

  const addNode = useCallback((kind, position) => {
    const spec = byKind[kind];
    const params = Object.fromEntries((spec.params || []).filter((p) => "default" in p).map((p) => [p.key, p.default]));
    const id = `n${Date.now().toString(36)}`;
    const pos = position || flow.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    setNodes((ns) => ns.concat({ id, type: "studio", position: pos, data: { kind, params, spec, types: catalog.types, gap: spec.backend.kind === "gap" } }));
    setSelected(id);
  }, [byKind, flow, setNodes, catalog.types]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData("application/studio-node");
    if (kind) addNode(kind, flow.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  }, [addNode, flow]);

  const current = () => ({ ...fromFlow(wf, nodes, edges), title, run_mode: mode });

  async function save() {
    const res = await fetch(`/api/workflows/${client.id}/${initial.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(current()) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { flash(data.error || "Could not save."); return; }
    const gaps = new Set(data.gaps.map((g) => g.node));
    setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, gap: gaps.has(n.id) } })));
    flash(`Saved. ${data.gaps.length ? `${data.gaps.length} step(s) not runnable yet.` : "Every step can run."}`);
  }

  async function check() {
    const res = await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(current()) });
    setPlan(await res.json());
  }

  const selectedNode = nodes.find((n) => n.id === selected) || null;

  return (
    <div className="studio" style={{ "--client": client.accent }}>
      <header className="panel topbar">
        <Link href={client.templates ? "/" : `/c/${client.id}`} className="crumb">
          <span className="client-swatch" aria-hidden /> {client.name}
        </Link>
        <span className="sep" aria-hidden>/</span>
        <input className="title-input" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Workflow title" readOnly={readOnly} />
        <span className="topbar-stats">
          {nodes.filter((n) => n.type === "studio").length} steps
          {initial.source?.combined && <span className="chip">Combined</span>}
          {wf.source?.engine && <span className="chip">Directed</span>}
          {nodes.some((n) => n.data.gap) && <span className="chip chip-gap">{nodes.filter((n) => n.data.gap).length} not runnable yet</span>}
        </span>
        <div className="topbar-actions">
          {!readOnly && (
            <>
              <span className="mode-toggle" role="radiogroup" aria-label="Run mode">
                {RUN_MODES.map(([id, label, hint]) => (
                  <button key={id} type="button" role="radio" aria-checked={mode === id} title={hint} className={`${mode === id ? "is-on " : ""}mode-${id}`} onClick={() => setMode(id)}>{label}</button>
                ))}
              </span>
              {!!wf.stages?.length && (
                <select className="stage-pick" value={stage} onChange={(e) => setStage(e.target.value)} aria-label="Stage to run">
                  <option value="next">Next stage</option>
                  {wf.stages.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              )}
              <button className="btn" onClick={() => runStage()} disabled={running} title={mode === "dry-run" ? "Writes what would run; nothing is submitted" : "Needs your approval; spends GPU time"}>
                {running ? "Running…" : mode === "dry-run" ? "Dry-run stage" : "Run stage"}
              </button>
              <button className="btn btn-quiet" onClick={() => setDirector((d) => !d)} aria-pressed={director}>Director</button>
            </>
          )}
          <button className="btn btn-quiet" onClick={check}>Check run plan</button>
          {readOnly
            ? <Link className="btn btn-primary" href="/">Use for a client from their workspace</Link>
            : <button className="btn btn-primary" onClick={save}>Save</button>}
        </div>
      </header>

      <Library catalog={catalog} onPick={(k) => !readOnly && addNode(k)} />

      <div className="canvas" ref={wrap} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={readOnly ? undefined : onDrop}>
        <ReactFlow
          nodes={nodes} edges={edges} nodeTypes={nodeTypes}
          onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
          isValidConnection={isValidConnection}
          onNodeClick={(_, n) => { if (n.type !== "studio") return; setSelected(n.id); setPicking(byKind[n.data.kind]?.category === "decide" ? n.id : null); }} onPaneClick={() => { setSelected(null); setPicking(null); }}
          nodesDraggable={!readOnly} nodesConnectable={!readOnly} elementsSelectable
          fitView fitViewOptions={{ padding: 0.2 }} minZoom={0.2} maxZoom={1.8}
          proOptions={{ hideAttribution: true }} deleteKeyCode={readOnly ? null : ["Delete", "Backspace"]}
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="#34343c" />
          <MiniMap pannable zoomable className="minimap" nodeColor={(n) => (n.data.gap ? "#6b5a5a" : catalog.types[n.data.spec?.outputs?.[0]?.type]?.color || "#555")} maskColor="rgba(20,20,22,.7)" />
        </ReactFlow>
        <div className="panel zoombar">
          <button className="icon-btn" onClick={() => flow.zoomOut()} aria-label="Zoom out">−</button>
          <button className="icon-btn" onClick={() => flow.fitView({ padding: 0.2 })} aria-label="Fit to screen">Fit</button>
          <button className="icon-btn" onClick={() => flow.zoomIn()} aria-label="Zoom in">+</button>
        </div>
        <div className="panel legend" aria-label="Port colours">
          {Object.entries(catalog.types).map(([k, t]) => (
            <span key={k}><i style={{ background: t.color }} />{t.label}</span>
          ))}
        </div>
      </div>

      {director && !readOnly && !picking && (
        <DirectorChat client={client.id} workflow={initial.id} session={sessionId}
          onWorkflow={(next) => replace(next)} onRun={(s) => runStage(s)} getStatus={workflowStatus}
          onClose={() => setDirector(false)} />
      )}

      {picking && selectedNode && (
        <PickGrid client={client.id} workflow={initial.id} node={{ id: selectedNode.id, data: selectedNode.data }}
          candidates={candidatesFor(current(), byKind, selectedNode.id)}
          onPicked={async (picked) => { flash(`Kept ${picked.length}.`); setPicking(null); await reload(); }}
          onClose={() => setPicking(null)} />
      )}

      {selectedNode && !picking && !director && (
        <Inspector node={selectedNode} catalog={catalog}
          onClose={() => setSelected(null)}
          onDelete={() => { if (readOnly) return; setNodes((ns) => ns.filter((n) => n.id !== selected)); setEdges((es) => es.filter((e) => e.source !== selected && e.target !== selected)); setSelected(null); }}
          onParam={(k, v) => !readOnly && setNodes((ns) => ns.map((n) => (n.id === selected ? { ...n, data: { ...n.data, params: { ...n.data.params, [k]: v } } } : n)))}
        />
      )}

      {plan && (
        <aside className="panel plan" aria-label="Run plan">
          <div className="inspector-head">
            <h3>Run plan</h3>
            <button className="icon-btn" onClick={() => setPlan(null)} aria-label="Close run plan">×</button>
          </div>
          <p className="muted">{plan.ready} ready, {plan.blocked} not runnable yet{plan.waiting ? `, ${plan.waiting} waiting for your pick` : ""}. {plan.note}</p>
          {plan.consent && <p className="notice">This workflow uses faces or characters. Get consent before running it.</p>}
          <ol className="plan-list">
            {plan.steps.map((s) => (
              <li key={s.id} className={`plan-${s.status}`}>
                <b>{s.label}</b>
                <small>{s.detail}</small>
              </li>
            ))}
          </ol>
        </aside>
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

export default function Canvas(props) {
  return (
    <ReactFlowProvider>
      <Editor {...props} />
    </ReactFlowProvider>
  );
}
