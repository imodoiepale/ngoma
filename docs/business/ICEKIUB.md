# Buying Icekiub: what you get, what we already have, how we absorb it

**Bought, 2026-09-14.** The Skool classroom (22 lessons) is imported. Every workflow, node
pack, model link and lesson note is in [ICEKIUB-SKOOL.md](ICEKIUB-SKOOL.md).

## Where it is sold

- **Whop:** [ComfyUI/AI Tech - Icekiub AI](https://whop.com/icekiub/). The public page on
  2026-09-13 showed about 6,995 members and a 5.0 rating from 44 reviews.
- **Price:** not in the public page's HTML. Whop shows it at checkout.
- **Source of the link:** the Whop URL is embedded in the pack files already in
  `Documents\COMFY`, which is how we know these packs came from there.
- **YouTube:** the old channel was removed by YouTube, and the live channel is
  [@icy-x4s](https://www.youtube.com/@icy-x4s) (KiubAI, 9 videos). None of those video
  descriptions link to a shop.

**You make the purchase.** I do not buy or sign up on your behalf.

## What the public Whop page shows being posted

- The AIO influencer dataset workflow (Flux Klein)
- Instagram carousel photosets with Klein 9B KV, also usable for product photography
- ICY SCAIL 2.0 motion control, with a free v2 zip attached to one post
- ICY Animate, in full-body and head-only versions

## What we already hold

There are 16 Icekiub workflows in `workflows/icekiub/`, registered in `workflows/manifest.json`:
- Carousel Pose changer (v1.7)
- I2V infinite extender, and I2V extender with prompt change
- ICY SCAIL 2.0 (two copies)
- INFLUENCER Dataset AIO (v1.1, Klein Revamped, and Klein Revamped without base)
- IcyMotion Free v3
- KleinDataset freelo
- LTX2 T2V and LTX 2.3 "KlingKiller" pose/depth
- QWEN ICY Faceswap, QWEN Image Unleashed, and the QWEN NSFW Klein faceswap

Plus one custom node pack, **ICYLM** (`workflows/icekiub/nodes/ICYLM/`): ComfyUI nodes that
call a local LM Studio server (`http://127.0.0.1:1234`) to caption or prompt from an image,
video frames or audio. Needs `requests`, `Pillow`, `numpy` and `opencv-python`.

Note that the NSFW faceswap workflow is **never** used on real people (see
`brands/_business/ideas.yaml` X01 hard gates).

## Why buy anyway

- **Newer versions.** Klein KV carousels, ICY Animate and future drops.
- **Updates tracked with model releases.** H3 reference mode and Krea 2 are both covered
  on the channel.
- **Directly unlocks** V02 carousel-from-one-photo, P06 character boards, P07 virtual try-on
  and U01 UGC packs.

## After you subscribe

1. Download the packs into `C:\Users\inkno\Documents\COMFY\<pack name>\`.
2. Tell me, and I will register each workflow with its hash and source (never guessing
   packs) and rebuild the graph:

   ```bash
   python packages/library/graph_build.py
   ```

3. For each new workflow, list its dependencies and add any missing models to the pod
   download plan:

   ```bash
   uv run packages/comfy-client/client.py deps <workflow>
   ```

## Rules that stay in force

- **No redistribution.** The packs carry no licence, so they are for our internal
  production only. They are never bundled into E03 workflow packs, a course, or anything we
  sell (`docs/LICENSING.md`).
- **Consent for faces.** Faceswap and dataset workflows run only on owned, consented or
  fictional likenesses.
