---
name: style-block
description: Use when a client or brief wants a specific rendering style carried through every asset and shot ("make it all look like these references", "our animation style", "the papercraft look", "extract the style from this moodboard"), when writing the style sentence for a character sheet or a location plate, when a set of reference images has to be checked for coherence before it becomes a look, or when a look has to become a `brands/_presets/directors.yaml` preset the Director Engine can load. Extracts the rendering DNA only, stress-tests it, refuses incoherent sets, and never names a person, studio or film.
---

# Style block

Slop is the absence of a point of view. This skill locks one at the start: it reads a
cohesive set of reference images, extracts the **rendering DNA** (what stays true no matter
what is depicted), and writes it as a short block that goes under the description of every
character and every location, so the whole set is authored, not generated. It then turns
that block into a `directors.yaml` preset so the engine composes the same look into every
angle and every motion prompt. Method restated from AiKAMI Day 7
(`docs/creators/aikami/NOTES.md`); the papercraft example there is the worked case.

## Repo rules

- **No names.** Not a director, a studio, a film, a game, an illustrator. The style is named
  by the term professionals use for the technique (cut-paper relief illustration, cel-shaded
  painterly animation, risograph print, gouache on board), never "in the style of X".
  `packages/engine/presets.py` `FORBIDDEN` refuses a preset that names a person.
- **Rights first.** Reference images a client owns or has licensed can be studied. A
  living creator's portfolio can be studied for its grammar and never reproduced; say so in
  the block's provenance line. `docs/creators/CREATOR-INTEL.md` records the creators we track.
- **Rendering, not composition.** The block excludes subject, location, time of day,
  weather, camera distance, scale, staging, composition, aspect ratio, foreground framing
  devices and specific named colours. Those belong to the brief and the preset's `framing`,
  `blocking` and `palette`, not to the style block.

## Procedure

1. **Check the set is coherent.** Look at every image for the same answers to: surface
   (matte, gloss, paper, paint, pixels), edge treatment (ink line, cut edge, soft brush,
   vector), tonal method (flat fills, shading, gradients, dither), texture (canvas, paper
   tooth, grain, none), lighting model (one studio light, ambient, none, rim), palette
   discipline (restrained plus accents, saturated primaries, monochrome), motion cues if
   frames are from video (parallax layers, stop-motion stutter, smooth). If the answers
   disagree across the set, **stop and say so**: name which images belong together and ask
   which group is the look. Never guess a unified style for an incoherent set.
2. **Extract the rendering DNA** as rules. Each line must be true of every image and must
   describe how anything would be rendered, not what is in frame.
3. **Stress test**: the block must hold for an extreme close-up of a hand, a macro product
   shot, a tight portrait, an interior and a wide landscape. Any line that would break in one
   of those is a composition rule in disguise; rewrite it as a rendering rule or drop it.
4. **Name the style** by its professional term, and state the medium the image should read
   as ("photographed as a real physical paper set", "a frame of hand-painted animation").
5. **Emit the three outputs** below, as short as possible without losing the style.
6. **Load-test the preset**: `python -c "import sys; sys.path.insert(0,'packages/engine'); import presets; print(presets.preset('<key>'))"`
   must print it; `python -m pytest tests/test_engine.py -q -k presets` must pass.

## Output 1: character-sheet block

Starts with the sheet specification (a specification, not a style, so it is fixed), then
the style:

```
3-panel character sheet on a plain mid-grey studio backdrop: panel 1 front-facing head-and-shoulders close-up, panels 2 and 3 full-body front view and back view, same character, consistent scale.
Style: <style name>. <rendering rules: surface, edges, tonal method, texture, lighting model, palette discipline, medium it reads as>.
```

The user writes a short description of the character before it; nothing else. This is the
asset the engine's `character_sheet` step and the Icekiub four-view sheet workflow produce.

## Output 2: location block

```
Style: <style name>. <the same rendering rules, with the location-specific ones: how depth reads, how far layers fall off, what the light does to a set>.
```

The user writes "A wide shot of <location>" before it.

## Output 3: the preset

A `directors.yaml` entry with the ten keys `presets.py` requires
(`label, inspired_by, framing, lens, palette, pacing, blocking, grade, motion, negatives`),
no names anywhere:

```yaml
  <kebab-key>:
    label: <Style name>
    inspired_by: <the technique, in our words; never a person or title>
    framing: [<two or three framings that suit the medium>]
    lens: <how the medium is "shot": 35mm on a paper set, flat orthographic, anamorphic>
    palette: [<palette discipline, not the reference's specific colours>]
    pacing: <how it moves in time>
    blocking: [<how figures are placed in this medium>]
    grade: <tonal method and texture>
    motion: <what motion looks like in this medium; what it never does>
    negatives: [<the failure modes of this style: gloss, 3D render, gradients, melting edges>]
```

`framing`, `blocking` and `palette` are where the composition and colour choices go; the
style block itself stays free of them.

## Worked example (from Day 7, in our words)

Coherent set: cut-paper illustrations. Rendering DNA: every form hand-cut from matte
uncoated textured cardstock with visible paper tooth and slightly fibrous cut edges;
stacked in shallow physical layers a few millimetres apart; flat solid colour fills only,
tonal change by swapping a sheet never by shading; simplified confident graphic
silhouettes with fine detail in thin, loose, slightly wobbly hand-drawn ink line; one soft
directional studio light so each layer drops a short soft real shadow on the layer beneath,
depth reads as stacked paper never as 3D rendering; fully matte regardless of material
depicted (no gloss, metal, glass or specular); restrained muted palette with one or two
saturated accents; photographed as a real physical paper set. Stress test: holds for a
hand, a product, a portrait, an interior and a landscape (the landscape adds "gentle focus
falloff into the rear layers", a rendering rule). Preset: `papercraft-relief` in
`brands/_presets/directors.yaml`.

For motion, the block gains a physics line (`shot-prompt-architect`): "characters stay flat,
rigid and on-model, moving in true parallax layers and casting real soft shadows onto the
set; they never inflate into 3D geometry, never bend like rubber, never morph; motion smooth
and cinematic, no stop-motion stutter, no melting paper edges".

## When it does not work

Rare styles may not extract cleanly; say which line the images disagree on rather than
smoothing it over. Different image models render the same block very differently; the
block is validated by generating one character sheet and one location on our route
(`krea2-t2i` or the Klein sheet workflow) and comparing against the set, not by reading it.
