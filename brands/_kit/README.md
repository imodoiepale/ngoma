# The workspace kit

A workspace is a folder `brands/<key>/` with a `brand.yaml`. That is the only requirement
the studio enforces: `workflow_author.clients()` and the UI's `listClients()` both list any
such folder, and everything else hangs off it. This folder holds the example files a new
workspace starts from and the minimum each must contain.

Do not edit a workspace by hand-copying these files. Use the scaffold, which fills the
placeholders and validates the result:

```bash
python packages/strategy/workspace.py new <key> --name "Display Name" [--accent "#30E0A8"] [--kind fashion] [--from epalle] [--dry-run] [--root DIR]
python packages/strategy/workspace.py list
python packages/strategy/workspace.py check <key>
```

`--dry-run` prints what would be written and writes nothing. `--from <key>` starts from an
existing workspace's `brand.yaml` and `styles/` instead of the example, with the key and
name rewritten and a note that the palette and grammars are inherited and must be
re-measured. `--root DIR` scaffolds under a different `brands/` folder, for tests.

Keys are lowercase, `a-z0-9-`, and may not start with `_`. `_presets`, `_templates`,
`_business` and `_kit` are the studio's own folders and are refused.

## Files here

| File | Becomes | Purpose |
|---|---|---|
| `brand.yaml.example` | `brands/<key>/brand.yaml` | the kit: name, kind, palette, logo path, typography, voice, languages, masters, claim safety |
| `collection.json.example` | `brands/<key>/references/<name>/collection.json` | the rights record every reference collection needs |
| `references.README.md` | `brands/<key>/references/README.md` | the rights rules, in the workspace where the files land |

Placeholders `{{key}}`, `{{name}}`, `{{name_upper}}`, `{{accent}}`, `{{kind}}` and
`{{date}}` are filled by the scaffold.

## What a workspace folder holds

```
brands/<key>/
  brand.yaml            the kit (required)
  assets/logo/          the logo master, composited and never generated
  references/           collections, each with collection.json (see references/README.md)
  workflows/            *.studio.json, what the canvas and the author read and write
  runs/                 results and manifests; gitignored (brands/*/runs/ in .gitignore)
  styles/               optional style grammars (brandkit needs at least one to build a request)
  calendar/             optional seed.yaml and plans
```

## Minimum `brand.yaml`

`check` fails on a kit missing any of these:

| Key | Why |
|---|---|
| `brand` | the key; must equal the folder name |
| `display_name` (or `name`) | the name the UI and the author show |
| `palette.measured` | a mapping of at least one `#RRGGBB` value; `accent` is the workspace accent in the UI |
| `logo.master` | path, relative to the workspace, of the master that gets composited |
| `logo.rule` | `COMPOSITE_ONLY`; the rule the compositor follows |
| `claim_safety.disclosure` | the disclosure line the compositor sets on AI-assisted imagery |

`check` warns, and still passes, on: a missing logo file at `logo.master` (the scaffold
cannot invent one), no `kind`, no `voice`, no `languages.primary`, no `positioning`
(the compositor's copy block reads it), no `styles/` grammar (brandkit refuses to build a
request without one), and a reference folder with media but no `collection.json`
(inspiration only until it has one).

## Minimum `collection.json`

```json
{ "name": "<folder name>", "use": "inspiration | data", "rights": "owned | licensed | unclear",
  "kind": "image | video", "consent": false, "source": "manual", "notes": [] }
```

`use: data` requires `rights: owned` or `licensed`. A real person as data requires
`consent: true` and a written release. The runner blocks a consent step whose collection
does not satisfy this, and `check` reports it.

## The first two workspaces

`epalle` (a music project) and `ongea-pesa` (a voice-activated M-Pesa assistant by NSAIT)
were built by hand before this kit existed. Both pass `check`. Their `brand.yaml` files
carry more than the minimum (narrative arcs, measured and as-shipped palettes, two visual
systems) and are worth reading as examples of a kit that was measured rather than assumed.
