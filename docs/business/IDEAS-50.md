# 50 ideas, costed

Generated from `brands/_business/ideas.yaml` by `packages/strategy/business_os.py` (as of 2026-09-13). Do not edit by hand.

> **Planning estimates, not forecasts.** Client counts are scenarios. GPU cost uses A100 80GB at $1.64/h (assumed: RunPod on-demand planning figure, verify live). Image throughput is measured on our pod (444/GPU-hour); video throughput is assumed until measured.

| Scenario | Combined MRR if every idea hit it |
|---|---|
| low | $41,360 |
| base | $169,925 |
| high | $525,900 |

Nobody runs 50 ideas at once. Use the table to pick 3-5 with fast first cash, high margin and low setup, then prove them.

## Volume content for social media managers and agencies

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | **1,000 images a day** | Social media agencies managing 10+ accounts | $1,500 | $255 | $1,500 · $4,500 · $12,000 | $3,614 | 80% | $300 | 0.1 mo | 14 d |
| V02 | **Carousel from one photo** | Boutiques and D2C brands on Instagram | $400 | $120 | $1,200 · $4,000 · $12,000 | $2,742 | 68% | $150 | 0.1 mo | 10 d |
| V03 | **Listing to cinematic reel** | Real-estate agents and developers | $49 | $16 | $980 · $2,940 · $9,800 | $1,959 | 67% | $200 | 0.1 mo | 7 d |
| V04 | **Restaurant content retainer** | Nairobi restaurants, cafes and bakeries | $250 | $111 | $1,250 · $5,000 · $15,000 | $2,739 | 55% | $150 | 0.1 mo | 10 d |
| V05 | **E-commerce model photos** | Fashion brands with 100+ SKUs | $600 | $133 | $1,200 · $4,800 · $15,000 | $3,655 | 76% | $300 | 0.1 mo | 14 d |
| V06 | **WhatsApp Status daily** | Kenyan SMEs selling on WhatsApp | $25 | $8 | $500 · $2,000 · $7,500 | $1,342 | 67% | $100 | 0.1 mo | 7 d |
| V07 | **Faceless shorts channel** | Channel owners and niche publishers | $600 | $151 | $1,200 · $3,600 · $12,000 | $2,642 | 73% | $200 | 0.1 mo | 14 d |
| V08 | **Thumbnail and cover retainer** | YouTubers and podcasters | $300 | $111 | $900 · $3,600 · $12,000 | $2,244 | 62% | $50 | 0.0 mo | 5 d |

**V01 1,000 images a day.** Daily pack of 1,000 on-brand images, delivered by 9am. Pipeline: `klein-t2i → compositor` on **pod**. Evidence: LoRAtech: 20 HD images/min Z-Image workflow; our pod measured 444/h. Risk: Buyers churn if images look generic; needs brand grammar per client. Compliance: Client supplies rights to logos and products.

**V02 Carousel from one photo.** 30 ready carousels a month from each product photo. Pipeline: `carousel-pose-changer → compositor` on **pod**. Evidence: LoRAtech 'Full Instagram carousels from 1 photo' (4.3k views); Icekiub Carousel Pose pack. Risk: Pose workflow needs gated Klein KV model. Compliance: Product rights from client.

**V03 Listing to cinematic reel.** Raw listing photos turned into a 30-second cinematic reel. Pipeline: `wan-i2v → ltx → voiceover` on **pod**. Evidence: ArtificialQuotient 'Raw real estate photos into cinematic videos' (30k views). Risk: Must not invent features a property lacks. Compliance: No misleading property claims.

**V04 Restaurant content retainer.** 60 food visuals and 8 reels a month, Swahili and English captions. Pipeline: `qwen-image → wan-i2v → compositor` on **pod**. Evidence: Ongea Pesa calendar (Mama Mboga, Mandazi) proves the local-vernacular format. Risk: Food must match the real menu. Compliance: Label AI-generated food imagery.

**V05 E-commerce model photos.** Every SKU on AI models in 4 poses, white and lifestyle backgrounds. Pipeline: `wardrobe → faceswap-consented` on **pod**. Evidence: ArtificialQuotient 'AI fashion models for e-commerce' (2.6k views); KiubAI infinite wardrobe workflow. Risk: Garment fidelity; returns if colours drift. Compliance: Fictional or licensed models only.

**V06 WhatsApp Status daily.** One branded Status a day, scheduled through OpenWA. Pipeline: `compositor → openwa` on **hosted**. Evidence: OpenWA publishing already built; M-Pesa-native market. Risk: WhatsApp number bans if volume is careless. Compliance: Opt-in contacts only.

**V07 Faceless shorts channel.** Daily faceless short: script, voice, visuals, captions. Pipeline: `hyperframes → tts → wan-i2v → captions` on **pod**. Evidence: ArtificialQuotient: Viblo faceless shorts (10k), FacelessReels review (13k). Risk: Platform demonetises low-effort AI content. Compliance: Disclose synthetic media.

- Decision: 2026-09-20: `hyperframes` (kinetic type) stays a declared gap until packages/video/motion_graphics.py exists; voice, WAN visuals and burned-in captions are bound, so a shorts pipeline without kinetic type can ship.

- Decision: 2026-09-20 (W6): kinetic type is bound to packages/video/motion_graphics.py (a spec of timed lines from the brief, kit colours, ffmpeg encode); to lay it over the WAN clip instead, wire the clip into its optional background input on the canvas. No declared gap left.

**V08 Thumbnail and cover retainer.** Up to 30 thumbnails a month with 3 variants each for A/B tests. Pipeline: `nano-banana-2 → compositor` on **hosted**. Evidence: Compositor already renders exact text and logos deterministically. Risk: Crowded market. Compliance: No impersonation of real people.

## UGC ads

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| U01 | **UGC ad pack** | D2C brands spending on Meta/TikTok ads | $1,200 | $250 | $2,400 · $7,200 · $18,000 | $5,602 | 78% | $400 | 0.1 mo | 14 d |
| U02 | **TikTok Shop product videos** | TikTok Shop sellers | $800 | $213 | $2,400 · $6,400 · $20,000 | $4,615 | 72% | $250 | 0.1 mo | 10 d |
| U03 | **Hook testing retainer** | Performance marketers | $900 | $221 | $1,800 · $4,500 · $13,500 | $3,333 | 74% | $150 | 0.0 mo | 10 d |
| U04 | **Sheng and Swahili fintech ads** | Kenyan fintechs, SACCOs, telcos | $700 | $213 | $700 · $2,800 · $8,400 | $1,888 | 67% | $300 | 0.2 mo | 21 d |
| U05 | **App install demo ads** | Mobile app startups | $1,000 | $223 | $1,000 · $4,000 · $10,000 | $3,057 | 76% | $200 | 0.1 mo | 14 d |
| U06 | **Multilingual spokesperson** | Brands selling in East Africa and francophone markets | $900 | $236 | $900 · $3,600 · $9,000 | $2,594 | 72% | $300 | 0.1 mo | 21 d |
| U07 | **Viral format remakes** | Brands wanting trend-speed content | $600 | $200 | $1,200 · $4,800 · $12,000 | $3,161 | 66% | $150 | 0.0 mo | 10 d |

**U01 UGC ad pack.** 20 UGC-style ads a month across the 10 formats. Pipeline: `persona-refmod → h3-ref2va → tts → captions` on **pod**. Evidence: MatrixLab 'ComfyUI + Claude = unlimited AI UGC' (14k); DGI Kaos 10 UGC formats. Risk: Ad platforms tightening AI-disclosure rules. Compliance: AI disclosure; no fake testimonials.

**U02 TikTok Shop product videos.** 15 product demo videos a month with hooks. Pipeline: `product-relight → h3-ref2va → captions` on **pod**. Evidence: ArtificialQuotient 'Supercool AI for TikTok Shop ads' (2.9k). Risk: Product must look exactly like the real item. Compliance: Show real product; no false claims.

**U03 Hook testing retainer.** 50 hook variants a month for one winning ad. Pipeline: `hook-variants → h3-ref2va` on **pod**. Evidence: packages/analytics already power-gates factor tests. Risk: Only valuable with the client's ad data. Compliance: Same as source ad.

**U04 Sheng and Swahili fintech ads.** Local-language UGC ads with claim-safety review. Pipeline: `persona-refmod → tts-sw → compositor → claim-check` on **pod**. Evidence: Ongea Pesa brand engine and claim-safety gate built for exactly this. Risk: Financial promotion rules; long sales cycles. Compliance: No returns or rate promises; CBK/CA rules.

**U05 App install demo ads.** Voice-over phone-mockup demos in 3 lengths. Pipeline: `hyperframes → tts → phone-mockup` on **hosted**. Evidence: ArtificialQuotient 'Hyperframes + Claude motion graphics' (18k). Risk: Needs real screen recordings. Compliance: Show real app behaviour.

- Decision: 2026-09-20: `hyperframes` and `phone-mockup` both resolve to the motion-graphics node, still a declared gap (packages/video/motion_graphics.py). The voice-over is bound; the demo cannot ship without the renderer.

- Decision: 2026-09-20 (W6): bound to packages/video/motion_graphics.py; `background.phone: true` with a `screen` image draws the phone mock-up and the typed lines run over it. The demo ships from the app screenshots and the voiceover.

**U06 Multilingual spokesperson.** One consented spokesperson, lip-synced in EN/SW/FR. Pipeline: `refmod-consented → lipsync → tts` on **pod**. Evidence: ArtificialQuotient 'Grok lip sync with consistent characters' (105k views). Risk: Consent paperwork per face. Compliance: Signed likeness release; disclose AI.

**U07 Viral format remakes.** Re-make trending reel structures with the brand's own assets. Pipeline: `reel-analysis → motion-control` on **pod**. Evidence: MatrixLab 'Copy viral AI reels in seconds with Claude' (16k). Risk: Copying too closely invites takedowns. Compliance: Grammar only, never the original footage.

## AI influencer / AI model as a business

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| P01 | **Own AI influencer** | Brands buying sponsored posts | $300 | $55 | $0 · $1,200 · $3,600 | $830 | 69% | $600 | 0.7 mo | 90 d |
| P02 | **Merch with the AI model** | The persona's audience | $12 | $2 | $240 · $1,800 · $7,200 | $1,528 | 85% | $250 | 0.2 mo | 60 d |
| P03 | **Character licensing** | Brands wanting a mascot without a celebrity | $800 | $240 | $800 · $2,400 · $6,400 | $1,620 | 68% | $300 | 0.2 mo | 45 d |
| P04 | **Persona as a service** | Agencies wanting their own AI creators | $2,000 | $343 | $2,000 · $4,000 · $12,000 | $3,164 | 79% | $500 | 0.2 mo | 30 d |
| P05 | **Realism fix setup** | Existing AI-influencer page owners | $300 | $200 | $600 · $2,400 · $7,500 | $771 | 32% | $150 | 0.2 mo | 14 d |
| P06 | **Character boards and datasets** | Creators starting a persona (units = boards) | $150 | $23 | $750 · $3,750 · $12,000 | $3,137 | 84% | $100 | 0.0 mo | 7 d |
| P07 | **Virtual try-on for fashion** | Online fashion stores | $700 | $225 | $700 · $3,500 · $10,500 | $2,326 | 66% | $250 | 0.1 mo | 21 d |
| P08 | **Brand ambassador for local brands** | Kenyan banks, telcos, FMCG | $2,500 | $386 | $0 · $2,500 · $7,500 | $1,964 | 79% | $800 | 0.4 mo | 90 d |
| P09 | **Personalised persona greetings** | Fans of the persona (units = videos) | $15 | $3 | $300 · $1,800 · $7,500 | $1,464 | 81% | $100 | 0.1 mo | 45 d |

**P01 Own AI influencer.** A consistent SFW persona with an audience, sold as sponsorships. Pipeline: `krea2 → dataset-aio → caption-dataset → lora-or-refmod → carousel → reels` on **pod**. Evidence: MatrixLab 'Ultra realistic AI influencer from scratch' (27k); LoRAtech ban-proofing video. Risk: Audience growth takes months; account bans. Compliance: Label as AI; platform synthetic-media rules.

**P02 Merch with the AI model.** Print-on-demand apparel and posters featuring the persona (units = orders). Pipeline: `compositor → print-on-demand` on **hosted**. Evidence: price_usd here is margin per order after print-on-demand cost. Risk: Needs the audience from P01 first. Compliance: Own persona IP only; no trademark mashups.

**P03 Character licensing.** Exclusive monthly rights to a consistent AI character in one category. Pipeline: `refmod → h3-ref2va → carousel` on **pod**. Evidence: RefMods make a character in seconds (Dainamo, KiubAI H3 reference mode). Risk: Exclusivity conflicts across clients. Compliance: Written licence terms.

**P04 Persona as a service.** Build and run a persona end to end: content, posting, reporting. Pipeline: `dataset-aio → refmod → postiz → analytics` on **pod**. Evidence: MatrixLab sells 'complete systems' in its Skool; demand is proven. Risk: High service load per client. Compliance: AI disclosure on every account.

**P05 Realism fix setup.** Install our realism and anti-slop pipeline, then monthly tuning. Pipeline: `realism-img2img → upscale` on **pod**. Evidence: LoRAtech 'AI influencers are getting banned, I built a ComfyUI fix'; 'real life locations, no AI slop'. Risk: Buyers may resell the method. Compliance: SFW accounts only.

**P06 Character boards and datasets.** Consistent character board plus 40-image training dataset. Pipeline: `character-sheet → dataset-aio → caption-dataset` on **pod**. Evidence: MatrixLab 'Character board makes your AI influencer 100% consistent'; 'Dataset from 3 photos'. Risk: Low price, needs volume. Compliance: Fictional characters or signed release.

**P07 Virtual try-on for fashion.** Customers' chosen outfits on consistent models, 200 looks a month. Pipeline: `wardrobe → klein-edit` on **pod**. Evidence: KiubAI 'Infinite wardrobe for your character' free workflow. Risk: Fit accuracy expectations. Compliance: Fictional models.

**P08 Brand ambassador for local brands.** A disclosed AI ambassador with a year of content. Pipeline: `refmod → h3-ref2va → tts-sw → compositor` on **pod**. Evidence: Ongea Pesa system is the working proof to show procurement. Risk: Procurement cycles; reputational caution. Compliance: Disclosure; ASA/CA advertising codes.

**P09 Personalised persona greetings.** Short personalised greeting videos. Pipeline: `refmod → lipsync → tts` on **pod**. Evidence: Cameo-style demand; lip sync videos draw 100k+ views (ArtificialQuotient). Risk: Depends on P01 audience. Compliance: SFW only; label as AI.

## Music videos and artist visuals

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| M01 | **Full-length music video** | Independent artists and EPALLE (units = videos) | $3,000 | $846 | $0 · $3,000 · $9,000 | $2,054 | 68% | $500 | 0.2 mo | 30 d |
| M02 | **Artist visual retainer** | Artists releasing monthly | $900 | $371 | $900 · $3,600 · $10,800 | $2,054 | 57% | $200 | 0.1 mo | 21 d |
| M03 | **Spotify Canvas and loops** | Artists and labels (per release) | $200 | $34 | $600 · $3,000 · $10,000 | $2,468 | 82% | $80 | 0.0 mo | 10 d |
| M04 | **Release rollout kit** | Artists before a drop | $350 | $117 | $700 · $2,800 · $8,750 | $1,831 | 65% | $100 | 0.1 mo | 14 d |
| M05 | **Artist digital double** | Artists who want more content without shoots | $600 | $348 | $600 · $2,400 · $7,200 | $968 | 40% | $150 | 0.2 mo | 21 d |
| M06 | **Event VJ loops** | Clubs, festivals, concert producers (units = events) | $500 | $155 | $500 · $2,000 · $5,000 | $1,361 | 68% | $150 | 0.1 mo | 21 d |
| M07 | **Label visual package** | Small labels with 5+ artists | $4,000 | $632 | $0 · $4,000 · $8,000 | $3,168 | 79% | $500 | 0.2 mo | 60 d |
| M08 | **Stock B-roll subscription** | Editors and creators (units = subscribers) | $19 | $1 | $380 · $2,850 · $11,400 | $2,590 | 91% | $300 | 0.1 mo | 45 d |

**M01 Full-length music video.** 3-4 minute music video with infinite-length H3, SCAIL motion and relit VFX. Pipeline: `h3-infinite → motion-control → relight → lipsync → edit` on **pod**. Evidence: LoRAtech 'MiniMax H3 infinite length videos (low VRAM)' (59k); ArtificialQuotient Beeble relight (3.5k). Risk: Long renders; quality bar is high. Compliance: Artist consent for any likeness; licensed audio.

- Decision: 2026-09-20: `relight` stays a declared gap. Closing it needs a video relight ComfyUI workflow (IC-Light video or a Beeble SwitchLight-style graph) registered in workflows/manifest.json with a .ports.json; sell the video without the relight pass until then.

- Decision: 2026-09-20 (W6): checked the one 'relight' the library has: WanAnimate_relight_lora_fp16.safetensors inside the two ICY WAN ANIMATE V4 graphs. It only matches a swapped character's light to the driving clip during a body or face swap and cannot change the light on footage, so binding it would fake the step. Still a gap; the exact missing thing is on the catalogue node (IC-Light video or SwitchLight graph with video, light_direction and prompt ports).

**M02 Artist visual retainer.** 4 visualizers, 1 lyric video and cover art a month. Pipeline: `hyperframes → wan-i2v → compositor` on **pod**. Evidence: ArtificialQuotient Revid music-to-video and OpenArt lip-sync music videos. Risk: Artists have thin budgets. Compliance: Licensed audio only.

- Decision: 2026-09-20: `hyperframes` (motion graphics) stays a declared gap until packages/video/motion_graphics.py wraps a HyperFrames or Remotion renderer; the visualizers ship from WAN image-to-video and the compositor meanwhile.

- Decision: 2026-09-20 (W6): `hyperframes` now runs on packages/video/motion_graphics.py (Pillow frames, ffmpeg encode, brand-kit colours; typed text, kinetic type, lower thirds, phone mock-ups). No Node renderer is installed or required; HyperFrames/Remotion stay a documented upgrade path for spring and per-glyph animation. Lyric videos are a spec of timed lines; the engine does not run this python step as a stage yet (runner LOCAL_STEPS), it is run from the command line.

**M03 Spotify Canvas and loops.** 8-second Canvas loops for every track on a release. Pipeline: `wan-i2v → loop-edit` on **pod**. Evidence: Cheap, fast, repeatable per track. Risk: Low price point. Compliance: Licensed cover art only.

**M04 Release rollout kit.** Cover art, 10 teaser clips, carousel and WhatsApp Status set. Pipeline: `compositor → wan-i2v → openwa` on **pod**. Evidence: EPALLE brand system reused per artist. Risk: Seasonal demand around releases. Compliance: Licensed audio.

**M05 Artist digital double.** Consented RefMod of the artist for monthly promo clips. Pipeline: `refmod-consented → h3-ref2va → lipsync` on **pod**. Evidence: Dainamo RefMod demo: identity preserved from 24 photos. Risk: Artists wary of deepfake stigma. Compliance: Signed release, revocable; watermark disclosure.

**M06 Event VJ loops.** 30 minutes of on-theme visual loops per event. Pipeline: `wan-t2v → ltx → loop-edit` on **pod**. Evidence: Nairobi event scene; generative loops are cheap to render. Risk: Seasonal. Compliance: No third-party logos.

**M07 Label visual package.** Monthly visual retainer across the roster. Pipeline: `M02 → M03 → M04` on **pod**. Evidence: Bundles M02-M04 at scale. Risk: Concentration on one client. Compliance: Licensed audio; artist consent.

- Decision: 2026-09-20: inherits M02's motion-graphics gap (packages/video/motion_graphics.py not built); everything else in the bundle is bound.

- Decision: 2026-09-20 (W6): M02's motion-graphics step is bound to packages/video/motion_graphics.py, so the bundle has no declared gap left.

**M08 Stock B-roll subscription.** Monthly drop of 100 royalty-free African-set AI B-roll clips. Pipeline: `wan-t2v → ltx → upscale` on **pod**. Evidence: Gap: few African-context stock libraries. Risk: Discovery and distribution. Compliance: Model licences must allow commercial output.

## Productised creative services

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| S01 | **RefMod or LoRA as a service** | Creators and brands (units = characters) | $150 | $24 | $600 · $3,000 · $9,000 | $2,487 | 83% | $100 | 0.0 mo | 7 d |
| S02 | **Product photography replacement** | Retailers paying for studio shoots | $900 | $151 | $900 · $4,500 · $13,500 | $3,683 | 82% | $250 | 0.1 mo | 14 d |
| S03 | **Interior and architecture visuals** | Architects, developers, interior designers | $1,000 | $156 | $1,000 · $4,000 · $10,000 | $3,324 | 83% | $250 | 0.1 mo | 21 d |
| S04 | **Archive restore and upscale** | Families, churches, media houses | $400 | $117 | $800 · $3,200 · $10,000 | $2,248 | 70% | $100 | 0.0 mo | 7 d |
| S05 | **Training avatar videos** | HR teams and NGOs | $1,200 | $190 | $1,200 · $3,600 · $9,600 | $2,971 | 82% | $300 | 0.1 mo | 30 d |
| S06 | **Explainer videos** | Startups, NGOs, public health programmes | $1,500 | $198 | $1,500 · $4,500 · $12,000 | $3,855 | 86% | $200 | 0.1 mo | 21 d |
| S07 | **Short-form dubbing** | Creators expanding to Swahili and French | $500 | $138 | $1,000 · $4,000 · $12,500 | $2,854 | 71% | $150 | 0.1 mo | 14 d |
| S08 | **Podcast to shorts** | Podcasters | $350 | $117 | $1,050 · $3,500 · $10,500 | $2,299 | 66% | $80 | 0.0 mo | 7 d |

**S01 RefMod or LoRA as a service.** A consistent-character file from client-owned references. Pipeline: `refmod → caption-dataset → ai-toolkit-lora` on **pod**. Evidence: KiubAI Klein 9B LoRA training (4.7k); LoRAtech character LoRA series; RefMods in seconds. Risk: Commoditising fast. Compliance: Consent proof required before training.

- Decision: 2026-09-20: `ai-toolkit-lora` stays a declared gap because the LoRA is the product being sold; RefMod (refmod-create, H3) is the deliverable we can make today and the offer says so. Closing the gap needs a python job module (proposed packages/engine/lora_train.py) that runs ostris/ai-toolkit on the pod from the captioned dataset.

- Decision: 2026-09-20 (W6): `ai-toolkit-lora` is bound to packages/engine/lora_train.py: rights gate (owned or licensed data, fictional or consented), ai-toolkit config.yaml, captions from the caption-dataset step, pod launch.sh and manifest. It never trains: the run is started by hand on the pod and needs an ai-toolkit clone plus the Klein 9B base model there (needs_setup, BLOCKERS 3). RefMod remains the same-day deliverable.

**S02 Product photography replacement.** Unlimited product shots from 3 phone photos per SKU. Pipeline: `klein-edit → product-relight → upscale` on **pod**. Evidence: ArtificialQuotient RiverFlow product photos (643); Krea 2 image-to-image (LoRAtech 10k). Risk: Label and text accuracy on packaging. Compliance: Real product appearance.

- Decision: 2026-09-20: the video `relight` gap was the wrong step for stills; the pipeline now uses `product-relight`, which the Qwen image-edit workflow already runs by instruction (same node as klein-edit, so the template shows one edit step).

**S03 Interior and architecture visuals.** Renders and walkthrough clips from sketches or empty rooms. Pipeline: `consistent-room → wan-i2v` on **pod**. Evidence: KiubAI 'Consistent room and backgrounds with ComfyUI and Flux Klein' (2.7k). Risk: Measurement accuracy expectations. Compliance: Mark as concept visuals.

**S04 Archive restore and upscale.** Restore, colourise and upscale old photos and footage. Pipeline: `upscale → restore` on **pod**. Evidence: LoRAtech upscale workflow build-along (9.2k). Risk: Faces must stay truthful. Compliance: Owner consent.

- Decision: 2026-09-20: `restore` runs interim on the Qwen image-edit workflow with a fixed restore instruction (keep every face as it is). A dedicated restoration graph (face restoration plus colourise) is still missing from workflows/manifest.json; add it and re-point the `restore` node when it lands.

**S05 Training avatar videos.** Consented presenter avatar for 10 training videos a month. Pipeline: `refmod-consented → lipsync → tts → hyperframes` on **pod**. Evidence: ArtificialQuotient Synthesia and HeyGen tutorials show paid demand; ours runs on open models. Risk: Competes with Synthesia and HeyGen. Compliance: Presenter release.

- Decision: 2026-09-20: `hyperframes` (title cards and lower thirds) stays a declared gap until packages/video/motion_graphics.py exists; the avatar, voice and lip-sync steps are bound.

- Decision: 2026-09-20 (W6): `hyperframes` is bound to packages/video/motion_graphics.py; the lip-synced avatar clip feeds its optional background input, so title cards and lower thirds render over the presenter. No declared gap left.

**S06 Explainer videos.** Two 90-second explainers a month. Pipeline: `hyperframes → remotion → tts` on **hosted**. Evidence: ArtificialQuotient 'Remotion with Claude Code' (15k) and Vox-style explainer tutorial. Risk: Script and research time dominates. Compliance: Fact-checked claims.

- Decision: 2026-09-20: `hyperframes` and `remotion` both resolve to the motion-graphics node, still a declared gap: packages/video/motion_graphics.py wrapping a Remotion project or HyperFrames is the one missing module. Do not sell this idea before it exists.

- Decision: 2026-09-20 (W6): both steps resolve to the motion-graphics node, now bound to packages/video/motion_graphics.py (Pillow and ffmpeg, no Node). A 90-second explainer is a spec of timed lines over colour, image or footage backgrounds plus the voiceover; richer animation (springs, per-glyph, 3D) still means adding a Remotion or HyperFrames renderer behind the same spec, documented in the module.

**S07 Short-form dubbing.** Dub and re-caption 20 shorts a month. Pipeline: `transcribe → translate → tts → lipsync → captions` on **pod**. Evidence: packages/voice transcribe + TTS bake-off already built. Risk: Voice quality in Sheng. Compliance: Original creator permission.

- Decision: 2026-09-20: `translate` stays a declared gap: packages/voice/translate.py (an OpenRouter chat call with the key the image-router already uses) is the missing module. Until then the translator is a person and the dub runs from the translated script.

- Decision: 2026-09-20 (W6): `translate` is bound to packages/voice/translate.py: OpenRouter chat completion through the vault key, .txt/.srt/.json in and out, a glossary of brand terms masked as placeholders so they come back untouched, and a claim check that refuses a translation whose numbers, glossary terms or money-promise flags differ from the source. Dry-run prints the request and sends nothing; a Sheng target is refused unless --sheng-reviewed. Needs OPENROUTER_API_KEY in the vault to run live.

**S08 Podcast to shorts.** 30 captioned clips a month from long episodes. Pipeline: `transcribe → clip-select → captions` on **hosted**. Evidence: ArtificialQuotient CapCut AI clipper (4.3k), Ssemble review. Risk: Tools like CapCut do this cheaply. Compliance: Podcaster owns content.

## Education and community

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| E01 | **AI creator lab community** | African creators and freelancers | $29 | $2 | $1,160 · $5,800 · $23,200 | $5,240 | 90% | $400 | 0.1 mo | 30 d |
| E02 | **Course on Whop** | Beginners (units = sales a month) | $149 | $11 | $745 · $3,725 · $11,920 | $3,365 | 90% | $300 | 0.1 mo | 30 d |
| E03 | **Original workflow packs** | ComfyUI users (units = packs sold) | $39 | $6 | $390 · $2,340 · $7,800 | $1,978 | 84% | $150 | 0.1 mo | 21 d |
| E04 | **Live cohort bootcamp** | Freelancers wanting clients (units = seats) | $100 | $20 | $500 · $2,000 · $6,000 | $1,540 | 77% | $200 | 0.1 mo | 45 d |
| E05 | **Agency incubator** | Small agencies adopting AI | $500 | $78 | $500 · $2,000 · $5,000 | $1,647 | 82% | $200 | 0.1 mo | 30 d |

**E01 AI creator lab community.** Monthly membership: our own workflows, weekly builds, job board. Pipeline: `whop-publish` on **hosted**. Evidence: MatrixLab runs a paid Skool; LoRAtech a Patreon; KiubAI paid packs. Risk: Needs consistent content output. Compliance: Only our original workflows; no resale of paid packs.

**E02 Course on Whop.** ComfyUI-to-income course with the studio's lessons. Pipeline: `whop-publish` on **hosted**. Evidence: packages/publish/whop publisher already built. Risk: Course market is saturated. Compliance: No income guarantees.

**E03 Original workflow packs.** Our own tested workflows with setup guides. Pipeline: `register-workflow` on **hosted**. Evidence: Icekiub and LoRAtech monetise packs; our epalle-nodes pack is original. Risk: Free alternatives on Discord. Compliance: Never bundle bought packs (Icekiub etc.).

- Decision: 2026-09-20: `register-workflow` is now a catalogue step on packages/library/tools/register_workflow.py (attribution and sha256 into workflows/manifest.json). The engine does not execute this python step yet (runner LOCAL_STEPS); it is run from the command line.

**E04 Live cohort bootcamp.** 4-week cohort ending with a paying client. Pipeline: `community` on **hosted**. Evidence: price_usd is seat price spread per month. Risk: Delivery time heavy. Compliance: No earnings claims.

**E05 Agency incubator.** Done-with-you setup of this studio for their team. Pipeline: `studio-handoff → community` on **pod**. Evidence: The studio itself is the product demo. Risk: Creates competitors. Compliance: Clear licence of our code.

- Decision: 2026-09-20: the vague `studio` step became `studio-handoff` (studio.py doctor and check on the team's install, the handoff report) plus the Whop `community` channel for the done-with-you weeks. The engine does not execute studio.py as a stage yet; it is run on the client's machine.

## Software and usage-based

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| A01 | **Brand engine for SMEs** | Small businesses | $29 | $6 | $870 · $4,350 · $17,400 | $3,258 | 75% | $1,500 | 0.5 mo | 60 d |
| A02 | **M-Pesa pay-per-post credits** | Informal traders (units = posts) | $0 | $0 | $195 · $1,170 · $4,680 | $350 | 30% | $800 | 2.3 mo | 45 d |
| A03 | **Image API for agencies** | Agencies and app builders (units = 1,000 images) | $25 | $7 | $250 · $1,500 · $6,250 | $939 | 63% | $600 | 0.6 mo | 45 d |

**A01 Brand engine for SMEs.** Self-serve: upload logo, get a month of branded posts. Pipeline: `brandkit → compositor → nano-banana-2` on **hosted**. Evidence: Ongea Pesa brand engine generalised. Risk: Software build effort and support. Compliance: Claim-safety on generated copy.

**A02 M-Pesa pay-per-post credits.** Pay KES 50 via M-Pesa for one branded post. Pipeline: `nano-banana-2 → compositor` on **hosted**. Evidence: Ongea Pesa voice M-Pesa product is the payment rail. Risk: Payments integration and fraud. Compliance: CBK payment rules; Daraja terms.

- Decision: 2026-09-20: the `ongea-pesa` payment step left the content pipeline. Collecting KES 50 is the Ongea Pesa product's job (Safaricom Daraja STK push) before an order reaches the studio; no module in packages/ talks to Daraja and a payment gate is not a creative step. The studio side is the hosted image plus the compositor.

**A03 Image API for agencies.** Branded image generation API at a flat per-thousand price. Pipeline: `comfy-client → compositor` on **pod**. Evidence: Unit cost ~$4 per 1,000 images on the pod vs $70 hosted. Risk: Uptime and serverless not yet proven. Compliance: Acceptable-use policy; abuse monitoring.

- Decision: 2026-09-20: `comfy-client` is now the `comfy-api` catalogue step on packages/comfy-client/client.py (pod or serverless submission with pre-flight validation). Serverless has never returned COMPLETED (docs/BLOCKERS.md item 2); prove it with the smoke test before selling.

## Fictional 18+ AI personas (compliance-gated)

| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |
|---|---|---|---|---|---|---|---|---|---|---|
| X01 | **Fictional 18+ persona subscription** | Adult subscribers on AI-permitting platforms (units = subscribers) | $10 | $1 | $500 · $4,000 · $20,000 | $3,468 | 87% | $700 | 0.2 mo | 60 d |
| X02 | **Compliance-first persona operations** | Operators of fictional 18+ personas | $1,000 | $158 | $0 · $2,000 · $6,000 | $1,604 | 80% | $300 | 0.2 mo | 45 d |

**X01 Fictional 18+ persona subscription.** Subscription to a fully fictional adult persona on a platform that allows disclosed AI content. Pipeline: `dataset-fictional → caption-dataset → lora → carousel` on **pod**. Evidence: LoRAtech and KiubAI build OFM-style persona pipelines; plan only, no explicit content produced here. Risk: Platform policy changes; payment processor risk; brand contamination. Compliance: HARD GATES: fictional adults only, never real or look-alike people, no minors or youthful styling, AI disclosure, platform ToS, separate entity/accounts/payments, never on Ongea Pesa or EPALLE infrastructure.

- Decision: 2026-09-20: `lora` stays a declared gap (same missing ai-toolkit job module as S01); the dataset and captions exist to train it, so RefMod is not substituted here. Plan only until the module and the separate entity exist.

- Decision: 2026-09-20 (W6): `lora` is bound to packages/engine/lora_train.py (same module as S01); the caption-dataset output feeds its captions input. The rights gate demands a fictional collection (no real-person likeness) with owned data, and the run itself still needs ai-toolkit and the base model on the pod (needs_setup, BLOCKERS 3). The separate entity and hard gates are unchanged; still plan only.

**X02 Compliance-first persona operations.** SFW teaser content, scheduling and a compliance audit trail. Pipeline: `carousel → postiz → audit-log` on **pod**. Evidence: Hash-chained audit log in packages/orchestrator already records who approved what. Risk: Reputational risk to the studio. Compliance: Same hard gates as X01; SFW deliverables only.
