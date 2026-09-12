# EPALLE AI Creative Studio — Course Blueprint

Status: production-ready curriculum outline; platform publication has not been performed because no Whop or Skool account/API credential was supplied.

## Promise

Build a repeatable, self-hosted studio that turns three or more character references, an approved product brief, or an original song into consistent images, short-form UGC, character-replacement clips, music-video sequences, and localized campaign variants.

## Module 1 — Safety, rights and the studio brief

- Define the performer, product, audience, language, claim sheet and usage rights.
- Separate inspiration analysis from copying. Extract structure, pacing and camera grammar; write original scripts and scenes.
- Deliverable: one approved creative brief, evidence sheet and rights checklist.

## Module 2 — Persistent RunPod studio

- Network volume layout, ComfyUI environment, SSH access, model manifest and hash verification.
- Pod work for development; scale-to-zero serverless work for repeatable approved API graphs.
- Deliverable: smoke-tested API request plus a restart/recovery exercise.

## Module 3 — Character dataset from references

- MATRIX Dataset V1: 14 native IMAGE references, 12 portrait shots, 13 body/half-body shots, independent prompt caching and live=false dry inspection.
- Shot acceptance: face geometry, skin detail, age, hair, wardrobe isolation, full-body proportions and identity drift.
- Deliverable: a curated dataset contact sheet with accepted/rejected reasons.

## Module 4 — Motion transfer and replacement

- SCAIL-2 animation versus replacement, composition matching, SAM 3.1 masks, 480p/720p budgeting and 81-frame tests.
- MiniMax H3 reference conditioning, face/body masks, motion context, keyframes and extension.
- Deliverable: one 5–10 second motion test and one replacement test before any long render.

## Module 5 — UGC formats and performance scripts

The DGI Kaos reference identifies ten reusable forms: creator review, ASMR unboxing, restocking ASMR, before/after, torture test, pet/security-cam discovery, street-prank reveal, cinematic macro, fantasy commercial and absurd spectacle. Students map each form to proof, visual action and CTA rather than treating a style label as a prompt.

- Build claim-safe hooks, product interaction beats, proof shots, objections and CTAs.
- Localize after timing: English master, standard Kiswahili, Sheng blend and French.
- Deliverable: three 20–35 second ads with word budgets, gesture notes and subtitle-safe lines.

## Module 6 — Visual direction for music

- Use Fanuel Leul as a study reference for future-facing African visual identity, travel/location texture, designed tableaux and creative-partner presentation. The studio recreates the directing principles with original scenes, not his protected shots or scripts.
- EPALLE palette: charcoal, ivory and dust gold; African visual poetry; fashion-film restraint; flowers, memory, burning, blooming and rebirth.
- ASALI pilot: desire → labor → doubt → prayer → gratitude → sweetness/protection.
- Deliverable: treatment, beat map, shot list, reference board and 30-second animatic.

## Module 7 — Long-form assembly and sound

- Lock the song master and frame rate before generation. Plan hero shots, connective motion, performance inserts, cutaways and transitions.
- Extend clips with overlap, remove duplicate frames and preserve audio sync.
- Deliverable: one 60–90 second original music-video sequence.

## Module 8 — Publishing and operations

- Archive every source once, index transcripts locally, version prompts, track models by revision/hash, and monitor selected channels daily.
- Package lessons, captions, downloads and assignments; publish a draft first.
- Deliverable: course export manifest and a platform-ready course tree.

## Platform decision

Whop is the clean API-first choice. Its official Courses API can create a hidden course inside an existing experience and accepts chapters and lessons; it requires an experience ID and a credential with `courses:update`. Skool's own help material documents course creation through its Classroom UI. Third-party Skool automation APIs exist, but they add account and maintenance risk and should not be treated as an official Skool publishing contract.

## Acceptance rules

- A workflow does not pass because it loads. Its node classes, model files, dimensions, frame rate, audio, outputs and restart behavior must be checked.
- No paid WaveSpeed graph runs during inspection. MATRIX begins with live=false.
- No performance or product claim is published without the claim sheet.
- No real person's voice or likeness is cloned without permission.
- All localized scripts are retimed and reviewed by a speaker from the target market.
