# The Director Engine

Talk, and a branching production workflow grows on the canvas. You describe the piece; the
engine writes a storyboard, makes several camera angles per scene, waits for you to pick the
keepers, turns the picks into clips, dresses and relocates shots, and ends with an edit and
an export. Nothing generates, spends or publishes unless the run mode and the control plane
let it.

## Two grammars, never a likeness

| Layer | File | What it decides |
|---|---|---|
| **Profile** (the craft) | `brands/_presets/profiles.yaml` | What kind of piece this is: beat sheet, default scene count, narration, consistency locks, generator route, per-ratio composition. Lookbook, stickman explainer, children's song, 2D animation short, music video, UGC ad, product demo. |
| **Preset** (the look) | `brands/_presets/directors.yaml` | Framing, lens, palette, pacing, blocking, grade, motion, negatives. Symmetric pastel, neon noir, handheld vérité, one take, high-key beauty, anamorphic epic, kinetic music video, minimal editorial, retro VHS, golden hour romance. |

Both are grammar in our own words. A test refuses any preset or profile that names a person
or a likeness. The stickman profile follows the shape of
[kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director) (MIT):
copy in, a confirmed beat sheet, then one locked prompt per scene, re-composed per aspect
ratio. Add a profile by adding a block to `profiles.yaml`; the tests check its keys.

## How a brief becomes a workflow

`packages/engine/director.py` is deterministic: the same brief always gives the same graph.

1. **References.** One input node per reference collection. A role whose references are
   owned or licensed data (or a real person with a written release) gets a character sheet
   and a RefMod character. Anyone else gets a declared gap, never a face.
2. **Storyboard.** One brief node per scene, named by the profile's beats, placed at the
   scene hints you gave ("rooftop at golden hour").
3. **Stills.** Per scene, K angle nodes (3, 5, 10 or 20) from the camera table, each with a
   composed prompt: scene, camera, preset fragments, profile locks, aspect note. With a
   character, the generator is H3 reference image; without, Krea 2.
4. **Pick.** A `pick` step keeps up to k. Nothing downstream runs until you choose.
5. **Dressing.** Wardrobe, room and jewellery steps attach only when a collection with
   owned or licensed rights is present.
6. **Motion.** Still to video for the scene's seconds, or motion control when a reference
   clip is attached. VFX you name become steps where a step exists (`upscale`) and gaps
   where none does (`relight`, anything unknown).
7. **Edit and ending.** Cut, captions, a voiceover when the profile narrates, then export.
   Publishing steps exist only if you ask and always need a person.

## Talking to it

Studio: open a client, choose **Direct it**, or press **Director** on any canvas. CLI:

```bash
uv run --with pyyaml python packages/engine/cli.py say --client epalle --session s1 --text "a lookbook of one persona across a city evening, neon noir"
uv run --with pyyaml python packages/engine/cli.py say --client epalle --session s1 --text "add a scene at a market at dawn"
uv run --with pyyaml python packages/engine/cli.py plan --brief tests/fixtures/engine_brief.json
```

Things it understands (`packages/engine/session.py`): a kind of piece or a look by name;
"add a scene at …"; "N scenes"; "N angles"; "N takes"; "clips 6 seconds long"; "wardrobe from
my red-dress" (rights: *my* = owned, *licensed*, otherwise unclear); "location …",
"jewellery …", "motion clip …"; "vfx relight"; "add role bob from avatar-bob"; "keep at
scene1.pick.keep: 1, 3, 4"; "switch to auto mode"; "run the next stage"; "undo". Anything
else is added to the brief as a note.

Every utterance is saved in `brands/<client>/workflows/<id>.session.json`. Replaying the
list rebuilds the same workflow, byte for byte. Picks and results survive a rebuild.

## Run modes

| Mode | What happens |
|---|---|
| **Dry run** | Every step writes a manifest saying what it would do. Nothing is submitted. |
| **Approve** | Each stage is an `engine_stage` task in the control plane. It runs only after a person approves its cost estimate. |
| **Auto** | One `engine_run` approval covers the workflow. The runner stops at any pick nobody has made and before any publishing step. |

Budget lives in `brands/_presets/engine.yaml` (`budget_usd`, default 0). A human raises it.
Estimates come from the same file's seconds-per-step table; every figure says whether it
was measured or assumed, and each manifest records the actual seconds.

Results: `brands/<client>/runs/<workflow>/<node>/<run>/manifest.json` plus the files, and
`data.results[]` on the node. A node is `completed` only when ComfyUI's history shows
outputs and they were fetched. Queued is not success.

## What runs a step

`workflows/<pack>/<name>.ports.json` says which ComfyUI node receives each studio port,
the prompt, the negative, the seed and the count, and which node saves the output. See
[PORT-MAPS.md](PORT-MAPS.md). `python` steps (cut, captions, voiceover) are recorded, not run,
by the engine for now; run them from their own CLIs.

## References

Collections live in `brands/<client>/references/<name>/` with a `collection.json`
(`use`, `rights`, `consent`). `use: data` needs owned or licensed rights; unclear rights
inspire prompts only; a real face as data needs consent. [POSSIBILITIES.md](POSSIBILITIES.md)
lists what each kind of reference can drive.

## Voice

The microphone button uses the browser's own speech recognition when it has one, else
records a clip and transcribes it locally with whisper. An ElevenLabs conversational agent
can front the same `/api/director` endpoint through client-side tools once
`set_secret.py elevenlabs` holds a key and you have an agent id; nothing is wired to a paid
voice service by default.
