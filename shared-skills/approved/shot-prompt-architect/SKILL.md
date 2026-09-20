---
name: shot-prompt-architect
description: Use when writing or reviewing a prompt for an image-to-video, text-to-video or motion-control step, a CUT list for a scene, a speed-ramp or slow-motion shot, a prompt that binds several reference images or a camera-reference clip, or when a generated clip came back wrong and the note has to become a prompt change ("too floaty", "eyes look dead", "the two riders swapped bikes"). Produces one finished, production-ready prompt per scene in a fixed block order, with no person's name or likeness, no hosted-model assumptions, and every beat answering shot size, camera move, action and transition.
---

# Shot prompt architect

Writes the prompt a video step actually receives. One scene in, one finished prompt out,
in the block order below, nothing else around it. The method fuses two published systems,
restated in our words: AiKAMI's five-block Seedance structure and speed-ramp grammar
(`docs/creators/aikami/NOTES.md`, Days 4 to 6) and PJ Accetturo's Nexus skill
(`docs/creators/pjaccetturo/NEXUS-SKILL.md`). Where they differ, this file wins.

Reference files: `reference/structure.md` (the blocks, with the rules for each) and
`reference/vocabulary.md` (shot sizes, angles, lenses, camera bodies and stocks, lighting,
camera moves, cut types, and what each one does to the viewer).

## Repo rules, before anything else

1. **No person's name or likeness, ever.** No director, cinematographer, actor, musician or
   film title in any prompt. Say the look, not the name: `packages/engine/presets.py`
   `FORBIDDEN` refuses the common ones and a preset that names a person fails to load. A
   character `@block` may only describe an owned or fictional character
   (`brands/<client>/references/<name>/collection.json` with `rights: owned` or `fictional`);
   a real person without a release is a declared gap, not a prompt.
2. **Write for our routes.** The engine's motion steps are Wan 2.2 image-to-video, MiniMax H3
   and SCAIL 2 motion control on the pod (`brands/_presets/profiles.yaml`, `generator` and
   the `motion-control` node). Hosted models are not adapters; do not write "Seedance" or
   "Kling" features (native audio, `<<<image_n>>>` binding) into a prompt unless the step
   really binds references that way. For our nodes, references are bound by ports; the
   prompt describes them by role ("the woman from the character sheet").
3. **The preset and profile are the style.** `directors.yaml` gives framing, lens, palette,
   pacing, blocking, grade, motion, negatives; `profiles.yaml` gives the locks and negatives
   of the kind of piece. The [Style] and [Hold constant] blocks are composed from those
   first, then the brief adds what is specific. `compose_motion_prompt` in
   `packages/engine/presets.py` produces the deterministic skeleton; this skill is how a
   person (or an LLM step) fills and reviews it.
4. **Plain punctuation.** Hyphens, commas, full stops. No em dashes anywhere in a prompt.
5. **4,000 characters per scene prompt, hard.** Count it; trim and recount if over.

## What to ask for, once

The scene in plain language; who is in it (by reference name); how many cuts (default: one
continuous take per scene unless the profile's pacing says otherwise, e.g.
`kinetic-music-video` cuts on the beat); the clip length in seconds (from the profile's
`seconds`); the aspect ratio; what each reference is for. If one thing is genuinely
unclear, ask one sharp question, never more than two.

## Block order

```
[References]        one block per active reference, scope-tagged; camera-reference clips say what to take and what to discard
[Summary]           two or three lines: who, where, what happens, the feeling; pairings that must never swap
[Style]             capture (camera body or stock, lens or field of view), lighting, grade, texture, "photographic realism throughout" or the animation style; locked across every cut
[Physics]           mass, weight transfer, cloth and hair lag, what the environment does in response
[Plot]              timecoded beats; every beat answers shot size and angle, camera move, action, transition; speed ramps placed by the second
[Hold constant]     aspect, count of people, wardrobe, grade, lens, lighting direction, staging; profile locks verbatim
[Audio]             SFX and diegetic sound only unless the profile says otherwise; perspective follows the camera; no music, no subtitles
[Strictly exclude]  the preset and profile negatives, plus whatever came out wrong last time
```

Full rules per block in `reference/structure.md`. The short version of the ones that
matter most:

- **Count.** Say the number of people, vehicles, animals in every beat ("one rider only,
  throughout"). Models duplicate subjects.
- **Restate staging in every cut**: who is left, who is right, relative scale, distance to a
  landmark in measurable terms (within one metre, hand on the door, back to the wall). Never
  "near", "beside", "nearby".
- **Performance is behaviour, not a label.** Not "she is angry"; what she does about it.
  Objective, obstacle, tactic; the beat changes when the tactic fails or the balance shifts,
  and the change shows in posture, tempo or gaze. Hands get a task; stopping it is the accent.
- **Eye life in every cut**: micro-saccades, blink rate tied to state, live catchlights, eyes
  reach the target a beat before the head.
- **Speed ramp**: "[normal speed] ... just as [the exact trigger], the speed ramps to [X]%
  slow motion, [the camera move that sells the beat] ... ramps back to normal at [second]".
  Slow motion must read crisp; exclude motion blur inside the slow section.
- **Camera reference only** (a blockout, a driving clip): take the camera's position,
  height, angle, roll, route and timing, beat for beat; discard everything the clip is made
  of, listed. Tiebreaker: the clip decides where the camera is, the plate decides what it
  sees; where they disagree the plate wins.
- **Lighting is a lock, not decoration.** If backlit: subject between camera and the brighter
  background, camera on the shadow side, no frontal fill.

## Reviewing a clip that came back wrong

Translate the note into a block change and regenerate; do not pile adjectives on.

| Note | Change |
| --- | --- |
| too short, lazy | lengthen each beat; more action per cut, 400 to 800 characters each |
| fake, robotic, over-acted | rewrite performance as objective, tactic, visible beat change |
| eyes look dead | add eye life to every cut |
| too floaty, weightless | add the [Physics] block back: gravity, weight transfer, follow-through |
| subjects duplicated or swapped | count in every beat; restate pairings in [Summary] and [Hold constant] |
| background generic or too busy | one specific, precise world detail behind the human moment |
| slow motion smeared | "crisp high-frame-rate slow motion", exclude motion blur in the slow section |
| camera looks keyframed | "flown, not animated": micro-corrections, breathing distance, uneven roll rate |
| fewer cuts than asked | recount the request, redeliver the full number |
| style drifted between cuts | move the drifting words into [Style] and [Hold constant]; lock lens and grade |
| likeness crept in | remove the name or feature; check `FORBIDDEN`; use the character sheet |

## Where it plugs in

- `packages/engine/presets.py:compose_motion_prompt` builds the deterministic skeleton
  (one timecoded beat for the scene's seconds, hold-constant from profile locks, SFX line,
  excludes from negatives) for `image-to-video` and `motion-control` nodes.
- A `brief` node's text is what the person wrote; the composed prompt is what the node gets.
  Both are in the run manifest under `brands/<client>/runs/`.
- `style-block` (sibling skill) produces the [Style] block for a stylised piece and the
  `directors.yaml` preset behind it.
