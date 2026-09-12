---
chapter: Music Direction
title: Long-form assembly and sound
lesson_type: text
embed_type: null
embed_id: null
references:
  - https://www.youtube.com/watch?v=OS31rr2QfkU
---

# Long-form assembly and sound

Generation produces clips. Assembly produces a video. This lesson is about the second one,
which is where most AI music videos fall apart.

## Lock before you generate

Two values get fixed and never move:

- **The audio master.** Final mix, final length. Not a rough, not a "close enough" bounce.
- **The frame rate.** One number for the whole project.

Every timing decision references these. Change the master after generation and every beat
alignment you made is wrong; change the frame rate and every join, overlap and duplicate-frame
count is wrong.

## Shot taxonomy for assembly

Sort every shot into one of four roles. This determines how you cut it.

**Hero shots.** The images the video exists for. Longest on screen, stillest, best-graded. Two
or three per minute, no more — hero shots stop being hero shots when everything is one.

**Connective motion.** Carries the eye between heroes. Short, directional, often a camera move
with no new information. These are the shots you generate cheapest and cut hardest.

**Performance inserts.** Face, mouth, hands, in sync with the audio. The one category where
sync accuracy is non-negotiable.

**Cutaways.** Texture, object, landscape, detail. Your recovery tool — a cutaway covers a bad
join, a drift in identity, or a section where nothing was working.

Generate more cutaways than you plan to use. They are cheap and they will save you.

## Joining generated segments

Segmented generation is the norm for anything beyond a single pass. The mechanics:

1. Generate with deliberate **frame overlap** between adjacent segments.
2. Feed **motion context** from the end of one segment into the start of the next, so movement
   continues rather than restarting.
3. **Blend across the overlap** rather than hard-cutting at the boundary.
4. **Remove duplicated frames.** Overlap means repeated content; leave it and every join
   stutters visibly.
5. **Recount audio sync.** Every frame added or removed at a join shifts picture against
   sound. Track the count numerically — do not judge it by eye, because small drift is
   invisible per join and obvious after five of them.

Steps 4 and 5 are the ones people skip, and they are the ones that produce that particular
juddering, slightly-out-of-sync quality that marks a video as machine-assembled.

## Where to place the seams

Hide joins where the audience is not looking:

- On a music transition, where a section change draws attention to the audio.
- On a hard cut you were going to make anyway.
- Behind a cutaway.
- On camera motion, where blur masks the boundary.

Never place a join mid-performance-insert. The mouth will not survive it.

## Identity across the piece

Drift compounds. Check identity every few segments against the frozen reference set, not at
the end — a drift caught late means re-rendering everything downstream of where it started.
Build a habit of assembling a rough cut early and repeatedly, so you are always looking at the
whole rather than at the newest clip.

## Grade as one pass

Grade the assembled timeline, not the individual clips. Per-clip grading guarantees mismatch.
One pass over everything, targeting the three palette values, then a second look at skin tone
specifically across every shot with a face in it.

## Sound beyond the master

The music master is the spine, but a music video is not only music:

- Add diegetic texture sparingly under the mix — cloth, footfall, wind, dust — where a shot
  needs physical presence.
- Keep every added element well under the music. If a viewer notices your sound design in a
  music video, it is too loud.
- Check the final mix on phone speakers. That is where it will be heard.

## Export

- Master at the project's native resolution and frame rate, once.
- Derive platform variants from the master — vertical crops, square, trimmed lengths — rather
  than re-rendering.
- Check the vertical crop for every shot with text or a face near frame edge. Composition that
  works wide often loses the subject when cropped.

## Deliverable

One 60–90 second original sequence, cut to a locked master, with invisible joins, verified
audio sync, a single grade pass, and platform variants derived from one export master.

## Reference viewing

- AI Ninja — [Multi-keyframes, long videos and video extension](https://www.youtube.com/watch?v=OS31rr2QfkU)
