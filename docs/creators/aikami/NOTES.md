# AiKAMI, "AI Creator Series" Days 1 to 7: what we take, what we leave

Source files: `source/day-1-arcane-x-spiderverse.pdf` ... `source/day-7-style-block-method.pdf`,
free public guides by @buck_the_aikami (Instagram), downloaded 2026-09-19. Study material
only; see `docs/LICENSING.md`. Hand-written notes; `docs/creators/CREATOR-INTEL.md` is
generated and does not cover these.

The whole series says one thing: the model is never the bottleneck, the input frame, the
prompt written like a cinematographer, and the finishing pass are. That matches how the
Director Engine already works (stills first, angles, then motion), so most of what follows
lands as vocabulary and structure, not as new machinery.

Repo rules that override the guides everywhere:

- **No person's name or likeness in any prompt.** The guides lean on "in the style of
  <director>" and "shot by <cinematographer>". We translate every one of those into the look
  it produces (`brands/_presets/directors.yaml` `inspired_by` and grammar keys), and
  `packages/engine/presets.py:FORBIDDEN` now refuses the names the guides use, so a pasted
  guide prompt fails loudly instead of being sent.
- **Hosted video models are not adapters.** Seedance 2.0/2.5, Kling 3.0, Flux 3, Gemini Omni
  Flash are referenced for their prompt grammar only. The engine's motion route is Wan 2.2 /
  MiniMax H3 / SCAIL on the pod (`brands/_presets/profiles.yaml`).
- **Midjourney, Topaz, KamiCraft, ChatGPT/Claude are not part of the pipeline.** Where a guide
  uses one of them, the note says what does that job here.

## Day 1: stylised animation from two assets

Two assets power every shot: a character sheet and a location plate. A style snippet is
pasted at the end of every prompt, character and location alike, so the set is coherent.
Then an LLM writes the motion prompt from the two assets, and the video model gets 2 to 4
variations per prompt.

Taken:

- The **3-panel character sheet on a grey studio background** (front close-up, full front,
  full back) as the canonical character asset. The engine's `character_sheet` step and the
  Icekiub `icy_ref_character_sheet_for_minimax.json` produce exactly this kind of sheet.
- The look itself as a preset, `painterly-cel` in `directors.yaml`: 3D cel-shaded painterly
  animation, bold hand-painted brushstrokes, confident graphic line accents, visible canvas
  texture, anamorphic framing. Named for the rendering, not for the two films the guide
  names.
- The **CUT block** shape: `CUT - <shot size and angle>, <camera move>, <speed> - <action> -`
  plus a closing `SFX only: ... No dialogue. No music` line. This is the same shape PJ's
  Nexus skill uses, so the two guides agree; `.claude/skills/shot-prompt-architect` fuses them.
- "One helicopter only", "one single helicopter throughout": count constraints restated in
  every cut. Video models duplicate subjects; say the number every time.

Left: Midjourney V7/V8.1 raw mode (we generate stills on the pod), the specific film names.

## Day 2: model per task, and the vocabulary

An honest model list (which hosted model for text-heavy images, edits, artistic images,
branding, posters; which video model for cheap simple motion, complex VFX, best realism,
editing) and three cheat sheets: camera bodies and film stocks, lenses, and directors.

Taken:

- The **camera and lens vocabulary**, reproduced in our words in
  `.claude/skills/shot-prompt-architect/reference/vocabulary.md`: camera body or film stock
  (what look each gives), focal length or field of view, depth of field, anamorphic
  character. This is exactly what the `lens` and `grade` keys of a preset hold.
- The rule that a prompt has **three parts a cinematographer would recognise**: capture
  (body, stock, lens), scene (subject, action, environment), and grade/mood (palette,
  contrast, texture). `compose_prompt` already orders scene, camera, then preset fragments.
- The "old model with a strong input frame beats a new model with a weak one" argument,
  which is the justification for the engine's still-first design.

Left: the director column. Each row is translated into a look:

| Guide says | We say (and where) |
| --- | --- |
| vast minimal sci-fi grandeur | `anamorphic-epic` |
| cold, precise, controlled, institutional palette | `minimal-editorial` grade, or a new preset when a brief needs it |
| symmetrical pastel whimsy | `symmetry-pastel` |
| golden-hour natural-light poetry | `golden-hour-romance` |
| saturated neon, moody, dreamy blur | `neon-noir` |
| long immersive floating takes | `one-take` |
| high-contrast desaturated epic slow motion | `impact-slow-motion` |

The paid-model price list (per second costs) is a 2026-09 snapshot and is not copied into
the repo; `brands/_presets/engine.yaml` carries our own measured costs.

## Day 3: the five dials, shots, angles and lighting

The five dials a cinematographer controls: shot size, camera angle, lens, lighting, and
movement. Pages 2 and 3 are image tables (rendered and read, not extractable as text):

- **Distance shots**: extreme wide (place and time, establishing), wide (subject in setting),
  full (body language), medium (dialogue distance), close-up (emotion, detail), extreme
  close-up (tension, intimacy).
- **Angle shots**: eye-level (neutral, direct), high (small, vulnerable), low (powerful,
  heroic), bird's-eye (overview, scale), worm's-eye (larger than life), dutch (unease),
  over-the-shoulder (POV between two characters), POV (what a character sees).
- **Lighting**: high key (even, low contrast, happy), low key (uneven, high contrast,
  dramatic), chiaroscuro (low key at a high ratio, mysterious or dangerous), hard light
  (directional, sharp shadows, intense), soft light (diffused, romantic), volumetric (god
  rays through dust, fog, haze, rain), bokeh (out-of-focus light, isolation, dreaminess),
  silhouette (subject against a brighter background, concealment).

Taken: the whole table, in `reference/vocabulary.md`, and the reading rule: **you should be
able to point at any part of a prompt and say which dial it turns**. The `cameras` table in
`directors.yaml` already names angles by intent; the vocabulary file gives the "what it
does" column so a brief's mood can be turned into an angle choice.

## Day 4: buttery slow motion is a speed curve

Slow motion is designed, not switched on. The footage runs at full speed, drops hard into
slow motion at the impact beat, then ramps back. Structure:

> [scene at normal speed] ... just as [the exact trigger moment], the speed dramatically
> ramps to [X]% slow motion, [camera motion that sells the beat] ... then ramps back to
> normal [as the action continues].

The example prompt has the block layout Day 5 formalises: reference binding, one-sentence
summary, [Subject], [Environment], [Lighting], [Style], timecoded [Shot list], [Overall
requirements], [Strictly exclude].

Taken:

- The `impact-slow-motion` preset, whose `motion` is this speed-ramp grammar and whose
  negatives include "motion blur during the slow-motion section" (the guide's own exclusion,
  since interpolated slow motion must read crisp).
- `compose_motion_prompt` in `packages/engine/presets.py` emits one timecoded beat for the
  scene's seconds, a hold-constant line from profile locks, an SFX-only line, and excludes
  from negatives. The speed ramp is placed by the preset's `motion` text.
- Frame interpolation as a finishing step: generate at 720p / 24 or 30 fps, interpolate and
  upscale afterwards. The Topaz settings page (30 fps, 1080 wide, Proteus, recover detail 20,
  no grain) is recorded here for reference; our upscale step runs on the pod (Krea 2 / Wan
  upscale workflows) and RIFE-style interpolation is a gap until a workflow is registered.

Left: Topaz itself.

## Day 5: the five blocks of a video prompt

The structure behind every good Seedance prompt, in order:

1. **Asset and prop binding**: tell the model what every upload is, after its tag. Include how
   it sounds when the model does audio. Scope each reference ("use this for her face, hair,
   wardrobe and build"; "environment, location and lighting reference").
2. **Summary**: two or three lines in plain language: who, where, what happens, the feeling.
   Restate pairings that must never swap.
3. **Style**: the look locked across every shot: camera and lens, lighting, theme, grade,
   grain, "photographic realism throughout" or the animation style.
4. **Detailed plot**: timecoded beats. Every beat answers four questions: shot size and angle,
   camera motion, the action, the transition into the next beat.
5. **Overall requirements**: everything held constant (aspect, count of people, wardrobe,
   grade, physical weight), audio rules (SFX only, no music, no subtitles), and a strict
   exclusion list, "most importantly, anything that came out wrong last time".

Taken: this is the spine of `shot-prompt-architect/reference/structure.md`, with PJ's
additions (staging restated per cut, performance as objective and tactic, eye life, physics
lock, sound design block, 4,000-character ceiling).

## Day 6: a grey blockout as camera reference

KamiCraft is the author's browser app: ChatGPT (ASTRA model) builds a low-detail 3D scene
with a keyframed camera from a description and the reference sheets, the app previews and
exports an MP4, and that MP4 goes to the video model as a **camera reference only**. The
point is not the 3D scene; it is anchoring positions and driving the camera cheaply.

Taken, because the prompt pattern is independent of the app:

- **"Camera reference only" bindings**: take from the clip only the camera's position,
  height, angle, roll, route and timing; discard everything the blockout is made of (listed
  explicitly so the model cannot borrow its grey shading, toy proportions or blank sky).
- **The tiebreaker rule**: the blockout decides where the camera is, the plate decides what
  the camera sees; where they disagree, the plate wins. Written into
  `reference/structure.md` as the rule for any two references that overlap.
- **"Flown, not animated"**: a hand-flown camera carries a pilot's errors (micro-corrections,
  breathing distance, uneven roll rate, prop-wash wobble). If a move looks keyframed it is
  wrong. Useful for any FPV or handheld preset's `motion`.
- **A physics block** between style and plot: mass, suspension, tyre deformation, wake,
  parallax. Nexus has the same "physics lock"; the skill keeps one.
- **Audio perspective follows the camera** (outside the car vs inside the cabin).

Left: the app, ChatGPT ASTRA. Our equivalent for camera reference is a driving clip in the
`motion-control` route (SCAIL 2 / Wan Animate take a pose or camera video), which is what
the engine's `motion-control` step consumes; a blockout MP4 from any 3D tool can be that clip.

## Day 7: the style block method

Slop is the absence of a point of view. Extract one rendering style from a coherent set of
reference images and carry that same block through every asset and every shot.

The extractor prompt (paraphrased; the original is in the PDF):

- Extract only the **rendering DNA**, what stays true no matter what is depicted. Exclude
  subject, location, time of day, weather, camera distance, scale, staging, composition,
  aspect ratio, framing devices, specific named colours.
- **Stress test**: the block must hold for an extreme close-up of a hand, a macro product
  shot, a tight portrait, an interior and a wide landscape. Any line that breaks becomes a
  rendering rule, not a composition rule.
- Name the style by the term professionals use for it.
- Output two blocks: a **character-sheet block** (3 panels, grey studio, then the style) and a
  **location block**, both as short as possible.
- **Refuse an incoherent set** rather than guessing a unified style.

The worked example is a cut-paper relief style (papercraft collage): matte uncoated
cardstock, flat fills only, tone changes by swapping a sheet never by shading, stacked layers
a few millimetres apart with one soft directional light dropping short real shadows, fully
matte regardless of material, restrained palette with one or two saturated accents,
photographed as a real paper set.

Taken:

- `.claude/skills/style-block`: the extractor as a skill that also turns a block into a
  `directors.yaml` preset (the ten `GRAMMAR_KEYS`, no names) so `presets.py` accepts it.
- `papercraft-relief` in `directors.yaml`, from the example, in our words.
- The character-sheet framing sentence, used verbatim in the skill because it is a
  specification, not a style: "3-panel character sheet on a plain mid-grey studio backdrop:
  panel 1 front-facing head-and-shoulders close-up, panels 2 and 3 full-body front view and
  back view, same character, consistent scale."

## What this changes in the tool

| Where | Change |
| --- | --- |
| `brands/_presets/directors.yaml` | `papercraft-relief`, `painterly-cel`, `impact-slow-motion` |
| `packages/engine/presets.py` | `FORBIDDEN` extended; `compose_motion_prompt` |
| `.claude/skills/shot-prompt-architect` | fused Day 4/5/6 + Nexus prompt system |
| `.claude/skills/style-block` | Day 7 extractor, preset emitter |
| `docs/engine/DIRECTOR-ENGINE.md` | "Prompt grammar" section |
