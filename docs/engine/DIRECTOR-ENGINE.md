# The Director Engine

Talk, and a branching production workflow grows on the canvas of any workspace. You describe the piece; the
engine writes a storyboard, makes several camera angles per scene, waits for you to pick the
keepers, turns the picks into clips, dresses and relocates shots, and ends with an edit and
an export. Nothing generates, spends or publishes unless the run mode and the control plane
let it.

## Two grammars, never a likeness

| Layer | File | What it decides |
|---|---|---|
| **Profile** (the craft) | `brands/_presets/profiles.yaml` | What kind of piece this is: beat sheet, default scene count, narration, consistency locks, generator route, per-ratio composition. Lookbook, stickman explainer, children's song, 2D animation short, music video, UGC ad, product demo. |
| **Preset** (the look) | `brands/_presets/directors.yaml` | Framing, lens, palette, pacing, blocking, grade, motion, negatives. Symmetric pastel, neon noir, handheld vérité, one take, high-key beauty, anamorphic epic, kinetic music video, minimal editorial, retro VHS, golden hour romance, papercraft relief, painterly cel, impact slow motion. |

Both are grammar in our own words. A test refuses any preset or profile that names a person
or a likeness. The stickman profile follows the shape of
[kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director) (MIT):
copy in, a confirmed beat sheet, then one locked prompt per scene, re-composed per aspect
ratio. Add a profile by adding a block to `profiles.yaml`; the tests check its keys.

## Prompt grammar

Every prompt the engine sends is composed from three sources and nothing else: the brief
(scene text and hints), the preset (the look) and the profile (the locks). Both composers
live in `packages/engine/presets.py` and are deterministic, so the same brief gives the same
prompt byte for byte.

**Stills** use `compose_prompt`: the scene text, the camera angle's phrase from the
`cameras` table, the preset fragments for that scene (a framing, a blocking, the lens, the
palette, the grade, the motion) and the profile locks with the aspect note, joined into one
sentence chain. The node also carries a `negative` built from the preset's and the
profile's negatives.

**Motion** (`image-to-video`, `motion-control`) uses `compose_motion_prompt`, which writes
the block structure the creator guides converge on, one line per block:

1. `0-<seconds>s:` one timecoded beat for the scene's length: shot size and angle (the
   preset framing), camera motion (the preset `motion`), the action (the scene text and
   blocking). A speed ramp or a slow-motion beat is placed here by the preset's `motion`.
2. `Style:` lens, palette and grade, held across the whole clip.
3. `Hold constant across the whole clip:` the profile locks (same face and body, wardrobe as
   attached, counts, the aspect note).
4. `Audio:` sound effects and diegetic sound only; no music, no dialogue, no subtitles.
5. `Strictly exclude:` the preset's and the profile's negatives.

The runner binds the node's `prompt` into the workflow's prompt widget through the port map
(see [PORT-MAPS.md](PORT-MAPS.md)); motion nodes are bound the same way stills are.

**No names.** `presets.FORBIDDEN` is one regex used at three levels: the preset loader
refuses a preset that names a person or a likeness; the profile loader does the same; and
`director.plan` refuses a brief whose `idea`, `title` or `scene_hints` name a director or a
cinematographer, or use "shot by", "in the style of" or "directed by". A pasted guide
prompt fails loudly with "names a person or a likeness" instead of being sent. Describe the
look instead, or add it as a preset in your own words.

Where the grammar comes from, and how to write prompts by hand in the same shape:
`.claude/skills/shot-prompt-architect/SKILL.md` (the beat structure, camera and lighting
vocabulary, turning a note on a bad clip into a prompt change),
`.claude/skills/style-block/SKILL.md` (extracting one rendering style from references and
emitting it as a preset), and the creator notes `docs/creators/aikami/NOTES.md` and
`docs/creators/pjaccetturo/NEXUS-SKILL.md`.

## How a brief becomes a workflow

`packages/engine/director.py` is deterministic: the same brief always gives the same graph.

1. **References.** One input node per reference collection. A role whose references are
   owned or licensed data (or a real person with a written release) gets a character sheet,
   which H3 reads as its identity picture. Anyone else gets a declared gap, never a face.
2. **Storyboard.** One brief node per scene, named by the profile's beats, placed at the
   scene hints you gave ("rooftop at golden hour").
3. **Stills.** Per scene, K angle nodes (3, 5, 10 or 20) from the camera table, each with a
   composed prompt: scene, camera, preset fragments, profile locks, aspect note. With a
   character, the generator is H3 reference image; without, Krea 2.
4. **Pick.** A `pick` step keeps up to k. Nothing downstream runs until you choose.
5. **Dressing.** Wardrobe, room and jewellery steps attach only when a collection with
   owned or licensed rights is present. The room step needs a trained LoRA for the lead
   (`roles[].lora`); without one the location is a gap and stays in the prompt.
6. **Motion.** Still to video for the scene's seconds, or motion control when a reference
   clip is attached, each with a motion prompt in the block structure above. VFX you name
   become steps where a step exists (`upscale`) and gaps where none does (`relight`,
   anything unknown).
7. **Edit and ending.** Cut, a voiceover of every scene's brief when the profile narrates,
   captions timed to that voiceover, then export.
   Publishing steps exist only if you ask and always need a person.

## Talking to it

Studio: open a workspace, choose **Direct it**, or press **Director** on any canvas. CLI
(`--client` takes the workspace key, a folder in `brands/` with a `brand.yaml`):

```bash
python packages/engine/cli.py say --client epalle --session s1 --text "a lookbook of one persona across a city evening, neon noir"
python packages/engine/cli.py say --client epalle --session s1 --text "add a scene at a market at dawn"
python packages/engine/cli.py plan --brief tests/fixtures/engine_brief.json
```

Things it understands (`packages/engine/session.py`): a kind of piece or a look by name;
"add a scene at …"; "N scenes"; "N angles"; "N takes"; "clips 6 seconds long"; "wardrobe from
my red-dress" (rights: *my* = owned, *licensed*, otherwise unclear); "location …",
"jewellery …", "motion clip …"; "vfx relight"; "add role bob from avatar-bob"; "keep at
scene1.pick.keep: 1, 3, 4"; "switch to auto mode"; "run the next stage"; "undo". Anything
else is added to the brief as a note.

Every utterance is saved in `brands/<workspace>/workflows/<id>.session.json`. Replaying the
list rebuilds the same workflow, byte for byte. Picks and results survive a rebuild.

The describe bar (`cli.py describe`, `POST /api/describe`) chooses between this director
route and the author route per sentence and returns one JSON contract: see [DESCRIBE.md](DESCRIBE.md).

## Run modes

| Mode | What happens |
|---|---|
| **Dry run** | Every step writes a manifest saying what it would do. Nothing is submitted. |
| **Approve** | Each stage is an `engine_stage` task in the control plane. It runs only after a person approves its cost estimate. |
| **Auto** | One `engine_run` approval covers the workflow. The runner stops at any pick nobody has made and before any publishing step. |

Budget lives in `brands/_presets/engine.yaml` (`budget_usd`, default 0). A human raises it.
Estimates come from the same file's seconds-per-step table; every figure says whether it
was measured or assumed, and each manifest records the actual seconds.

Results: `brands/<workspace>/runs/<workflow>/<node>/<run>/manifest.json` plus the files, and
`data.results[]` on the node. A node is `completed` only when ComfyUI's history shows
outputs and they were fetched. Queued is not success.

## What runs a step

`workflows/<pack>/<name>.ports.json` says which ComfyUI node receives each studio port,
the prompt, the negative, the seed and the count, and which node saves the output. See
[PORT-MAPS.md](PORT-MAPS.md). Before a live submission the runner uploads every bound file to
ComfyUI's input folder (`ComfyClient.upload`, `/upload/image`) and converts where a map says so.

Cut, voiceover, captions and export run on this machine (`packages/engine/edit.py`: ffmpeg,
`voice/tts.py`, `voice/mux.py`). A voiceover from ElevenLabs or OpenAI spends, so its stage
goes through the same approval as a GPU stage.

## References

Collections live in `brands/<workspace>/references/<name>/` with a `collection.json`
(`use`, `rights`, `consent`). `use: data` needs owned or licensed rights; unclear rights
inspire prompts only; a real face as data needs consent. [POSSIBILITIES.md](POSSIBILITIES.md)
lists what each kind of reference can drive; `brands/_kit/README.md` gives the minimum
`collection.json`, and `python packages/strategy/workspace.py check <key>` validates every
collection in a workspace.

## Voice

The microphone button talks to the **Director** agent on ElevenLabs (the name is
`AGENT_NAME` in `packages/voice/elevenlabs_agent.py`; `brands/_presets/voice-agent.json`
records the same name and the saved agent id, and the next `sync` pushes the display name
to the dashboard). The
agent has ten client tools (`packages/voice/elevenlabs_agent.py`): `director_say`,
`add_scene`, `set_angles`, `set_look`, `set_kind`, `attach_reference`, `keep_candidates`,
`set_run_mode`, `run_stage`, `workflow_status`. They run in the browser
(`components/VoiceDirector.js`) and go through `/api/director` and `/api/run`, so a spoken
"run it" meets the same approvals and budget as a click. A test keeps the two tool lists equal.

```bash
python packages/voice/elevenlabs_agent.py sync        # create or update the agent and tools
python packages/voice/elevenlabs_agent.py signed-url  # what /api/voice/session hands the browser
```

The key stays in the vault (`set_secret.py elevenlabs`); the browser only gets a short-lived
signed URL. Ids live in `brands/_presets/voice-agent.json`. If the agent cannot be reached,
the button falls back to the browser's own speech recognition.
