// A small local drafter for when /api/describe is offline: it turns a sentence into steps by
// matching catalogue step aliases, honours "then" for order, "for each" for fan-out and "N
// slides" for the carousel, and chains steps by port type. It is a stand-in so describing
// still builds nodes; the engine's describe (W2) is the real thing and wins when it answers.
import { splitEach } from "../../lib/graph";

const PHRASES = [
  [/\b(change|swap|replace)\s+(the\s+)?(character|head|face)\b|\bcharacter[-\s]?(changer|swap)\b|\bhead[-\s]?swap\b/, "character-swap"],
  [/\b(change|swap)\s+(the\s+)?(outfit|clothes|clothing|dress)\b|\bwardrobe\b|\boutfit\b/, "wardrobe"],
  [/\bcarousels?\b/, "carousel"],
  [/\b(animate|make (it|them) move|image[-\s]to[-\s]video|i2v)\b/, "image-to-video"],
  [/\blip[-\s]?sync\b/, "lipsync"],
  [/\bvoice[-\s]?over\b|\bnarrat/, "voiceover"],
  [/\bcaptions?\b|\bsubtitles?\b/, "captions"],
  [/\bupscale\b/, "upscale-video"],
  [/\b(add|place|put)\s+(the\s+)?logo\b|\bcomposit/, "compositor"],
  [/\bexport\b|\bdeliver\b/, "export"],
  [/\bpick\b|\bchoose\b|\bkeep the best\b/, "pick"],
];
const EACH_RE = /\bfor each\b|\bper (image|photo|post|item|result)\b|\beach of them\b|\bacross all of them\b|\bone per\b/;

export function draftFromText(text, catalog, { allowAdult = false } = {}) {
  const byStep = {};
  for (const n of catalog.nodes) {
    if (n.adult && !allowAdult) continue;
    for (const s of n.steps || []) byStep[s] = n.kind;
    byStep[n.kind] = n.kind;
  }
  const clauses = text.toLowerCase().split(/\bthen\b|\bafter that\b|\band next\b|\bfinally\b|;/).map((c) => c.trim()).filter(Boolean);
  const steps = [];
  let count = 0, collection = null;
  const m = text.match(/\b(\d{1,3})\s+(reference\s+)?(images?|photos?|pictures?|references?)\b/i);
  if (m) count = Number(m[1]);
  const f = text.match(/\b(?:folder|collection|references?)\s+(?:called\s+|named\s+)?([a-z0-9][a-z0-9_-]{1,60})\b/i);
  if (f) collection = f[1];

  for (const clause of clauses) {
    const found = [];
    // explicit spellings first: "carousel@each", "wardrobe"
    for (const tok of clause.match(/[a-z0-9-]+(?:@each)?/g) || []) {
      const [step, each] = splitEach(tok);
      if (byStep[step] && !found.some((x) => x.kind === byStep[step])) found.push({ kind: byStep[step], each });
    }
    for (const [re, step] of PHRASES) {
      if (re.test(clause) && byStep[step] && !found.some((x) => x.kind === byStep[step])) found.push({ kind: byStep[step], each: false });
    }
    const each = EACH_RE.test(clause);
    const slides = clause.match(/\b(\d{1,2})\s+slides?\b/);
    for (const s of found) {
      const params = {};
      if (s.kind === "carousel" && slides) params.slides = Number(slides[1]);
      const spec = catalog.nodes.find((n) => n.kind === s.kind);
      const iterable = spec?.inputs.some((p) => !p.optional && (p.type === "image" || p.type === "video" || p.id === "media"));
      steps.push({ kind: s.kind, each: (s.each || each) && iterable && ["comfy", "router", "python", "gap"].includes(spec.backend.kind), params });
    }
  }
  if (!steps.length) return { steps: [], reply: "I did not recognise a step in that. Name one, like carousel, wardrobe or head swap." };

  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const first = byKind[steps[0].kind];
  const needsImage = first?.inputs.some((p) => !p.optional && (p.type === "image" || p.id === "media"));
  const nodes = [];
  if (needsImage) nodes.push({ kind: "reference-images", each: false, params: { folder: collection ? `references/${collection}` : "" }, count });
  nodes.push(...steps);
  const parts = nodes.map((n) => n.kind + (n.each ? "@each" : "") + (n.params.slides ? ` (${n.params.slides} slides)` : ""));
  const reply = `Local draft, engine offline: ${parts.join(" -> ")}.${count ? ` ${count} items.` : ""}${collection ? ` Collection ${collection}.` : ""} Check the steps and add them to the graph.`;
  return { steps: nodes, reply, count, collection };
}

// Wire a list of steps into nodes and edges by port type, placing them in a row.
export function stepsToGraph(steps, catalog, origin = { x: 0, y: 0 }, idPrefix = "d") {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const nodes = [], edges = [];
  const stamp = Date.now().toString(36);
  let prev = null;
  steps.forEach((s, i) => {
    const spec = byKind[s.kind];
    if (!spec) return;
    const id = `${idPrefix}${stamp}${i}`;
    const data = { params: { ...Object.fromEntries((spec.params || []).filter((p) => "default" in p).map((p) => [p.key, p.default])), ...(s.params || {}) } };
    if (s.each) data.each = true;
    if (s.count) data.ref = { count: s.count };
    nodes.push({ id, kind: s.kind, position: { x: origin.x + i * 290, y: origin.y }, data });
    if (prev) {
      const pspec = byKind[prev.kind];
      for (const port of spec.inputs) {
        const out = pspec.outputs.find((o) => port.id === "media" ? catalog.media_ports.accepts.includes(o.type) : o.type === port.type);
        if (out) { edges.push({ id: `e${id}`, source: prev.id, sourceHandle: out.id, target: id, targetHandle: port.id, type: out.type }); break; }
      }
    }
    prev = { id, kind: s.kind };
  });
  return { nodes, edges };
}
