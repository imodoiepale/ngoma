"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ReactFlow, {
  Background, BackgroundVariant, MiniMap, ReactFlowProvider, addEdge,
  useEdgesState, useNodesInitialized, useNodesState, useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import StudioNode from "./StudioNode";
import DirectorChat from "./DirectorChat";
import PickGrid from "./PickGrid";
import GhostNode from "./canvas/GhostNode";
import { Palette, CommandK } from "./canvas/Palette";
import Inspector from "./canvas/Inspector";
import PlanCard from "./canvas/PlanCard";
import DescribeBar from "./canvas/DescribeBar";
import ToolDialog from "./canvas/ToolDialog";
import ResultsDrawer from "./canvas/ResultsDrawer";
import ReferenceIntake from "./refs/ReferenceIntake";
import { purposeForRole } from "./refs/RefStack";
import { REF_KINDS } from "./StudioNode";
import { CanvasContext } from "./canvas/context.js";
import { stepsToGraph } from "./canvas/localDraft";
import { byKindOf, computeGaps, continuationsFor, iteratedPort, pendingPicks, runPlan, validateWorkflow } from "../lib/graph";
import { estimateNode, estimateWorkflow, fmtUsd } from "../lib/estimate";

const RUN_MODES = [["dry-run", "Dry run", "Nothing runs or spends"], ["stage-approval", "Approve", "You approve each stage's cost before it runs"], ["auto", "Auto", "One approval; pauses at your picks and before publishing"]];
const GHOST = "ghost:";

// A stage label drawn on the canvas, one per lane. It never receives clicks.
function LaneLabel({ data }) {
  return <div className="lane-label">{data.label}</div>;
}
const nodeTypes = { studio: StudioNode, lane: LaneLabel, ghost: GhostNode };

function laneNodes(wf) {
  if (!wf.stages?.length) return [];
  // The label sits above the top-left node of its stage, so it works for stages laid out as
  // rows (a lane per stage) and as columns (the engine's left-to-right batch layout).
  const byStage = {};
  for (const n of wf.nodes) {
    const s = n.data?.stage;
    if (!s) continue;
    const cur = byStage[s] || { x: Infinity, y: Infinity };
    byStage[s] = { x: Math.min(cur.x, n.position.x), y: Math.min(cur.y, n.position.y) };
  }
  return wf.stages.filter((s) => byStage[s.id] != null).map((s) => ({
    id: `lane:${s.id}`, type: "lane", position: { x: byStage[s.id].x, y: byStage[s.id].y - 34 }, draggable: false, selectable: false, connectable: false,
    data: { label: s.label }, style: { zIndex: -1 },
  }));
}

// What a pick step can choose from: every result of every step feeding it.
function candidatesFor(wf, byKind, pickId, runsByNode) {
  const out = [];
  for (const e of wf.edges) {
    if (e.target !== pickId) continue;
    const src = wf.nodes.find((n) => n.id === e.source);
    if (!src) continue;
    const label = [byKind[src.kind]?.label, src.data?.camera].filter(Boolean).join(" / ");
    const run = runsByNode[src.id];
    const files = run?.items ? run.items.flatMap((i) => i.files) : run?.files || [];
    const done = files.length ? [{ run_id: run.run_id, files }] : (src.data?.results || []).filter((r) => r.status === "completed");
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
    edges: edges.filter((e) => !e.id.startsWith(GHOST)).map((e) => ({
      id: e.id, source: e.source, sourceHandle: e.sourceHandle, target: e.target, targetHandle: e.targetHandle,
      type: e.data?.type, ...(e.data?.married ? { married: true } : {}),
    })),
  };
}

function Editor({ client, initial, catalog, pricing, readiness, runs = [], references = [], workspaces = [], query = {} }) {
  const router = useRouter();
  const byKind = useMemo(() => byKindOf(catalog), [catalog]);
  const start = useMemo(() => toFlow(initial, byKind, catalog.types), [initial, byKind, catalog.types]);
  const [nodes, setNodes, onNodesChange] = useNodesState(start.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(start.edges);
  const [selected, setSelected] = useState(query.node || null);
  const [title, setTitle] = useState(initial.title);
  const [showPlan, setShowPlan] = useState(false);
  const [toast, setToast] = useState("");
  const [wf, setWf] = useState(initial);
  const [mode, setMode] = useState(initial.run_mode || "dry-run");
  const [director, setDirector] = useState(false);
  const [stage, setStage] = useState("next");
  const [running, setRunning] = useState(false);
  const [picking, setPicking] = useState(null);
  const [results, setResults] = useState(null);
  const [paletteHidden, setPaletteHidden] = useState(false);
  const [cmdk, setCmdk] = useState(false);
  const [toolDlg, setToolDlg] = useState(false);
  const [proposal, setProposal] = useState(null); // {count, reply, source}
  const [useFor, setUseFor] = useState(workspaces[0]?.id || "");
  const [runsByNode, setRunsByNode] = useState(() => indexRuns(runs));
  const [refs, setRefs] = useState(references);
  const [intake, setIntake] = useState(null); // {nodeId?, files?, purpose?, collection?, mode?, expected?, onDone?}
  const rejected = useRef(null);
  const flow = useReactFlow();
  const readOnly = !!client.templates;
  const allowAdult = !!client.adult;
  const sessionId = initial.source?.engine?.session || initial.id;

  const flash = useCallback((msg) => { setToast(msg); setTimeout(() => setToast(""), 3200); }, []);

  function indexRuns(list) {
    const out = {};
    for (const r of list) if (!out[r.node] || String(r.finished || "") > String(out[r.node].finished || "")) out[r.node] = r;
    return out;
  }

  // Reference collections by folder and by name, for the stacks on input nodes and the item
  // counts behind per-item estimates.
  const refsByFolder = useMemo(() => Object.fromEntries(refs.map((r) => [r.folder, r])), [refs]);
  const refsByName = useMemo(() => Object.fromEntries(refs.map((r) => [r.name, r])), [refs]);
  const refCounts = useMemo(() => { const o = {}; for (const r of refs) { o[r.folder] = r.count; o[r.name] = r.count; } return o; }, [refs]);

  // The graph as a workflow file, live, so validation and estimates track every edit.
  const current = useCallback(() => ({ ...fromFlow(wf, nodes, edges), title, run_mode: mode }), [wf, nodes, edges, title, mode]);
  const live = useMemo(() => {
    const c = current();
    const gaps = computeGaps(c, catalog);
    const withGaps = { ...c, gaps };
    return {
      wf: withGaps,
      gaps,
      problems: validateWorkflow(withGaps, catalog),
      plan: runPlan(c, catalog),
      estimate: estimateWorkflow(c, catalog, pricing, refCounts),
      pending: pendingPicks(c, catalog),
      consent: c.nodes.some((n) => byKind[n.kind]?.consent),
    };
  }, [current, catalog, pricing, refCounts, byKind]);

  const openIntake = useCallback((opts) => setIntake({ mode: "pick", ...opts }), []);

  const ctx = useMemo(() => ({
    estimates: live.estimate.nodes, readiness, runsByNode, refsByFolder, refsByName, openIntake: readOnly ? null : openIntake,
    iteratedPort: (data, spec) => iteratedPort({ data }, spec),
  }), [live.estimate.nodes, readiness, runsByNode, refsByFolder, refsByName, openIntake, readOnly]);

  async function refreshRefs() {
    const res = await fetch(`/api/references?ws=${encodeURIComponent(client.id)}`);
    const data = await res.json().catch(() => ({}));
    if (res.ok && Array.isArray(data.collections)) setRefs(data.collections);
  }

  // A collection was chosen or created: bind it to the node that asked (folder param plus a
  // ref summary the estimate reads), or to the proposed node with that id, then tell whoever
  // else asked (the describe bar answering a plan input).
  function bindCollection(nodeId, col) {
    if (!nodeId) return;
    const patch = { collection: col.name, ref: { name: col.name, count: col.count, rights: col.rights, consent: col.consent, kind: col.kind, path: col.folder } };
    setNodes((ns) => ns.map((n) => {
      if (n.id === nodeId && n.type === "studio") return { ...n, data: { ...n.data, ...patch, params: { ...n.data.params, folder: col.folder } } };
      if (n.id === `${GHOST}${nodeId}` && n.type === "ghost") return { ...n, data: { ...n.data, ...patch, itemCount: col.count, params: { ...n.data.params, folder: col.folder } } };
      return n;
    }));
  }

  // The director or the runner rewrote the file: redraw everything from it.
  const replace = useCallback((next) => {
    setWf(next);
    setTitle(next.title);
    setMode(next.run_mode || "dry-run");
    const f = toFlow(next, byKind, catalog.types);
    setNodes(f.nodes);
    setEdges(f.edges);
    setProposal(null);
    setTimeout(() => flow.fitView({ padding: 0.2 }), 50);
  }, [byKind, catalog.types, setNodes, setEdges, flow]);

  async function reload() {
    const [a, b] = await Promise.all([
      fetch(`/api/workflows/${client.id}/${initial.id}`),
      fetch(`/api/runs?client=${client.id}&workflow=${initial.id}`),
    ]);
    if (a.ok) replace(await a.json());
    if (b.ok) { const d = await b.json(); if (Array.isArray(d.runs)) setRunsByNode(indexRuns(d.runs)); }
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
    pending_picks: live.pending,
    gaps: live.gaps.map((g) => g.reason).slice(0, 12),
  });

  // ---------------------------------------------------------------- connections

  const portType = useCallback((nodeId, handle, dir) => {
    const n = nodes.find((x) => x.id === nodeId);
    const spec = n && byKind[n.data.kind];
    if (!spec) return null;
    return (dir === "out" ? spec.outputs : spec.inputs).find((p) => p.id === handle) || null;
  }, [nodes, byKind]);

  // The validator's port rule, applied while dragging. A refused link explains itself.
  const isValidConnection = useCallback((c) => {
    const out = portType(c.source, c.sourceHandle, "out");
    const inp = portType(c.target, c.targetHandle, "in");
    if (!out || !inp || c.source === c.target || c.target.startsWith(GHOST) || c.source.startsWith(GHOST)) return false;
    const ok = inp.id === "media" ? catalog.media_ports.accepts.includes(out.type) : inp.type === out.type;
    if (!ok) {
      const tl = catalog.types[out.type]?.label || out.type, il = inp.id === "media" ? "image or video" : (catalog.types[inp.type]?.label || inp.type);
      rejected.current = `${tl} cannot feed ${byKind[nodes.find((n) => n.id === c.target)?.data.kind]?.label || "that step"}'s ${inp.id} port (${il}).`;
    }
    return ok;
  }, [portType, catalog, byKind, nodes]);

  const onConnect = useCallback((c) => {
    const out = portType(c.source, c.sourceHandle, "out");
    rejected.current = null;
    setEdges((eds) => addEdge({
      ...c, id: `e${Date.now().toString(36)}`, data: { type: out.type },
      style: { stroke: catalog.types[out.type]?.color, strokeWidth: 1.6 },
    }, eds.filter((e) => !(e.target === c.target && e.targetHandle === c.targetHandle))));
  }, [portType, setEdges, catalog]);

  const onConnectStart = useCallback(() => { rejected.current = null; }, []);
  const onConnectEnd = useCallback(() => { if (rejected.current) { flash(rejected.current); rejected.current = null; } }, [flash]);

  // ---------------------------------------------------------------- adding nodes

  const addNode = useCallback((kind, position, extra = {}) => {
    const spec = byKind[kind];
    if (!spec || (spec.adult && !allowAdult)) return null;
    const params = { ...Object.fromEntries((spec.params || []).filter((p) => "default" in p).map((p) => [p.key, p.default])), ...(extra.params || {}) };
    const id = extra.id || `n${Date.now().toString(36)}${Math.floor(Math.random() * 1e3).toString(36)}`;
    const pos = position || flow.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    const data = { kind, params, spec, types: catalog.types, gap: spec.backend.kind === "gap" };
    if (extra.each) data.each = true;
    if (extra.ref) data.ref = extra.ref;
    setNodes((ns) => ns.concat({ id, type: "studio", position: pos, data }));
    setSelected(id);
    return id;
  }, [byKind, flow, setNodes, catalog.types, allowAdult]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData("application/studio-node");
    if (kind) addNode(kind, flow.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  }, [addNode, flow]);

  // Deep links from Home and Explore: ?use=<kind> drops a step, ?node=<id> selects one.
  const bootstrapped = useRef(false);
  // Centre one node in the part of the canvas the palette and inspector leave uncovered.
  const focusNode = useCallback((n, inspectorOpen = true, tries = 0) => {
    // fitView reports false until the node has been measured; try again shortly
    const ok = flow.fitView({ nodes: [{ id: n.id }], padding: 1.2, maxZoom: 1.2, duration: 0 });
    if (!ok) { if (tries < 30) setTimeout(() => focusNode(n, inspectorOpen, tries + 1), 50); return; }
    const left = paletteHidden || readOnly ? 0 : 200, right = inspectorOpen ? 420 : 0;
    const vp = flow.getViewport();
    flow.setViewport({ ...vp, x: vp.x + (left - right) / 2 }, { duration: 0 });
  }, [flow, paletteHidden, readOnly]);

  // ?node=<id>: once React Flow has measured the nodes, centre the linked one.
  const nodesInitialized = useNodesInitialized();
  const focused = useRef(false);
  useEffect(() => {
    if (!nodesInitialized || !query.node || focused.current) return;
    const n = nodes.find((x) => x.id === query.node);
    if (!n) return;
    focused.current = true;
    focusNode(n);
  }, [nodesInitialized, query.node, nodes, focusNode]);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    if (query.use && !readOnly) setTimeout(() => addNode(query.use), 100);
    if (query.node) setTimeout(() => {
      const n = nodes.find((x) => x.id === query.node);
      if (!n) return;
      setSelected(n.id);
      if (runsByNode[n.id]) setResults(n.id);
      if (query.continue && byKind[query.continue] && !readOnly) {
        const c = continuationsFor(n.data.spec?.outputs?.[0]?.type, catalog, { allowAdult }).find((x) => x.kind === query.continue);
        if (c) continueWith(n, c);
      }
    }, 250);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (!readOnly) setCmdk((v) => !v); }
      if (e.key === "Escape") { setCmdk(false); setToolDlg(false); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [readOnly]);

  // ---------------------------------------------------------------- proposals (ghost nodes)

  const clearGhosts = useCallback(() => {
    setNodes((ns) => ns.filter((n) => n.type !== "ghost"));
    setEdges((es) => es.filter((e) => !e.id.startsWith(GHOST)));
    setProposal(null);
  }, [setNodes, setEdges]);

  const acceptGhost = useCallback((gid) => {
    setNodes((ns) => {
      const g = ns.find((n) => n.id === gid);
      if (!g) return ns;
      const id = g.data.acceptId || `n${Date.now().toString(36)}`;
      const spec = g.data.spec;
      const data = { kind: g.data.kind, params: g.data.params || {}, spec, types: catalog.types, gap: spec?.backend.kind === "gap" };
      if (g.data.each) data.each = true;
      if (g.data.ref) data.ref = g.data.ref;
      const real = { id, type: "studio", position: g.position, data };
      setEdges((es) => es.map((e) => (e.source === gid || e.target === gid
        ? { ...e, id: e.id.replace(GHOST, "e"), source: e.source === gid ? id : e.source, target: e.target === gid ? id : e.target, animated: false, className: undefined, style: { stroke: catalog.types[e.data?.type]?.color, strokeWidth: 1.6 } }
        : e)));
      return ns.filter((n) => n.id !== gid).concat(real);
    });
    setProposal((p) => (p && p.count > 1 ? { ...p, count: p.count - 1 } : null));
  }, [setNodes, setEdges, catalog.types]);

  const discardGhost = useCallback((gid) => {
    setNodes((ns) => ns.filter((n) => n.id !== gid));
    setEdges((es) => es.filter((e) => e.source !== gid && e.target !== gid));
    setProposal((p) => (p && p.count > 1 ? { ...p, count: p.count - 1 } : null));
  }, [setNodes, setEdges]);

  const setGhost = useCallback((gid, patch) => {
    setNodes((ns) => ns.map((n) => (n.id === gid ? { ...n, data: { ...n.data, ...patch(n.data) } } : n)));
  }, [setNodes]);

  // Turn a workflow fragment (nodes + edges in studio.json shape) into ghost nodes and edges.
  const proposeGraph = useCallback((fragment, { reply, source, itemCount } = {}) => {
    const existing = new Set(nodes.filter((n) => n.type === "studio").map((n) => n.id));
    const fresh = fragment.nodes.filter((n) => !existing.has(n.id));
    if (!fresh.length) { flash(reply || "Nothing new to add."); return; }
    const ghosts = fresh.map((n) => {
      const gid = `${GHOST}${n.id}`;
      const spec = byKind[n.kind] || null;
      const params = n.data?.params || {};
      const each = !!n.data?.each;
      const items = each ? (itemCount || n.data?.ref?.count || 1) : 1;
      return {
        id: gid, type: "ghost", position: n.position, draggable: true,
        data: {
          kind: n.kind, spec, types: catalog.types, each, params, ref: n.data?.ref, acceptId: existing.has(n.id) ? undefined : n.id, itemCount: each ? itemCount || n.data?.ref?.count : undefined,
          estimate: spec ? estimateNode(n.kind, spec, params, pricing, { items }) : null,
          kindLabel: n.data?.step || n.kind,
          onAccept: () => acceptGhost(gid),
          onDiscard: () => discardGhost(gid),
          onToggleEach: spec && ["comfy", "router", "python", "gap"].includes(spec.backend.kind) ? (v) => setGhost(gid, (d) => ({ each: v, estimate: estimateNode(d.kind, d.spec, d.params, pricing, { items: v ? (d.itemCount || 1) : 1 }) })) : undefined,
          onParam: spec?.params?.length ? (k, v) => setGhost(gid, (d) => { const p = { ...d.params, [k]: v }; return { params: p, estimate: estimateNode(d.kind, d.spec, p, pricing, { items: d.each ? (d.itemCount || 1) : 1 }) }; }) : undefined,
        },
      };
    });
    const ghostIds = new Set(fresh.map((n) => n.id));
    const gEdges = fragment.edges
      .filter((e) => (ghostIds.has(e.source) || ghostIds.has(e.target)) && (existing.has(e.source) || ghostIds.has(e.source)) && (existing.has(e.target) || ghostIds.has(e.target)))
      .map((e) => ({
        id: `${GHOST}${e.id}`, source: ghostIds.has(e.source) ? `${GHOST}${e.source}` : e.source, sourceHandle: e.sourceHandle,
        target: ghostIds.has(e.target) ? `${GHOST}${e.target}` : e.target, targetHandle: e.targetHandle,
        data: { type: e.type }, animated: true, className: "ghost-edge", style: { stroke: catalog.types[e.type]?.color || "#777", strokeWidth: 1.6, strokeDasharray: "6 6" },
      }));
    setNodes((ns) => ns.filter((n) => n.type !== "ghost").concat(ghosts));
    setEdges((es) => es.filter((e) => !e.id.startsWith(GHOST)).concat(gEdges));
    setProposal({ count: ghosts.length, reply, source });
    setTimeout(() => flow.fitView({ padding: 0.25, duration: 500 }), 50);
  }, [nodes, byKind, catalog.types, pricing, acceptGhost, discardGhost, setGhost, setNodes, setEdges, flow, flash]);

  // Where new steps go: to the right of everything on the canvas.
  const nextOrigin = useCallback(() => {
    const studio = nodes.filter((n) => n.type === "studio");
    if (!studio.length) return { x: 80, y: 120 };
    const maxX = Math.max(...studio.map((n) => n.position.x));
    const minY = Math.min(...studio.map((n) => n.position.y));
    return { x: maxX + 320, y: minY };
  }, [nodes]);

  // The describe bar answered. Engine answers carry a whole workflow (the contract's
  // `workflow`), whose nodes not yet on the canvas become proposals; local drafts carry steps.
  const onProposal = useCallback((p) => {
    if (p.source === "engine") {
      const wfNew = p.workflow;
      const count = p.plan?.estimate?.items || undefined;
      if (wfNew?.nodes?.length) {
        const existing = new Set(nodes.filter((n) => n.type === "studio").map((n) => n.id));
        const fresh = wfNew.nodes.filter((n) => !existing.has(n.id));
        const origin = nextOrigin();
        const laid = fresh.map((n, i) => (n.position && Number.isFinite(n.position.x) && existing.size === 0 ? n : { ...n, position: { x: origin.x + i * 290, y: origin.y } }));
        proposeGraph({ nodes: laid, edges: wfNew.edges || [] }, { reply: p.reply, source: "engine", itemCount: count });
      } else if (Array.isArray(p.plan?.steps) && p.plan.steps.length) {
        const g = stepsToGraph(p.plan.steps.map((s) => ({ kind: byKind[s.kind] ? s.kind : (catalog.nodes.find((n) => (n.steps || []).includes(s.kind))?.kind || s.kind), each: !!s.each, params: s.params || {} })), catalog, nextOrigin(), "p");
        proposeGraph(g, { reply: p.reply, source: "engine", itemCount: count });
      } else {
        flash(p.reply || "The engine answered without steps.");
      }
      if (Array.isArray(p.continuations) && p.continuations.length) {
        flash(`${p.reply || ""} ${p.continuations.length} continuation(s) offered after stage one completes.`.trim());
      }
    } else {
      const g = stepsToGraph(p.steps, catalog, nextOrigin(), "d");
      proposeGraph(g, { reply: p.reply, source: "local", itemCount: p.count });
    }
  }, [nodes, nextOrigin, proposeGraph, byKind, catalog, flash]);

  // "Continue with": a proposed step hanging off a completed node's output, fan-out on by
  // default, with its estimate for the item count the run recorded.
  const continueWith = useCallback((srcNode, c) => {
    const spec = byKind[c.kind];
    const run = runsByNode[srcNode.id];
    const itemCount = run?.items ? run.items.filter((i) => i.status === "completed").length : (run?.files?.length || 1);
    const out = srcNode.data.spec.outputs[0];
    const id = `${c.kind}-${Date.now().toString(36)}`;
    const params = Object.fromEntries((spec.params || []).filter((p) => "default" in p).map((p) => [p.key, p.default]));
    if ("slides" in params) params.slides = 10;
    const fragment = {
      nodes: [{ id, kind: c.kind, position: { x: srcNode.position.x + 320, y: srcNode.position.y }, data: { params, each: c.each } }],
      edges: [{ id: `c${id}`, source: srcNode.id, sourceHandle: out.id, target: id, targetHandle: c.port, type: out.type }],
    };
    proposeGraph(fragment, { reply: `Continue with ${spec.label}${c.each ? ` for each of the ${itemCount}` : ""}.`, source: "continue", itemCount });
    setResults(null);
  }, [byKind, runsByNode, proposeGraph]);

  // Accepting a continuation goes through the describe engine when it is there (mode create,
  // "carousel@each slides=10" appended to this workflow), else it is added locally to save.
  const acceptAll = useCallback(async () => {
    const ghosts = nodes.filter((n) => n.type === "ghost");
    if (proposal?.source === "continue" && ghosts.length === 1 && !readOnly) {
      const g = ghosts[0];
      const text = `${g.data.kind}${g.data.each ? "@each" : ""}${g.data.params?.slides ? ` slides=${g.data.params.slides}` : ""}`;
      try {
        const res = await fetch("/api/describe", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace: client.id, text, mode: "create", workflow: initial.id }) });
        if (res.ok) {
          const data = await res.json();
          if (data.workflow?.nodes) { replace(data.workflow); flash(data.reply || "Stage appended."); return; }
        }
      } catch { /* engine offline: fall through to the local path */ }
      flash("Describe engine offline. Added locally; press Save to keep it.");
    }
    for (const g of ghosts) acceptGhost(g.id);
    setProposal(null);
  }, [nodes, proposal, readOnly, client.id, initial.id, replace, flash, acceptGhost]);

  // ---------------------------------------------------------------- save, tool, plan

  async function save(extra = {}) {
    if (readOnly) return;
    const body = { ...current(), ...extra };
    const res = await fetch(`/api/workflows/${client.id}/${initial.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { flash(data.error || "Could not save."); return false; }
    setWf(data);
    const gaps = new Set(data.gaps.map((g) => g.node));
    setNodes((ns) => ns.map((n) => (n.type === "studio" ? { ...n, data: { ...n.data, gap: gaps.has(n.id) } } : n)));
    flash(`Saved. ${data.gaps.length ? `${data.gaps.length} step(s) not runnable yet.` : "Every step can run."}`);
    return true;
  }

  async function saveTool({ title: toolTitle, inputs, exposeByNode }) {
    setNodes((ns) => ns.map((n) => (n.type === "studio" ? { ...n, data: { ...n.data, expose: exposeByNode[n.id] || undefined } } : n)));
    const c = current();
    c.nodes = c.nodes.map((n) => ({ ...n, data: { ...n.data, expose: exposeByNode[n.id] || undefined } }));
    const res = await fetch(`/api/workflows/${client.id}/${initial.id}`, { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...c, tool: { enabled: true, title: toolTitle, inputs } }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { flash(data.error || "Could not save the tool."); return; }
    setWf(data);
    setToolDlg(false);
    flash("Saved as a tool.");
    router.push(`/w/${client.id}/t/${initial.id}`);
  }

  async function useTemplate() {
    if (!useFor) return;
    const res = await fetch("/api/author", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "idea", client: useFor, idea: initial.source?.idea, title: initial.title }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { flash(data.error || "Could not copy this template."); return; }
    router.push(`/w/${useFor}/f/${data.id}`);
  }

  const selectedNode = nodes.find((n) => n.id === selected && n.type === "studio") || null;
  const selectedRun = selectedNode ? runsByNode[selectedNode.id] : null;
  const stageEstimate = useMemo(() => {
    const ids = stage === "next" ? null : new Set(nodes.filter((n) => n.type === "studio" && n.data.stage === stage).map((n) => n.id));
    let usd = 0;
    for (const [id, e] of Object.entries(live.estimate.nodes)) if (!ids || ids.has(id)) usd += e.usd;
    return usd;
  }, [stage, nodes, live.estimate.nodes]);
  const studioCount = nodes.filter((n) => n.type === "studio").length;

  return (
    <CanvasContext.Provider value={ctx}>
      <div className="studio" style={{ "--accent": client.accent, "--accent-ink": client.accentInk || "#15120b" }}>
        <header className="panel topbar">
          <Link href="/" className="wordmark wordmark-sm" aria-label="Director home">Director</Link>
          <span className="sep" aria-hidden>/</span>
          <Link href={client.templates ? "/explore" : `/w/${client.id}`} className="crumb">
            <span className="client-swatch" aria-hidden /> {client.name}
          </Link>
          <span className="sep" aria-hidden>/</span>
          <input className="title-input" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Workflow title" readOnly={readOnly} />
          <span className="topbar-stats">
            {studioCount} steps
            {initial.source?.combined && <span className="chip">Combined</span>}
            {wf.source?.engine && <span className="chip">Directed</span>}
            {wf.tool?.enabled && <Link className="chip chip-link" href={`/w/${client.id}/t/${initial.id}`}>Tool</Link>}
            {live.gaps.length > 0 && <span className="chip chip-gap">{live.gaps.length} not runnable yet</span>}
            {live.problems.length > 0 && <span className="chip chip-gap">{live.problems.length} problem(s)</span>}
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
                <button className="btn btn-run" onClick={() => runStage()} disabled={running || live.problems.length > 0}
                  title={mode === "dry-run" ? "Writes what would run; nothing is submitted" : `Needs your approval; est ${fmtUsd(stageEstimate)} (${live.estimate.basis})`}>
                  {running ? "Running" : mode === "dry-run" ? "Dry-run stage" : "Run stage"}
                  <small>{mode === "dry-run" ? "$0 spent" : `est ${fmtUsd(stageEstimate)} ${live.estimate.basis}`}</small>
                </button>
                <button className="btn btn-quiet" onClick={() => setDirector((d) => !d)} aria-pressed={director}>Director</button>
                <button className="btn btn-quiet" onClick={() => setToolDlg(true)}>Save as tool</button>
              </>
            )}
            <button className={`btn btn-quiet${showPlan ? " is-on" : ""}`} onClick={() => setShowPlan((v) => !v)} aria-pressed={showPlan}>
              Plan <small>{fmtUsd(live.estimate.usd)}</small>
            </button>
            {readOnly ? (
              <span className="use-for">
                <select value={useFor} onChange={(e) => setUseFor(e.target.value)} aria-label="Workspace to use this template in">
                  {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
                <button className="btn btn-primary" onClick={useTemplate} disabled={!useFor}>Use in workspace</button>
              </span>
            ) : (
              <button className="btn btn-primary" onClick={() => save()} disabled={live.problems.length > 0} title={live.problems[0] || "Save this workflow"}>Save</button>
            )}
          </div>
        </header>

        <Palette catalog={catalog} allowAdult={allowAdult} readiness={readiness} onPick={(k) => !readOnly && addNode(k)} collapsed={paletteHidden || readOnly} onToggle={() => setPaletteHidden((v) => !v)} />

        <div className={`canvas${paletteHidden || readOnly ? " palette-hidden" : ""}`} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={readOnly ? undefined : onDrop}>
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onConnectStart={onConnectStart} onConnectEnd={onConnectEnd}
            isValidConnection={isValidConnection}
            onNodeClick={(_, n) => { if (n.type !== "studio") return; setSelected(n.id); setPicking(byKind[n.data.kind]?.category === "decide" ? n.id : null); setResults(runsByNode[n.id] ? n.id : null); }}
            onNodeDoubleClick={(_, n) => { if (n.type === "studio" && runsByNode[n.id]) setResults(n.id); }}
            onPaneClick={() => { setSelected(null); setPicking(null); setResults(null); }}
            nodesDraggable={!readOnly} nodesConnectable={!readOnly} elementsSelectable
            fitView={!query.node} fitViewOptions={{ padding: 0.2 }} minZoom={0.15} maxZoom={1.8}
            proOptions={{ hideAttribution: true }} deleteKeyCode={readOnly ? null : ["Delete", "Backspace"]}
          >
            <Background variant={BackgroundVariant.Dots} gap={24} size={1.1} color="#2a2a31" />
            <MiniMap pannable zoomable className="minimap" nodeColor={(n) => (n.type === "ghost" ? "#5a5a66" : n.data.gap ? "#6b5a5a" : catalog.types[n.data.spec?.outputs?.[0]?.type]?.color || "#555")} maskColor="rgba(11,11,13,.75)" />
          </ReactFlow>
          <div className="panel zoombar">
            <button className="icon-btn" onClick={() => flow.zoomOut()} aria-label="Zoom out">-</button>
            <button className="icon-btn" onClick={() => flow.fitView({ padding: 0.2 })} aria-label="Fit to screen">Fit</button>
            <button className="icon-btn" onClick={() => flow.zoomIn()} aria-label="Zoom in">+</button>
            {!readOnly && <button className="icon-btn" onClick={() => setCmdk(true)} aria-label="Add a step" title="Add a step (Ctrl K)">+ step</button>}
          </div>
          <div className="panel legend" aria-label="Port colours">
            {Object.entries(catalog.types).map(([k, t]) => (
              <span key={k}><i style={{ background: t.color }} />{t.label}</span>
            ))}
          </div>
          {proposal && (
            <div className="panel proposal-bar" role="status">
              <span>{proposal.count} proposed step{proposal.count === 1 ? "" : "s"}{proposal.source === "local" ? " (local draft)" : ""}</span>
              <button type="button" className="btn btn-primary btn-sm" onClick={acceptAll}>Add all</button>
              <button type="button" className="btn btn-quiet btn-sm" onClick={clearGhosts}>Dismiss</button>
            </div>
          )}
        </div>

        {!readOnly && (
          <DescribeBar workspace={client.id} workflowId={initial.id} catalog={catalog} allowAdult={allowAdult} onProposal={onProposal} initialText={query.describe || ""}
            refsByName={refsByName}
            onIntake={(input, done) => openIntake({
              nodeId: input.node, purpose: purposeForRole(input.role, input.kind), mode: "pick",
              expected: { kind: input.kind === "video" || input.kind === "video-clip" ? "video" : "image", count: input.expected_count, prompt: input.prompt },
              onDone: (col) => done?.(col),
            })} />
        )}

        {intake && !readOnly && (
          <ReferenceIntake workspace={client.id} initial={intake} onClose={() => setIntake(null)}
            onDone={async (col) => {
              bindCollection(intake.nodeId, col);
              intake.onDone?.(col);
              setIntake(null);
              await refreshRefs();
              flash(`${col.name}: ${col.count} file(s), ${col.feeds ? "may feed a step" : "inspiration only"}.${intake.nodeId ? " Press Save to keep the binding." : ""}`);
            }} />
        )}

        {director && !readOnly && !picking && (
          <DirectorChat client={client.id} workflow={initial.id} session={sessionId}
            onWorkflow={(next) => replace(next)} onRun={(s) => runStage(s)} getStatus={workflowStatus}
            onClose={() => setDirector(false)} />
        )}

        {picking && selectedNode && (
          <PickGrid client={client.id} workflow={initial.id} node={{ id: selectedNode.id, data: selectedNode.data }}
            candidates={candidatesFor(current(), byKind, selectedNode.id, runsByNode)}
            onPicked={async (picked) => { flash(`Kept ${picked.length}.`); setPicking(null); await reload(); }}
            onClose={() => setPicking(null)} />
        )}

        {results && selectedNode && selectedRun && !picking && (
          <ResultsDrawer node={selectedNode} run={selectedRun}
            continuations={continuationsFor(selectedNode.data.spec?.outputs?.[0]?.type, catalog, { allowAdult })}
            onContinue={(c) => continueWith(selectedNode, c)}
            onRerun={readOnly ? undefined : () => runStage(selectedNode.data.stage || "next")}
            onClose={() => setResults(null)} />
        )}

        {selectedNode && !picking && !director && !results && (
          <Inspector node={selectedNode} catalog={catalog} readiness={readiness} estimate={live.estimate.nodes[selectedNode.id]} readOnly={readOnly}
            collection={REF_KINDS.has(selectedNode.data.kind) ? (refsByFolder[selectedNode.data.params?.folder] || refsByName[selectedNode.data.collection] || refsByName[String(selectedNode.data.params?.folder || "").split("/").filter(Boolean).pop()] || null) : undefined}
            onIntake={readOnly ? undefined : (opts) => openIntake({ nodeId: selectedNode.id, purpose: selectedNode.data.kind === "video-clip" ? "motion" : selectedNode.data.kind === "product-photo" ? "product" : "persona", ...opts })}
            onClose={() => setSelected(null)}
            onDelete={() => { setNodes((ns) => ns.filter((n) => n.id !== selected)); setEdges((es) => es.filter((e) => e.source !== selected && e.target !== selected)); setSelected(null); }}
            onParam={(k, v) => setNodes((ns) => ns.map((n) => (n.id === selected ? { ...n, data: { ...n.data, params: { ...n.data.params, [k]: v } } } : n)))}
            onData={(patch) => setNodes((ns) => ns.map((n) => (n.id === selected ? { ...n, data: Object.fromEntries(Object.entries({ ...n.data, ...patch }).filter(([, v]) => v !== undefined)) } : n)))}
          />
        )}

        {showPlan && (
          <PlanCard estimate={live.estimate} problems={live.problems} gaps={live.gaps} plan={live.plan} consent={live.consent} pending={live.pending}
            budget={pricing?.budget_usd ?? 0} onClose={() => setShowPlan(false)}
            onSelect={(id) => { setSelected(id); const n = nodes.find((x) => x.id === id); if (n) focusNode(n); }} />
        )}

        {cmdk && <CommandK onClose={() => setCmdk(false)} catalog={catalog} allowAdult={allowAdult} readiness={readiness} onPick={(k) => addNode(k)} />}
        {toolDlg && <ToolDialog wf={current()} catalog={catalog} onSave={saveTool} onClose={() => setToolDlg(false)} />}

        {toast && <div className="toast" role="status">{toast}</div>}
      </div>
    </CanvasContext.Provider>
  );
}

export default function Canvas(props) {
  return (
    <ReactFlowProvider>
      <Editor {...props} />
    </ReactFlowProvider>
  );
}
