---
chapter: Operations
title: Publishing QA
lesson_type: text
embed_type: null
embed_id: null
---

# Publishing QA

The last gate. Everything upstream can be right and a bad publish still costs you the
account, the client or the credibility. This is a checklist lesson, and it is meant to be run
literally.

## Technical

- **Master exists and is archived.** One master at native resolution and frame rate, stored
  somewhere independent of the machine that made it. Platform variants derive from it.
- **Audio sync verified at the end of the video, not the start.** Drift accumulates; the last
  ten seconds is where it shows.
- **Loudness appropriate to platform.** Over-loud audio gets normalised down and sounds
  worse than a correctly levelled mix.
- **Checked on a phone, muted and unmuted.** That is the real viewing condition.
- **Every platform crop checked shot by shot** for subjects and text lost at frame edge.
- **Captions burned or attached** as the platform requires, spell-checked in the target
  language, not split across a price, number or CTA.
- **No frame with a visible artefact you have stopped noticing.** Fresh eyes, or a day away.

## Identity and craft

- Character reads as the same person in every shot, checked as a contact sheet.
- Hands and product interaction hold up at full speed and paused.
- Grade is one pass, consistent across the piece; skin tone consistent across every face shot.
- Joins invisible; no duplicate-frame stutter at segment boundaries.

## Claims and rights

- Every factual line traces to a Confirmed row on the claim sheet.
- Price, currency, market and offer terms current as of the publish date.
- No comparative claim naming a competitor.
- No implied endorsement you cannot produce in writing.
- Performer consent on file, covering likeness and voice, covering synthetic reproduction.
- Music licensed for the platform and territory.
- Fonts licensed for commercial use.
- Every third-party asset accounted for on the rights checklist.

## Disclosure

- AI generation disclosed where the platform requires it.
- Synthetic voice or performer labelled.
- Paid partnership declared.
- Dramatisation or simulated result labelled on screen, in the ad's own language.

## Localisation

- Each variant reviewed by a native speaker of that market — recorded, with a name.
- Retimed rather than re-cut; CTA lands complete in every variant.
- Brand name, price and CTA pronounced correctly in every audio track.

## Provenance and reproducibility

Before publishing, be able to reconstruct the piece:

- Workflow files versioned, with the exact graph used per shot.
- Model versions and hashes recorded.
- Prompts and seeds stored per shot.
- Reference set archived and frozen.
- Output hashes recorded.

The test: if a client asks for a variant in six months, can you produce it without guessing?
If not, you have a video but not an asset.

## Publish sequencing

**Draft or hidden first, always.** Publish in a non-public state, then review it *as
published* — platform compression, aspect handling, caption rendering and thumbnail cropping
all change things. What you approved in an editor is not what the audience sees.

Then:

1. Review the hidden or draft version on a real device.
2. Fix and re-upload if needed.
3. Make public deliberately, as a separate decision by a named person.

Never let "publish" be the same action as "finish rendering". They are different decisions,
and the second one is not reversible in any way that matters — content circulates after
deletion.

## Post-publish

- Record what went out, when, where, and which version.
- Keep the master and the provenance bundle together.
- Note early performance against the format you chose, so the next teardown has your own data
  in it rather than only competitors'.

## Honest reporting

Applies internally as much as externally: report what happened, not what was supposed to
happen. A partial result described as complete is worse than a failure, because it removes the
chance to fix it. If three of five variants shipped, say three of five, and say which two did
not and why.

## Deliverable

A completed checklist for one real publish, a provenance bundle sufficient to reproduce it,
and a written record of the publish decision with the approver named.
