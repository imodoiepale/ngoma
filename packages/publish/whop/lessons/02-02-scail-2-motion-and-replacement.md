---
chapter: Character Systems
title: SCAIL-2 motion and replacement
lesson_type: text
embed_type: null
embed_id: null
references:
  - https://www.youtube.com/watch?v=sVKV0RNrsKY
  - https://www.youtube.com/watch?v=RQ_gvpdo9ac
---

# SCAIL-2 motion and replacement

SCAIL-2 covers two related jobs that people constantly confuse. Choosing the wrong one wastes
a render.

## Animation versus replacement

**Animation** drives a reference photo with motion from a control video. The output world is
generated: your still character starts moving, and the background is whatever the model
builds around them.

**Replacement** swaps a subject inside existing footage while retaining the original scene.
The output world is the source video's world, with a different person in it.

Ask what you want to keep. Keeping the *performance* and generating a new scene means
animation. Keeping the *scene* and changing the person means replacement.

## Composition matching is the whole game

The single biggest quality lever is how well your control video's composition matches your
reference image. Match:

- **Framing and crop** — a full-body control video against a head-and-shoulders reference
  makes the model invent a body, and it will invent a different one each time.
- **Camera distance and lens character** — wide-angle motion against a compressed portrait
  reference produces a warping face.
- **Subject scale and position in frame.**
- **Orientation** — do not fix a sideways source with a rotation node downstream; fix it
  before it enters the graph.

When a replacement result looks uncanny, composition mismatch is the first thing to check, not
the prompt.

## Masks

Replacement depends on segmentation quality. Practical notes:

- Prompt-driven segmentation lets you select a full body, or a specific person out of a crowd,
  by describing them. Be specific about position and clothing when several people are present.
- Track the subject across frames and inspect the mask at the *worst* frame, not the first
  one. Occlusion, motion blur and frame edges are where masks fail.
- Feather and dilate deliberately. A tight mask leaves halo seams; an over-dilated one drags
  background into the subject.
- Hands and hair are where masks lose. Check them explicitly.

## Budgeting and frame limits

- Resolution is controlled by a megapixel setting rather than raw dimensions. Roughly, a low
  setting lands near 480p and a mid setting near 720p.
- Cost scales hard with resolution. On a 24 GB-class consumer card, expect a 720p render to
  take several times as long as the same clip at 480p — reported figures on an RTX 3090 sit
  around 800 seconds for 720p against roughly 300 seconds for 480p anime-style content. Treat
  those as order-of-magnitude, not a promise for your hardware.
- The model works in a bounded clip length — around 81 frames per pass. Longer sequences need
  a context-window or extension approach, covered in the MiniMax H3 lesson.

## Test discipline

Always run a 5–10 second test at low resolution before committing to a long render. Confirm in
this order: is the subject the right person, does the motion track, is the mask clean at the
worst frame, does the scene hold. Only then raise resolution.

## Deliverable

One motion test and one replacement test, both 5–10 seconds, both accepted, before any
full-length render.

## Reference viewing

Third-party tutorials, linked to the creators' originals:

- KiubAI — [The best open source motion control model (SCAIL 2)](https://www.youtube.com/watch?v=sVKV0RNrsKY)
- Prompt Mastery — [SCAIL-2 character replacement tutorial](https://www.youtube.com/watch?v=RQ_gvpdo9ac)
