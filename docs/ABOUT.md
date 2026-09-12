# What this project is about

## The problem

Making content for a brand is not hard because generating images is hard. Generating images
got easy. It is hard because *consistency* is hard, and consistency is what a brand is.

Point any image model at "make a post for my fintech app" thirty times and you get thirty
different companies. The green drifts. The logo comes back mangled or misspelled. The
headline reads "ONGEA PESSA". One post is a photograph, the next is an illustration, the
third has a lens flare. Each image is individually fine. Together they are noise.

The usual response is to prompt harder — longer prompts, more negatives, a style reference,
a LoRA. That helps and it does not solve it, because you are asking a probabilistic system
to be deterministic about the exact things that must never vary.

## The idea

> **Models make pictures. Code makes brands.**

Split the job at the place where the requirements actually differ.

**The model makes the base visual only.** Composition, light, subject, texture, mood —
the things where variation is the value, and where being slightly surprising is good.

**Code applies everything a viewer reads as identity.** The headline, in the right
typeface, spelled correctly. The logo, composited from the master file, never redrawn. The
palette, checked numerically. The disclosure line. The contrast ratio, measured against
WCAG rather than eyeballed. A SHA-256 so you can prove what you published.

Nothing about that split is clever. It is just putting the deterministic requirements in
the deterministic system, which is where they belonged.

Everything else in the repo follows from it. If code owns the brand, then the brand has to
be *written down as data* — hence `brand.yaml` and the style grammars. If the grammar is
data, a plan can reference it. If a plan references it, a publisher can check it. The whole
pipeline is that one decision propagating.

## The style grammar

The unit the system works in is not a prompt. It is a **grammar**:

> Fix the system — field colour, composition, light, palette, finish, negatives.
> Vary only the subject and the copy.

Adapted from a poster prompt-pack that specified nine posters to letter-for-letter
replication. The insight in it is that a specification tight enough to reproduce one poster
is also a specification loose enough to make a hundred different ones that clearly belong
together. That is exactly what a brand needs.

So Ongea Pesa has 24 grammars and EPALLE has 11. Each one names its background hex, its
composition rule, its lighting, its palette subset, its finish, its cultural direction, and
— the part that does the most work — an explicit list of the defaults it refuses.

## Measure, don't assume

Every palette in this repo was **measured from the real product**, not taken from a
document.

That mattered immediately. A prior spec said Ongea Pesa's primary was emerald `#30E0A8`.
The live site is `#0A0A0A` with `#22C55E`, and the logo is navy and pale cyan. The document
was wrong about the product.

It mattered again for EPALLE, in the opposite direction. The brand's written visual
language says charcoal must "never be pure black, so shadow keeps detail". The shipped
cover art crushes 30–47% of its pixels to pure black. There, the *document* was right and
the artwork had drifted. So `brand.yaml` carries both: the corrected target, and
`as_shipped` recording what is actually in the files — because a drift you normalise away
is a drift you will repeat.

The same principle runs through the analysis layer. `packages/vision` measures references
offline — palette, crushed blacks, subject placement, quiet zones, edge density, cut pacing
— with no API key. A measurement is *checkable* in a way a description is not. "Dust gold
drifted into orange" is an opinion; `#C4702A at 12% of frame, 41 units from target` is a
number you can gate on.

## Learning without copying

You want the system to learn from creators who are good at this. That is legitimate and it
has a line through it.

From the project's own creative direction:

> What you take from a director is the *grammar*: how an artefact is framed to read as
> significant, how repetition accumulates rather than bores, how restraint creates weight.
> What you do not take is their shots, their scripts, their locations or their specific
> images.

`packages/strategy/study.py` implements exactly that, and the line is enforced in code
rather than written as advice:

- Captions are read for **shape only** — length, hook position, hashtag density. No caption
  text is retained.
- No subject, object or location is carried forward.
- It **refuses below 12 samples**, because a pattern from four posts is noise wearing a
  suit.

What comes out is a set of constraints to compose original work inside. Never a template to
refill.

## Honesty as an engineering property

Six rules are enforced throughout. Each exists because breaking it produced a real,
expensive failure here — usually a *wrong answer that looked like a right one*, which is
the costly kind.

1. **Queued is not success.** A reachable endpoint and an `IN_QUEUE` response mean nothing
   happened. Only a completed history with outputs counts.
2. **Unknown is not OK.** An unreachable backend once validated as passing. Validation is
   now three-state — OK / UNVERIFIED / BLOCKED — and `--live` refuses on UNVERIFIED.
3. **Dry-run by default.** Everything that spends or publishes needs an explicit flag, and
   anything outward-facing needs a human yes on top.
4. **Composite the logo, never regenerate it.**
5. **Agents create, deterministic code validates, humans approve.** A generating agent
   cannot clear its own sensitive brief, and the publisher refuses such briefs at the
   boundary rather than trusting the planner.
6. **Take the grammar, never the images.**

The same instinct shows up in smaller places. The TTS bake-off leaves its score columns
blank, because perceived naturalness in a language is not something a script can measure
and a fabricated number is worse than an honest gap. Sheng voiceover is refused outright —
no TTS system supports it, so every provider renders it as mispronounced Swahili, which
reads as a brand that does not know its own audience. The skill curator treats an
*unmeasured* gate as a failed one.

## Learning from results, carefully

Phase 8 closes the loop, and the interesting part is the refusals.

Memory is **bitemporal**. Facts carry a validity window, so "pearl editorial worked for
Kenyan professionals" is true from 1 July to 29 July and then superseded — not overwritten.
You can ask what the system believed on any past date. Nothing is deleted, because what
used to be true and when it stopped is precisely what you need later.

The skill curator can propose a reusable skill from measured results, gated on: 3 repeated
wins, 3 distinct days, 12 items, 2 contexts, 12% lift, 0.90 brand consistency, 0.80 holdout
pass. The gates are tuned to be annoying. The failure mode of an automated learning loop is
not that it learns nothing — it is that it **learns noise confidently and then enforces
it**.

And it proposes only. Promotion is a human action, and eleven protected areas — publishing
authorisation, financial claims, security, secrets, budgets, approval policy — are never
auto-authored regardless of evidence. Automating the thing that decides what may be
published is how an automated system removes its own brakes.

## Two brands, on purpose

**Ongea Pesa** — voice-activated M-Pesa, by NSAIT. Fintech, Kenyan, five languages, real
regulatory exposure. Claim safety is a first-class field: no rate or return claims, no
implied Safaricom endorsement, no real till numbers.

**EPALLE** — a music project. Charcoal, ivory, dust gold. A six-stage narrative arc where
the palette itself is the story: dust gold is *withheld* until gratitude, so its arrival
means something. That is the difference between a colour scheme and direction.

Two brands that share nothing — different industries, different output, different
ethics — was the point. It forces every brand-specific assumption out of the pipeline and
into `brands/<key>/`. A third brand is a directory.

## Where it stands

Phases 0–8 are built. Ingestion, the knowledge graph, generation across four backends,
compositing, vision, strategy, publishing, voice, and memory.

What it cannot do yet is mostly not code. Instagram publishing needs the account converted
to Professional and linked to a Facebook Page. The RunPod serverless endpoint has never
completed a generation. FLUX.2 Klein KV is licence-gated. Those are in `docs/BLOCKERS.md`
with owners, because a list of what is broken, honestly maintained, is worth more than a
list of what works.

## The one-line version

A content studio where the model is allowed to be creative and the code is not allowed to
be wrong.
