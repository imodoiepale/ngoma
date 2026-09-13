"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import ReactFlow, {
  Background, BackgroundVariant, MiniMap, ReactFlowProvider, addEdge,
  useEdgesState, useNodesState, useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import StudioNode from "./StudioNode";

const nodeTypes = { studio: StudioNode };

function toFlow(wf, byKind, types) {
  const gapNodes = new Set((wf.gaps || []).map((g) => g.node));
  const nodes = wf.nodes.map((n) => ({
    id: n.id,
    type: "studio",
    position: n.position,
    data: { kind: n.kind, params: n.data?.params || {}, step: n.data?.step, part: n.data?.part, spec: byKind[n.kind] || null, types, gap: gapNodes.has(n.id) },
  }));
  const edges = wf.edges.map((e) => ({
    id: e.id, source: e.source, sourceHandle: e.sourceHandle, target: e.target, targetHandle: e.targetHandle,
    data: { type: e.type, married: !!e.married },
    animated: !!e.married,
    style: { stroke: types[e.type]?.color || "#777", strokeWidth: e.married ? 2.4 : 1.6 },
  }));
  return { nodes, edges };
}

function fromFlow(initial, nodes, edges) {
  return {
    ...initial,
    nodes: nodes.map((n) => ({
      id: n.id, kind: n.data.kind, position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      data: { params: n.data.params, ...(n.data.step ? { step: n.data.step } : {}), ...(n.data.part ? { part: n.data.part } : {}) },
    })),
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
        router: "Hosted image model through OpenRouter.", python: `Runs ${be.module}`, publish: `Creates a draft through ${be.module}`, gap: be.reason }[be.kind];
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
  const wrap = useRef(null);
  const flow = useReactFlow();
  const readOnly = !!client.templates;

  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(""), 2600); };

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

  const current = () => ({ ...fromFlow(initial, nodes, edges), title });

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
          {nodes.length} steps
          {initial.source?.combined && <span className="chip">Combined</span>}
          {nodes.some((n) => n.data.gap) && <span className="chip chip-gap">{nodes.filter((n) => n.data.gap).length} not runnable yet</span>}
        </span>
        <div className="topbar-actions">
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
          onNodeClick={(_, n) => setSelected(n.id)} onPaneClick={() => setSelected(null)}
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

      {selectedNode && (
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
          <p className="muted">{plan.ready} ready, {plan.blocked} not runnable yet. {plan.note}</p>
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
