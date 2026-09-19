// A small YAML reader for the repo's configuration files (brand.yaml, engine.yaml). It
// covers what those files use: nested maps by indentation, scalars, quoted strings, block
// lists, inline {flow maps} and [flow lists], folded (>) and literal (|) block scalars, and
// comments. It is for display and estimates, not a general parser; anything it does not
// understand becomes a string rather than an error.

function stripComment(line) {
  let inS = false, inD = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === "'" && !inD) inS = !inS;
    else if (c === '"' && !inS) inD = !inD;
    else if (c === "#" && !inS && !inD && (i === 0 || /\s/.test(line[i - 1]))) return line.slice(0, i);
  }
  return line;
}

function scalar(raw) {
  const s = raw.trim();
  if (s === "" || s === "~" || s === "null") return null;
  if (s === "true") return true;
  if (s === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s);
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) return s.slice(1, -1);
  if (s.startsWith("{") && s.endsWith("}")) return flowMap(s.slice(1, -1));
  if (s.startsWith("[") && s.endsWith("]")) return flowList(s.slice(1, -1));
  return s;
}

function splitTop(s, sep) {
  const out = [];
  let depth = 0, cur = "", inS = false, inD = false;
  for (const c of s) {
    if (c === "'" && !inD) inS = !inS;
    else if (c === '"' && !inS) inD = !inD;
    if (!inS && !inD) {
      if (c === "{" || c === "[") depth++;
      if (c === "}" || c === "]") depth--;
      if (c === sep && depth === 0) { out.push(cur); cur = ""; continue; }
    }
    cur += c;
  }
  if (cur.trim()) out.push(cur);
  return out;
}

function flowMap(body) {
  const out = {};
  for (const part of splitTop(body, ",")) {
    const i = part.indexOf(":");
    if (i < 0) continue;
    out[part.slice(0, i).trim().replace(/^["']|["']$/g, "")] = scalar(part.slice(i + 1));
  }
  return out;
}

function flowList(body) {
  return splitTop(body, ",").map((p) => scalar(p));
}

function indentOf(line) {
  return line.match(/^ */)[0].length;
}

export function parseYaml(text) {
  const lines = text.split(/\r?\n/).map((l) => (l.trim().startsWith("#") ? "" : stripComment(l).replace(/\s+$/, "")));
  let i = 0;

  function block(indent) {
    // Decide whether this block is a list or a map from its first meaningful line.
    while (i < lines.length && lines[i].trim() === "") i++;
    if (i >= lines.length) return null;
    const first = lines[i];
    if (indentOf(first) < indent) return null;
    return first.trim().startsWith("- ") || first.trim() === "-" ? list(indentOf(first)) : map(indentOf(first));
  }

  function blockScalar(indent, style) {
    const parts = [];
    while (i < lines.length) {
      const l = lines[i];
      if (l.trim() === "") { parts.push(""); i++; continue; }
      if (indentOf(l) < indent) break;
      parts.push(l.slice(indent));
      i++;
    }
    while (parts.length && parts[parts.length - 1] === "") parts.pop();
    return style === "|" ? parts.join("\n") : parts.join(" ").replace(/\s+/g, " ").trim();
  }

  function value(rest, indent) {
    const r = rest.trim();
    if (r === ">" || r === "|" || r === ">-" || r === "|-") {
      while (i < lines.length && lines[i].trim() === "") i++;
      const childIndent = i < lines.length ? indentOf(lines[i]) : indent + 2;
      return childIndent > indent ? blockScalar(childIndent, r[0]) : "";
    }
    if (r === "") {
      const saved = i;
      const child = block(indent + 1);
      if (child === null) { i = saved; return null; }
      return child;
    }
    return scalar(r);
  }

  function map(indent) {
    const out = {};
    while (i < lines.length) {
      const l = lines[i];
      if (l.trim() === "") { i++; continue; }
      const ind = indentOf(l);
      if (ind < indent) break;
      if (ind > indent) { i++; continue; }
      const t = l.trim();
      if (t.startsWith("- ")) break;
      const m = t.match(/^("[^"]*"|'[^']*'|[^:]+?)\s*:(.*)$/);
      if (!m) { i++; continue; }
      i++;
      out[m[1].replace(/^["']|["']$/g, "")] = value(m[2], indent);
    }
    return out;
  }

  function list(indent) {
    const out = [];
    while (i < lines.length) {
      const l = lines[i];
      if (l.trim() === "") { i++; continue; }
      const ind = indentOf(l);
      if (ind < indent) break;
      if (ind > indent) { i++; continue; }
      const t = l.trim();
      if (!t.startsWith("-")) break;
      const rest = t.slice(1).trim();
      i++;
      if (rest === "") { out.push(block(indent + 1)); continue; }
      const m = rest.match(/^("[^"]*"|'[^']*'|[^:{\[]+?)\s*:(.*)$/);
      if (m && !rest.startsWith("{") && !rest.startsWith("[")) {
        // "- key: value" starts an inline map whose further keys sit at indent + 2
        const item = {};
        item[m[1].replace(/^["']|["']$/g, "")] = value(m[2], indent + 2);
        // remaining keys of the same item
        while (i < lines.length) {
          const n = lines[i];
          if (n.trim() === "") { i++; continue; }
          const nind = indentOf(n);
          if (nind <= indent) break;
          const nt = n.trim();
          if (nt.startsWith("- ")) break;
          const mm = nt.match(/^("[^"]*"|'[^']*'|[^:]+?)\s*:(.*)$/);
          if (!mm) { i++; continue; }
          i++;
          item[mm[1].replace(/^["']|["']$/g, "")] = value(mm[2], nind);
        }
        out.push(item);
      } else {
        out.push(scalar(rest));
      }
    }
    return out;
  }

  const result = block(0);
  return result ?? {};
}

// Walk an object with a dotted path, returning undefined when any step is missing.
export function dig(obj, dotted) {
  return dotted.split(".").reduce((o, k) => (o && typeof o === "object" ? o[k] : undefined), obj);
}
