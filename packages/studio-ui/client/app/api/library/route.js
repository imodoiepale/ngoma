import { DatabaseSync } from "node:sqlite";
import path from "node:path";
import fs from "node:fs";

export const dynamic = "force-dynamic";

// The archive lives outside this app, next to it in the workspace. Overridable so the
// same build works on the RunPod volume, where it sits under /workspace/epalle.
const DB_PATH =
  process.env.EPALLE_LIBRARY_DB ||
  path.resolve(process.cwd(), "../../libraries/library.sqlite3");
const WORKFLOW_DIR =
  process.env.EPALLE_WORKFLOW_DIR ||
  path.resolve(process.cwd(), "../../libraries/workflows");

function openDb() {
  if (!fs.existsSync(DB_PATH)) return null;
  return new DatabaseSync(DB_PATH, { readOnly: true });
}

function listWorkflows() {
  // Read the real directory rather than a hardcoded list, so the page cannot drift
  // from what is actually on disk.
  if (!fs.existsSync(WORKFLOW_DIR)) return [];
  const groups = [];
  for (const entry of fs.readdirSync(WORKFLOW_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const items = [];
    const walk = (dir, depth) => {
      if (depth > 4) return;
      for (const child of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, child.name);
        if (child.isDirectory()) walk(full, depth + 1);
        else if (child.name.toLowerCase().endsWith(".json")) {
          items.push({
            name: child.name.replace(/\.json$/i, ""),
            relPath: path.relative(WORKFLOW_DIR, full).split(path.sep).join("/"),
            bytes: fs.statSync(full).size,
          });
        }
      }
    };
    walk(path.join(WORKFLOW_DIR, entry.name), 0);
    items.sort((a, b) => a.name.localeCompare(b.name));
    groups.push({ group: entry.name, count: items.length, items });
  }
  groups.sort((a, b) => b.count - a.count);
  return groups;
}

export async function GET(request) {
  const query = (new URL(request.url).searchParams.get("q") || "").trim();
  const db = openDb();

  if (!db) {
    return Response.json(
      {
        ok: false,
        error: `library index not found at ${DB_PATH}. Build it with: python outputs/libraries/tools/build_library_index.py`,
        workflows: listWorkflows(),
      },
      { status: 503 },
    );
  }

  try {
    const stats = {
      assets: db.prepare("SELECT count(*) c FROM assets").get().c,
      bytes: db.prepare("SELECT coalesce(sum(bytes),0) b FROM assets").get().b,
      sources: db
        .prepare("SELECT count(DISTINCT source_id) c FROM assets WHERE source_id <> ''")
        .get().c,
      kinds: db
        .prepare(
          "SELECT kind, count(*) c FROM assets GROUP BY kind ORDER BY c DESC LIMIT 12",
        )
        .all(),
    };

    let results = [];
    if (query) {
      // FTS5 MATCH, same query shape as tools/search_library.py. Quote the whole
      // string so user punctuation cannot become FTS operator syntax.
      const safe = `"${query.replace(/"/g, '""')}"`;
      results = db
        .prepare(
          `SELECT path, title, snippet(search, 2, '[', ']', '…', 18) AS snippet
             FROM search WHERE search MATCH ? ORDER BY rank LIMIT 40`,
        )
        .all(safe);
    }

    return Response.json({
      ok: true,
      dbPath: DB_PATH,
      query,
      stats,
      results,
      workflows: listWorkflows(),
    });
  } catch (error) {
    return Response.json({ ok: false, error: String(error) }, { status: 500 });
  } finally {
    db.close();
  }
}
