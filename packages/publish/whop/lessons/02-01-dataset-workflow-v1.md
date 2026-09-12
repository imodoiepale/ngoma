---
chapter: Character Systems
title: Dataset Workflow V1
lesson_type: text
embed_type: null
embed_id: null
references:
  - https://www.youtube.com/watch?v=rbBNEVyQyyk
  - https://www.youtube.com/watch?v=x9ETAqkAysg
  - https://www.youtube.com/watch?v=_mN1AAzcBT4
---

# Dataset Workflow V1

A character dataset is the asset everything else is built on. Get it right and every later
shot is cheap; get it wrong and you will fight identity drift in every render.

## What the workflow does

Dataset V1 takes up to **14 native reference images** — passed through without resizing or
batching them together — and produces **25 independently prompted shots**: 12 portrait and 13
full- or half-body. Each prompt card is cached independently, and enabled shots execute
sequentially with one admitted API operation at a time.

Three design choices matter more than they look:

- **`live=false` by default.** Loading or inspecting the graph sends no paid request. You can
  open it, read it, and wire it without spending anything.
- **Independent caching per card.** Re-running to fix one bad shot does not re-bill the other
  24.
- **Row-level and per-shot bypass.** You enable only the shots you intend to buy.

## Cost model — read this twice

Every enabled prompt is a **separate paid provider operation**. There is no batch discount and
no partial refund. Two consequences:

1. Enable a small subset first. Three or four shots tell you whether identity is holding.
   Only then enable the rest.
2. A lost submit response **may already have been billed**. The pack deliberately blocks the
   same semantic retry after an indeterminate submit, so you do not silently pay twice. If
   this happens, check the provider dashboard before creating another result.

Set `live=true` only at the moment you deliberately authorise the spend.

## Credentials

No API key ships in the workflow, and the key is kept out of the node input schema so it does
not travel inside exported graphs. On a local install you enter it through the visible key
control. For LAN, remote, container or RunPod installs, the supported path is the
environment-variable name the pack documents.

Provider keys and runtime caches live outside the repository, under the current user's data
directory. That matters when you share a workflow, a log, a screenshot or a support bundle —
check what you are about to send.

## Choosing your references

The references decide the ceiling. Aim for:

- Consistent identity, varied conditions. Same person, different light, angle and distance.
- Neutral, unambiguous face data in at least a few frames — no heavy shadow across features,
  no extreme lens distortion, no sunglasses.
- At least one clean full-body frame if you want reliable body shots; portrait-only references
  produce guessed proportions.
- No other faces in frame. Crop them out.

Three good references beat fourteen mediocre ones. Adding weak images pulls the identity
average toward mush.

## Shot acceptance

Judge every output against the references, not against how nice it looks. Reject on:

- **Face geometry** — inter-eye distance, nose bridge, jaw and chin, ear placement.
- **Skin detail** — plastic smoothing, lost texture, wrong pore scale.
- **Apparent age** — drift of five years either way is common and disqualifying.
- **Hair** — hairline shape, density, edge quality.
- **Wardrobe isolation** — clothing bleeding identity cues into the face, or vice versa.
- **Full-body proportion** — limb length, shoulder width, hand structure.
- **Identity drift across the set** — the set must read as one person, so compare shots to
  each other, not only to the references.

Write down *why* you rejected each one. That record is what teaches you which references to
supply next time.

## Deliverable

A curated contact sheet of the accepted set, plus the rejected shots with a stated reason
each.

## Reference viewing

Third-party tutorials, linked to the creators' originals:

- Json — [The only dataset video you will ever need for AI influencers](https://www.youtube.com/watch?v=rbBNEVyQyyk)
- Json — [This character board makes your AI influencer consistent](https://www.youtube.com/watch?v=x9ETAqkAysg)
- Json — [How to create an AI influencer from scratch without training a LoRA](https://www.youtube.com/watch?v=_mN1AAzcBT4)
