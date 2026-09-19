# References for {{name}}

Every folder under `references/` is one collection: media files plus a `collection.json`
that says how the studio may use them. The engine reads the JSON before it binds a file
to any step; without it, a folder is treated as inspiration only, rights unclear, no
consent.

## The three fields that gate a run

| Field | Values | What it allows |
|---|---|---|
| `use` | `inspiration`, `data` | `inspiration` reaches a prompt as fragments (palette, framing, pacing). `data` is fed straight into a node port: a face, an outfit, a room, a product. |
| `rights` | `owned`, `licensed`, `unclear` | `data` needs `owned` or `licensed`. `unclear` can only inspire. |
| `consent` | `true`, `false` | A real person's likeness may be used as data only with `consent: true`, which means a written release exists. Record where it is kept in `notes`. |

Fictional characters (a generated persona, geometric fixtures, an illustrated mascot) are
`rights: owned` and `consent: false`; there is no person to release.

## Rules

- A real face is never swapped, animated, dressed or trained on without a written release.
  There is no exception for public figures, customers, staff or friends.
- Harvested pins, screenshots and other people's posts are `inspiration`, `unclear`. They
  shape prompts. They are never fed to a port.
- Take the grammar, never the images. A studied creator's framing, rhythm and restraint are
  fair to learn; their shots, scripts, locations and specific images are not.
- Bought or downloaded stock is `licensed` only if the licence covers AI training or
  editing, whichever the step does. Note the licence in `notes`.

## Layout

```
references/
  <collection-name>/
    collection.json
    <files>.png | .jpg | .webp | .mp4 | .mov
```

Create a collection by copying `brands/_kit/collection.json.example` into a new folder and
editing it, or with `python packages/engine/references.py pull --brand {{key}} --name <name> "<search>"`
for harvested inspiration (dry run by default).
