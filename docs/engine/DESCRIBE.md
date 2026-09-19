# Describe: a sentence becomes a workflow

The describe bar has one entry point, `session.describe` in `packages/engine/session.py`.
The CLI subcommand `describe` and the studio route `POST /api/describe` are two thin shells
around it and return the same JSON. Nothing in this path runs a step; it plans, and in
`create` mode it saves the workflow and its session. Spec: Part 2C of
`docs/superpowers/specs/2026-09-20-general-creative-studio-design.md`.

## The CLI

```bash
python packages/engine/cli.py describe --client epalle --text "change the character in my 50 reference images from red-dress to our persona, then make a carousel of 10 slides for each" --json
python packages/engine/cli.py describe --client epalle --text "a lookbook of one persona across a city evening, neon noir" --mode plan
python packages/engine/cli.py describe --client epalle --session s1 --text "now add captions and export" --json
python packages/engine/cli.py describe --client epalle --workflow faceswap --text "also a carousel for each" --answer collection=red-dress --json
```

| Flag | Meaning |
|---|---|
| `--client C` | required; the workspace key, a folder in `brands/` with a `brand.yaml`. An unknown key is a clean error, exit 1. |
| `--text T` | required; plain words, or the step grammar (`carousel@each slides=10`). |
| `--session S` | a session id. A second `describe` with the same id extends that session's workflow. New when unseen. |
| `--workflow W` | a saved workflow id to extend. Its session is found or created; an author workflow stays on the author route, a workflow with `stages` goes to the director. |
| `--mode plan\|create\|direct` | `plan` writes nothing (`id` is `null`, `saved` false); `create` (default) saves the workflow and the session; `direct` forces the director route. |
| `--answer KEY=VALUE` | repeatable; answers a `questions[]` entry: `collection=red-dress`, `persona=...`, `slides=10`, `kind=carousel`, `each=carousel`. |
| `--json` | print the contract below instead of the reply and a step table. |

Exit codes: 0 with the contract; 2 with `{"error", "refused", ...}` when the brief is refused
(it names a person: `refused: true`) or nothing in it names a step to add; 1 on any other
failure (unknown client, validation), still as JSON with `--json`, never a traceback.

## The route

`session.py` decides which grammar reads the sentence and records it as `Session.route`
(`director` | `author`; `session.ROUTES`). The choice, in order:

1. `--mode direct`: director.
2. An existing session (by `--session`, or the one attached to `--workflow`): its saved route.
3. `--workflow` names a saved workflow with no session: author, unless the workflow has
   `stages` (the director made it), then director.
4. Otherwise `intents.route(text)`: director when the sentence names a **profile** (a
   lookbook, an explainer, a music video piece; `profiles.find`) or a **preset** (a look;
   `intents.matched_preset`), author for everything else.

The director route grows scenes, angles and picks from a brief (`director.plan`, the same
path as `cli.py say`); in `plan` mode it previews without writing. The author route names
steps and wires them by type: `workflow_author.parse_brief` reads the sentence into steps,
`@each` flags, params, collections and continuations; `from_brief` builds the workflow;
`extend` appends to a saved one. On both routes `intents.refusal(text)` runs first: a
person's name or a likeness phrase is refused before any node exists.

## The response

Both shells return this object; `POST /api/describe` returns it verbatim as the body.

```json
{
  "id": "change-the-character-in-my-50-reference-images-from-red-dres",
  "workflow": { "...the saved .studio.json document (nodes, edges, gaps, source, stages?)..." },
  "plan": {
    "steps": [
      {"id": "n2", "kind": "klein-headswap", "step": "character-swap@each", "label": "Head swap (no LoRA)",
       "each": true, "params": {}, "backend": "comfy", "status": "ready", "consent": true,
       "category": "edit", "stage": null, "expected_count": null, "role": null}
    ],
    "gaps": [],
    "estimate": {"usd": 0.1545, "gpu_seconds": 336.0, "basis": "assumed", "items": 3, "items_basis": "disk",
                 "budget_usd": 0.0, "per_node": [{"node": "n3", "kind": "carousel", "items": 30, "usd": 0.138,
                 "gpu_seconds": 300.0, "basis": "assumed"}], "note": "item counts read from the reference folders on disk"},
    "consent_required": true,
    "inputs": [{"node": "n7", "kind": "reference-images", "param": "folder", "role": "face", "expected_count": null,
                "prompt": "Which reference collection?", "options": ["red-dress", "wardrobe-red-dress"]}],
    "pending_picks": []
  },
  "steps": ["reference-images", "reference-images", "character-swap@each", "carousel@each", "brand-kit", "compositor", "export"],
  "added": [],
  "continuations": [{"step": "wan-i2v", "each": true, "params": {}, "kind": "wan-i2v",
                     "estimate": {"usd": 0.09, "basis": "assumed", "items": 3}}],
  "questions": [{"key": "collection", "prompt": "Which reference collection did you mean by 'persona'?", "options": ["red-dress"]}],
  "route": "author",
  "mode": "create",
  "extended": false,
  "saved": true,
  "session": {"id": "...", "client": "epalle", "workflow_id": "...", "brief": {}, "utterances": ["..."], "version": 1,
              "history": [], "pending_picks": [], "route": "author"},
  "reply": "Created \"...\": character-swap@each, carousel@each; 3 items per fan-out step; est $0.1545 (assumed); consent notice applies. Nothing runs until you press Run."
}
```

Field by field:

- `id`: the workflow id when saved, `null` in `plan` mode or while a question is open.
- `workflow`: the full `.studio.json` document, saved or not. The canvas can render it
  straight away.
- `plan` (`session.plan_of`): the plan card.
  - `steps[]`: one per node in graph order. `step` is the name the brief used (`data.alias`,
    e.g. `character-swap` on kind `klein-headswap`) with `@each` when the node fans out;
    `status` is one of `ready` (a comfy node with a port map, or a python node in
    `runner.LOCAL_STEPS`), `needs-setup`, `gap`, `input` (a person fills it) or `decide` (a
    pick); `consent` mirrors the catalogue flag; `expected_count` and `role` come from the
    node data (below).
  - `gaps[]`: the workflow's declared gaps (`wf.gaps`).
  - `estimate` (`session.estimate_workflow`): USD and GPU seconds with items included. A
    fan-out node costs its single run times its items; a carousel is priced per slide.
    `items` is the batch size (the biggest input folder); `items_basis` says where that
    number came from: `disk` (the folder was counted), `brief` (the sentence said "50"),
    `assumed` (no folder yet, 1 until there is). `budget_usd` is the engine cap from
    `brands/_presets/engine.yaml`.
  - `inputs[]`: input nodes a person still has to fill, with a `prompt` and, for
    `reference-images`, the workspace's known collections as `options`.
  - `pending_picks[]`: pick nodes with nothing picked.
- `steps[]`: the `plan.steps[].step` names, flat, for tests and logs.
- `added[]`: node ids the extension added (empty on a first describe).
- `continuations[]`: proposed next stages the sentence offered as options ("we could then
  make a reel for each"), each with `step`, `each`, `params`, the resolved `kind` and an
  `estimate` scaled by the batch. Empty when "then" made the clause a step instead. Read from
  the parse, else from `workflow.source.continuations`. The "Continue with" strip calls
  `describe` again with `--workflow <id>` and the continuation's step.
- `questions[]` (at most two): `{"key", "prompt", "options"}`. Keys the parser asks for:
  `collection` (a named collection is not on disk), `kind` (no step could be inferred).
  While a question is open nothing is saved (`saved: false`, `id: null`); answer with
  `--answer key=value` (`answers` in the route body) and describe again.
- `route`: `director` | `author`, as chosen above and stored on the session.
- `mode`: the mode that was asked for.
- `extended`: true when the call added to an existing workflow.
- `saved`: whether the workflow and session were written.
- `session`: the `Session` dataclass when saved (`id`, `client`, `workflow_id`, `brief`,
  `utterances`, `version`, `history`, `pending_picks`, `route`), else `{"id": S}` when a
  session id was given, else `null`.
- `reply`: one sentence for the bar. A refused or failed call has `error`, `refused`,
  `route: null`, `id: null`, `plan: null`, empty `questions` and `continuations`, and the
  message repeated as `reply`.

### Node data keys the contract relies on

`workflow.nodes[].data` is what the canvas stores per node. The describe path adds:

| Key | Set by | Meaning |
|---|---|---|
| `alias` | `workflow_author.author` | the step name the brief used when it differs from the node kind (`character-swap` on `klein-headswap`); `plan.steps[].step` shows it |
| `each` | `author` / `extend` | the node runs once per item on its iterated port (`workflow_author.is_each`, `iterated_port`) |
| `expected_count` | `from_brief` | the item count the sentence stated ("my 50 reference images"), used by the estimate until the folder is on disk |
| `role` | `_split_shared_inputs` | why a second input node exists: the port it fills (`face`, `clothes`) when one folder was wired to two required image ports |
| `collection` | `from_brief` / `_split_shared_inputs` | the reference collection name behind `params.folder` (`brands/<client>/references/<collection>`) |

### `workflow.source`

`source.brief` is the sentence. `source.continuations[]` keeps the options the first parse
offered, so a later call can propose them again. `source.extended[]` is appended by
`workflow_author.extend` on every "Continue with": `{"steps": [...asked], "added": [ids],
"skipped": [steps already present], "on": "YYYY-MM-DD"}`. A workflow with `stages` gets one
more stage per extension (`extendN`) and the new nodes carry `data.stage = extendN`.

## `POST /api/describe`

`packages/studio-ui/client/app/api/describe/route.js`. Body:

```json
{"workspace": "epalle", "text": "...", "mode": "create", "session": "s1", "workflow": "faceswap",
 "answers": {"collection": "red-dress", "slides": "10"}}
```

`client` is accepted for `workspace`, `message` for `text`. The route validates (a
workspace, not the template library; text 2 to 2,000 characters; mode in the three; ids
match `^[a-z0-9][a-z0-9_-]{0,79}$`; answer keys `^[a-z][a-z0-9_]{0,31}$`, values cut at 200
characters, empty ones dropped), then spawns
`python packages/engine/cli.py describe --client ... --text ... --mode ... --json [--session] [--workflow] [--answer k=v]...`
and returns its JSON. An exit-2 JSON error is returned as the body with status 422 when
`refused` is true, 400 otherwise; a spawn failure is 500; the route's own validation errors
are 400 with the same error shape.

### `STUDIO_PYTHON` (`lib/python.js`)

Every API route runs repo scripts through `runPython(script, args)`: `python` by default
(not `uv`, which is not on every PATH), or the `STUDIO_PYTHON` environment variable when
set: `python3`, `C:\venv\Scripts\python.exe`, or `uv run --with pyyaml python` (split on
spaces, quotes respected; the first token is the executable, the rest lead the arguments).
Runs at the repo root, never through a shell, with `PYTHONIOENCODING=utf-8` and a 120 s
timeout; stdout is parsed as JSON from the first `{` or `[`, so a warning printed before the
JSON does not break the route. A missing interpreter reads
`Python was not found as "<cmd>". Install Python 3 or set STUDIO_PYTHON.`

## Tests

`tests/test_describe.py` pins the contract (the acceptance sentence returns
`[reference-images, character-swap@each, carousel@each, compositor, export]` with
`carousel.params.slides == 10` and empty `continuations`); `tests/test_fan_out_contract.py`
pins `is_each`, `iterated_port`, `split_each` and `EACH_BACKENDS`.
