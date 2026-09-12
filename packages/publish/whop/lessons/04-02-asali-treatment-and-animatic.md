---
chapter: Music Direction
title: Treatment and animatic — the ASALI pilot
lesson_type: text
embed_type: null
embed_id: null
---

# Treatment and animatic — the ASALI pilot

This lesson turns a song into a plan. The pilot case is ASALI, the lead candidate from the
EPALLE catalogue, but the process is the transferable part.

## The treatment

A treatment is one document that a stranger could shoot from. Sections:

1. **Premise** — one paragraph. What the video is about, not what happens in it.
2. **Emotional arc** — the beats, in order, with the feeling at each.
3. **World** — where this exists, what it is made of, what the rules are.
4. **Character** — who we follow and what changes in them.
5. **Visual language** — inherited from the reference board, restated in one paragraph.
6. **Beat map** — timecoded against the song master.
7. **Shot list** — every shot, with type, action, palette note and generation route.
8. **What this is not** — the explicit refusals. Saves more time than any other section.

## The ASALI arc

ASALI works on a six-stage progression:

**Desire → labour → doubt → prayer → gratitude → sweetness and protection.**

Each stage gets a visual state, not just a mood word. Worked example of the mapping logic:

| Stage | Visual state | Palette weight | Motion |
|---|---|---|---|
| Desire | Reaching, incomplete frames, subject partly out of frame | Ivory dominant, gold absent | Slow push |
| Labour | Hands, repetition, sweat and dust, tight crops | Charcoal dominant | Repetitive, cyclical |
| Doubt | Space between subject and camera opens, symmetry breaks | Charcoal, ivory drained | Static, held too long |
| Prayer | Stillness, downward light, subject centred and small | Ivory returns as light source | Almost none |
| Gratitude | Widening, other figures enter, warmth arrives | Dust gold enters here for the first time | Opening, lifting |
| Sweetness and protection | Enclosure, hands over, bloom | Gold and ivory together, charcoal recedes | Settled, circular |

Note what that table does: it makes the palette itself narrative. Dust gold is *withheld*
until gratitude, so its arrival means something. That is the difference between a colour scheme
and direction.

The flower vocabulary from the visual-language lesson threads through: closed in desire,
crushed in labour, absent in doubt, offered in prayer, opening in gratitude, whole in the
final stage.

## Beat mapping against the song

Lock the audio master and the frame rate **before** you generate anything. Everything after
this is measured against those two numbers, and changing either one invalidates every timing
decision downstream.

Then:

- Mark structural boundaries on the timeline — where sections begin and end.
- Assign each of your six stages a timecode range.
- Inside each range, mark hero moments (the shots the video is *for*) and connective moments
  (the shots that carry you between them).
- Note every point where picture must hit audio exactly. These are your non-negotiables.

Do not distribute shots evenly. Hero moments get length and stillness; connective moments get
cut short. Even distribution is what makes a music video feel like a slideshow.

## The shot list

Every row: shot number, stage, duration, framing, subject action, palette note, and
**generation route** — which pipeline produces it.

- Static or near-static hero image → image generation, then a slow synthetic push.
- Performance or lip-sync → reference-conditioned video with audio.
- Motion inherited from a real performance → motion transfer.
- Existing footage with a different subject → replacement.
- Anything longer than a single pass → segmented generation with motion context and
  overlapping joins.

Deciding the route at shot-list time is what stops you from discovering in week three that a
key shot has no way to be made.

## The animatic

Before committing to full renders, build a 30-second animatic covering the strongest passage.
Stills, rough motion, placeholder grade, cut to the real audio.

The animatic answers three questions cheaply:

1. Does the arc read without explanation?
2. Are the beats landing on the music, or near it?
3. Does the palette progression actually communicate?

An animatic costs hours. Finding out after full renders costs the project. If the animatic does
not work, the treatment is wrong — go back to the treatment, not to the prompts.

## Deliverable

Treatment, beat map, shot list with generation routes, reference board, and a 30-second
animatic cut to the locked audio master.
