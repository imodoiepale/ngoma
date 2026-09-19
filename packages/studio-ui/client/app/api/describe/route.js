import { runPython } from "../../../lib/python";
import { StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;
const MODES = new Set(["plan", "create", "direct"]);
const ANSWER_KEY = /^[a-z][a-z0-9_]{0,31}$/;

// The describe bar. A sentence becomes a workflow (or extends one) through
// `packages/engine/cli.py describe`, which decides between the author route (named steps,
// wired by type) and the director route (a profile or preset was named). The response is
// the contract in docs/superpowers/specs/2026-09-20-general-creative-studio-design.md,
// Part 2C: id, workflow, plan, continuations, questions, route, reply. Nothing runs here.
//
// Body: { workspace|client, text, mode?: "plan"|"create"|"direct", session?, workflow?, answers?: {k: v} }
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const client = body.workspace || body.client;
  const text = String(body.text || body.message || "").trim();
  const mode = body.mode || "create";
  const { session, workflow } = body;
  try {
    if (client === TEMPLATES) throw new StudioError("Describe work for a workspace, not the template library.");
    await workflowDir(client);
    if (text.length < 2) throw new StudioError("Describe what you want to make first.");
    if (text.length > 2000) throw new StudioError("Keep the description under 2,000 characters.");
    if (!MODES.has(mode)) throw new StudioError("mode is plan, create or direct.");
    if (session && !ID.test(session)) throw new StudioError("A session needs a short id.");
    if (workflow && !ID.test(workflow)) throw new StudioError("That workflow id is not valid.");
    const args = ["describe", "--client", client, "--text", text, "--mode", mode, "--json"];
    if (session) args.push("--session", session);
    if (workflow) args.push("--workflow", workflow);
    const answers = body.answers && typeof body.answers === "object" ? body.answers : {};
    for (const [k, v] of Object.entries(answers)) {
      if (!ANSWER_KEY.test(k)) throw new StudioError(`Answer key ${k} is not valid.`);
      if (v === null || v === undefined || v === "") continue;
      args.push("--answer", `${k}=${String(v).slice(0, 200)}`);
    }
    const res = await runPython("packages/engine/cli.py", args, { timeout: 120000 });
    if (res.json && res.json.error) {
      // a refused brief (a person's name), an unknown client, nothing to add: exit 2 with a JSON body
      return Response.json(res.json, { status: res.json.refused ? 422 : 400 });
    }
    if (!res.ok || !res.json) throw new StudioError(res.error || "The engine did not answer.", 500);
    return Response.json(res.json);
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message || "Could not describe that.", refused: false, id: null, plan: null,
      questions: [], continuations: [], route: null, reply: e.message || "" }, { status });
  }
}
