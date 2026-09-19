// One way for every API route to run a repo Python script: `python` by default (not `uv`,
// which is not on PATH on every machine), `STUDIO_PYTHON` when set ("python3",
// "C:\\venv\\Scripts\\python.exe", or "uv run --with pyyaml python" - split on spaces),
// cwd at the repo root, UTF-8 output, a timeout, and never a shell. The result is a plain
// object: parsed JSON when stdout is JSON, otherwise the raw text, plus a structured error.
import { execFile } from "node:child_process";
import { REPO } from "./studio";

const DEFAULT_TIMEOUT_MS = 120000;
const MAX_BUFFER = 32 * 1024 * 1024;

export function pythonCommand() {
  const configured = (process.env.STUDIO_PYTHON || "").trim();
  if (!configured) return { cmd: "python", lead: [] };
  const parts = configured.match(/(?:[^\s"]+|"[^"]*")+/g) || ["python"];
  const clean = parts.map((p) => p.replace(/^"|"$/g, ""));
  return { cmd: clean[0], lead: clean.slice(1) };
}

function tryJson(text) {
  const t = (text || "").trim();
  if (!t) return null;
  // the script may print warnings before the JSON; take the first { or [ that parses
  const start = Math.min(...["{", "["].map((c) => t.indexOf(c)).filter((i) => i >= 0));
  if (!Number.isFinite(start)) return null;
  try {
    return JSON.parse(t.slice(start));
  } catch {
    return null;
  }
}

function lastLines(text, n = 2) {
  return (text || "").toString().split("\n").map((l) => l.trim()).filter(Boolean).slice(-n).join(" ");
}

/**
 * Run `python <script> ...args` at the repo root.
 * @param {string} script  path relative to the repo root, e.g. "packages/engine/cli.py"
 * @param {string[]} args  arguments, passed as an array (never through a shell)
 * @param {{timeout?: number, maxBuffer?: number}} [options]
 * @returns {Promise<{ok: boolean, code: number|null, stdout: string, stderr: string, json: any, error: string|null, timedOut: boolean}>}
 */
export function runPython(script, args = [], options = {}) {
  const { cmd, lead } = pythonCommand();
  const timeout = options.timeout || DEFAULT_TIMEOUT_MS;
  const env = { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" };
  return new Promise((resolve) => {
    execFile(cmd, [...lead, script, ...args], { cwd: REPO, env, timeout, windowsHide: true, maxBuffer: options.maxBuffer || MAX_BUFFER },
      (err, stdout, stderr) => {
        const out = (stdout || "").toString();
        const errText = (stderr || "").toString();
        const json = tryJson(out);
        if (!err) return resolve({ ok: true, code: 0, stdout: out, stderr: errText, json, error: null, timedOut: false });
        const timedOut = err.killed && err.signal === "SIGTERM";
        let error;
        if (err.code === "ENOENT") error = `Python was not found as "${cmd}". Install Python 3 or set STUDIO_PYTHON.`;
        else if (timedOut) error = `The script did not finish within ${Math.round(timeout / 1000)} seconds.`;
        else error = (json && json.error) || lastLines(errText) || lastLines(out) || err.message || "The script failed.";
        resolve({ ok: false, code: typeof err.code === "number" ? err.code : null, stdout: out, stderr: errText, json, error, timedOut });
      });
  });
}
