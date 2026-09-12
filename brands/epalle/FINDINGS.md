# EPALLE — what the analysis actually found

Measured on 2026-09-12 by `packages/vision/analyze.py`. These are numbers, not opinions,
and three of them contradict something the project currently assumes.

## 1. The shipped cover art breaks EPALLE's own visual language

| File | crushed to near-black |
|---|---|
| `COVER ART.png` | 30% |
| `MAIN COVER ART.png` | 47% |
| `slide 1.png` | 46% |

Lesson 04-01 says charcoal must be *"deep neutral, never pure black, so shadow keeps
detail"* and names crushing as one of the two standing drifts to check on every output. The
art does exactly the thing the brand forbids.

This is why `brand.yaml` carries both `palette.measured` (the corrected targets) and
`palette.as_shipped` (what is actually in the files). The rule wins; the drift stays
visible rather than being normalised away.

**Decision needed:** regrade the covers to hold shadow detail, or amend the visual language
to permit crushed blacks. Right now the document and the artwork disagree.

## 2. The Flowers Falling footage is 29.97fps; the treatment defaults to 24

`IMG_8189/8190/8191.MOV` are 3840x2160, **29.97fps**, single continuous takes (no cuts
detected across 60-142s).

Lesson 04-03 is explicit: lock the audio master and the frame rate before generating,
because changing either invalidates every timing decision downstream. Generated shots at
24fps intercut with 29.97fps live footage will need a conform, and conforming after
generation is the expensive direction.

**Decision needed:** pick one rate now. If the live footage is hero material, generate at
29.97 (`--fps 30`). If it is B-roll, conform it to 24 once, before anything else.

## 3. The live footage is not yet in the brand palette

In-palette share against charcoal/ivory/dust gold: **8%, 24%, 34%**. Dominant measured
tones are sage-grey (`#A6A79D`, `#D5D4C8`, `#D6D6CF`) — daylight, ungraded.

That is normal for camera-original material and not a fault. It does mean the grade is
load-bearing: lesson 04-01's "grade to the palette at the end, as one pass over
everything" is the step that makes this footage and generated shots belong to each other.
Do not judge cohesion before that pass.

## 4. Not enough samples to derive a grammar yet

`packages/strategy/study.py` refused at 4 samples against a floor of 12. That refusal is
the correct behaviour — a pattern from four clips is noise. To study a reference body of
work properly, harvest at least 12 and ideally 40+ items first.

## Catalogue on disk

| Song | What exists |
|---|---|
| Flowers Falling | cover art (3 files) + 9 .MOV clips, ~3.6 GB |
| Ancestral Pulse | master .wav (32.5 MB) + stems .zip |
| Basalt Depth | master .wav |
| ASALI | treatment only — no master located |

A 177.3s treatment for Ancestral Pulse is generated at
`calendar/treatment-ancestral-pulse.md` (48 shots, full coverage, +0.1s drift).
Note that ASALI is the *pilot named in the course*, but Ancestral Pulse is the song that
actually has a master on disk — so it is the one that can be built first.
