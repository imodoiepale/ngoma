# The blocks, with the rules for each

One scene, one prompt, blocks in this order. Headings in square brackets are for the
reader; some models ignore them, none are hurt by them. Sources: AiKAMI Days 4 to 6 and PJ
Accetturo's Nexus skill, restated (see `docs/creators/`). Repo rules first: no person's
name or likeness, plain punctuation, 4,000 characters per scene, our routes not hosted ones.

## [References]

One block per active reference. Fuse identity and performance in one block so the
character shows up consistent and alive:

```
@TAG: [age] [role or body type] [current physical state, action-critical anchors].
[The engine in one clause: what drives the physicality].
[One signature tic and its trigger]. However, when [trigger], [the crack in the mask].
Eye life: [saccades and blink behaviour tied to state]. Matches the reference sheet. [Scope tag.]
```

- **Scope tag, always**, at the end: "Character appearance only." / "Costume only." /
  "Prop only." / "Environment only." / "Camera reference only." / "Voice only."
- **Already bound by a port** (the engine links the character sheet into the node): do not
  redescribe appearance. Write "the woman from the character sheet; already referenced.
  Appearance from the sheet." and spend the budget on action and staging.
- **Locations**: "use this plate exactly as it is: this street, these facades, this light,
  this grade, this grain. Do not restyle, relight, or add, move or invent architecture. The
  only things not already in the plate are [subjects] and what their passage disturbs."
  Add an **exemption** for what must move (daylight through the window, leaves, sky).
- **Props and vehicles**: shape, proportion and colour "exact and never change"; if the
  model does audio, how it sounds (a high-pitched turbine whine that rises with throttle).
- **Camera reference only** (a grey blockout MP4, a driving clip for motion control): "take
  from it only the camera's position, height, angle, roll and route, its timing beat for
  beat, and where [subject] sits at each beat. Everything the clip is made of is discarded
  and reaches nothing in the final image:" then list it (flat grey shading, blank sky, toy
  proportions, mannequin occupants, weightless motion).
- **Tiebreaker**, whenever two references overlap: "[clip] decides where the camera is.
  [plate] decides what the camera sees. Wherever they disagree, the plate wins, every time."
- **Pairings**: "the woman rides the green bike; the man rides the chrome bike. These
  pairings must never swap."
- **Face coverings** (masks, helmets) tend to turn a face into stone or a knight. Describe
  the human first; the covering is one line at the end ("a smooth fitted metal face covering
  cast to the face contours"), never a skin-toned colour, never "mask", "helmet", "visor".
- **Real people**: not here. A role without `rights: owned` or `fictional` is a declared gap.

## [Summary]

Two or three lines in plain language: who, where, what happens, the feeling. State speed
throughout (normal, where the slow-motion moment is, ramps), what persists (environment
intact, lighting constant), and how the scene resolves. Restate pairings. This is what
keeps the whole generation consistent; if the plot and the summary disagree, the model
picks one at random.

## [Style]

Locks the look across every cut. Composed from the preset first (`lens`, `palette`,
`grade`, `motion`, `pacing` in `brands/_presets/directors.yaml`), then the brief:

- **Capture**: camera body or film stock and the lens, by the look they give (see
  `vocabulary.md`): "shot on 35mm anamorphic, wide lenses for the chase, long lens with
  shallow depth of field for the close-ups". Or field of view by outcome: 84° close
  intimate face with environment, 47° natural action, 29° medium portrait, 18° tight
  emotional close-up, 107° geography, 8° distant observation. Lock the lens across the
  cuts of a shot; hard cut between lens characters, never drift.
- **Lighting** as a priority constraint: direction, quality (hard, soft, volumetric,
  chiaroscuro), time of day, "no flat frontal key, no beauty fill".
- **Grade and texture**: palette, contrast, grain, halation, "photographic realism
  throughout" or the animation style ("cut-paper animation ... fully matte throughout").
- **Camera character**: "kinetic, weighty, practical" or "locked off, minimal" or "flown, not
  animated: continuous micro-corrections in yaw and pitch, the gap between camera and
  subject breathes, the roll rate loads up and unwinds unevenly; if a move looks keyframed
  it is wrong".
- **Realism tags**: "real footage off a real drone, not a render" for live action; the
  matching exclusions go into [Strictly exclude].

## [Physics]

Every body and object carries gravity, mass, inertia and weight transfer. Motion has cause
and effect: no floating, no frictionless feet, no teleporting, no rubber. Cloth and hair
lag behind the body. Liquids cling, drip, pool. Say what the environment does in response
(dust behaves as heavy particulate and settles a beat after; suspension compresses; tyres
deform at the contact patch; near buildings streak, far ones drift). For stylised worlds,
say what the material is and how it behaves ("everything behaves as paper and card with
real mass; hair and apron swing as hinged flat sections, not cloth simulation").

## [Plot]

Timecoded beats that add up to the scene's seconds (from the profile's `seconds`). Every
beat answers four questions, in this order:

1. **Shot size and angle**: wide, medium, close-up, extreme close-up; low, high, eye-level,
   over-the-shoulder, POV (what each does: `vocabulary.md`).
2. **Camera motion**: static, push in, dolly back, pan, orbit, tracking, crane, whip, or the
   speed ("fast tracking backward just ahead of the car").
3. **The action**: exactly what the subject does, mechanically, with staging restated (who
   is left, who is right, scale, distance to landmark in measurable terms).
4. **The transition** into the next beat: HARD CUT, SMASH CUT, MATCH CUT, INSERT CUT,
   REVERSE CUT, WHIP CUT, or continuous. No fades or dissolves unless asked.

Format for a multi-cut scene:

```
0-3s: CUT - wide establishing, high aerial sweeping down, normal speed - two bikes far below throwing twin rooster tails of red dust, the chrome bike leading, the green bike behind - the camera dives and levels into a low tracking shot alongside them.
3-5s: HARD CUT - tight close-up on the woman from the sheet, camera travelling backward in front of her at her own speed - hair streams straight back, eyes locked forward, jaw sets, she twists the throttle - the whine climbs.
```

- Default to a single continuous take unless the profile's pacing or the brief asks for
  cuts; then define every cut with duration, camera, who is visible in the first frame,
  blocking, action, cut type. Minimum 3 cuts, typically 5, 400 to 800 characters each. A
  short shot is a lazy shot.
- Every internal cut preserves the same active characters, geography, screen direction,
  gaze targets, lighting direction, wardrobe and prop state. Nothing resets or teleports.
- **Performance inside the beat**: objective against an obstacle, behaviour not label;
  reactions begin before the partner's action ends; a beat change shows in posture, tempo
  or gaze; hands have a task; eye life in every cut.
- **Speed ramp** (AiKAMI Day 4):
  "[scene at normal speed] ... at the [N]-second mark, just as [the exact trigger moment],
  the speed ramps to roughly [X]% slow motion, [camera motion that sells the beat] ...
  speed ramps back up to normal at the [M]-second mark [as the action continues]". State
  the ramp on both sides by the second. Slow motion must read as genuine high-frame-rate
  slow motion, crisp, with suspended droplets and grit; exclude motion blur inside it.
- **Count** in every beat: "one rider only", "one helicopter throughout".
- **Rack focus, holds and end frames** are beats too: "final frame holds on her".

## [Hold constant]

Everything the model must keep across the whole generation, in one block: aspect ratio,
count of people and vehicles, each character keeps the exact face, hair and wardrobe from
the sheet, each stays with their own prop or vehicle, consistent grade, grain, lens
character and time of day across all cuts, constant camera character, real physical weight,
stable geometry (no warping of wheels, limbs, frames). The profile's `locks`
(`profiles.yaml`) go in here verbatim, then the brief's own.

## [Audio]

SFX and diegetic sound only unless the profile's `narration` says otherwise. Physical and
specific to what is happening (tyres on gravel, the charge whine and crack, hard breathing
dropping into a low stretched drone through the slow-motion section then snapping back).
Perspective follows the camera (outside the car the engine echoes off buildings; inside,
wind roar dominates and the engine goes boomy). "No music, no score. No dialogue. No
subtitles." Voice lines, where a profile allows speech, are one fixed quoted line per
character, written once and pasted verbatim, never rewritten per scene.

## [Strictly exclude]

The preset's `negatives` and the profile's `negatives` first, then the realism exclusions
that match the style (for live action: animation, illustration, painterly texture, 3D CG
render, video game look, glossy plastic surfaces; for paper animation: photorealistic
skin, 3D CGI look, gradients), then the frame hygiene list (additional people or vehicles,
text, lettering, logos, watermarks, letterboxing, any part of the rig in frame), then
**whatever came out wrong last time**, named exactly.

## Silent self-check before delivering

Every reference used is active and none are stale; the first frame contains everyone it
needs to; gaze and body orientation are both stated wherever a relationship matters; the
lens is locked and has not drifted; lighting cannot go flat; every beat change is visible
in behaviour; counts are stated in every beat; the total time matches the scene's seconds;
no person's name or likeness anywhere; no em dash; under 4,000 characters. Then deliver
the prompt and nothing else.
