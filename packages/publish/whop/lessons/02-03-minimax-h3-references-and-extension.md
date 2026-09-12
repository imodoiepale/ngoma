---
chapter: Character Systems
title: MiniMax H3 references and extension
lesson_type: text
embed_type: null
embed_id: null
references:
  - https://www.youtube.com/watch?v=IksoPQm7Sog
  - https://www.youtube.com/watch?v=5wOU7yhR0dQ
  - https://www.youtube.com/watch?v=OS31rr2QfkU
  - https://www.youtube.com/watch?v=2IxKL3-Igh4
---

# MiniMax H3 references and extension

H3 is the workhorse for anything longer than a single clip, and for anything where a character
has to stay recognisable across shots without training a LoRA.

## Reference conditioning

The headline capability is reference mode: you condition generation on images of your
character rather than on a trained model. Practical implications:

- No training run, no LoRA files, no per-character wait. Your Dataset V1 output feeds straight
  in.
- Identity strength is a function of reference quality and count, exactly as in the dataset
  lesson. Weak references cannot be prompted away.
- It is cheaper to iterate but harder to lock. A LoRA gives you a fixed identity; references
  give you a negotiable one. For a long project, keep the reference set frozen once accepted,
  and version it, so shot 40 uses the same inputs as shot 1.

## Face and body replacement with masks

H3 also handles face and body swaps in existing footage. The pattern is the same as SCAIL-2
replacement: segment the subject, track across frames, crop, process, composite back into the
original.

Where H3 differs usefully is that latent video and audio travel together, so a performance
clip can keep its sync through the swap. Check lip sync explicitly after compositing — it is
the first thing an audience notices and the last thing you look at.

For crowd shots, describe the target subject by position and appearance rather than hoping the
segmenter picks the obvious one. Verify on a frame where two people overlap.

## Getting past the clip-length limit

A single pass is bounded. Four techniques extend beyond it, and they compose:

**Chaining.** Generate a clip, then start the next from the last frame. Simple, but drift
accumulates and cuts can read as seams.

**Motion context.** Feed the model context from the preceding clip so the continuation
inherits movement rather than restarting it. This is the difference between a continuation and
a jump cut.

**Overlapping blends.** Generate with deliberate frame overlap between segments, then blend
across the overlap. Costs a few frames of render per join and buys a much smoother transition.

**Multi-keyframe.** Specify several keyframes across the sequence and let the model interpolate
between them. Best when you know the beats you need to hit — which, if you did the shot list,
you do.

Two housekeeping rules that cause most long-video failures:

- **Remove duplicate frames at joins.** Overlap means repeated frames; leave them in and you
  get a visible stutter at every transition.
- **Keep audio and video sync explicit.** Every frame you add or remove at a join shifts audio
  against picture. Track the frame count, do not eyeball it.

## Character references across a long piece

For a long video with a recurring character, combine reference conditioning with motion
context: references hold *who*, motion context holds *continuity*. Neither alone gets you
there. Re-verify identity every few segments rather than at the end, because drift compounds
and a late catch means re-rendering everything after the drift started.

## Deliverable

One continued sequence of at least three chained segments where the joins are not visible and
audio stays in sync, and one replacement clip with verified lip sync.

## Reference viewing

Third-party tutorials, linked to the creators' originals:

- KiubAI — [MiniMax H3 reference mode](https://www.youtube.com/watch?v=IksoPQm7Sog)
- KiubAI — [MiniMax H3 reference based image generation](https://www.youtube.com/watch?v=5wOU7yhR0dQ)
- AI Ninja — [MiniMax H3: multi-keyframes, long videos and video extension](https://www.youtube.com/watch?v=OS31rr2QfkU)
- AI Ninja — [MiniMax H3 face swap and body swap complete workflow](https://www.youtube.com/watch?v=2IxKL3-Igh4)
