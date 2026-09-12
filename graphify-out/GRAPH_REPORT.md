# Graph Report - C:\Users\inkno\Documents\GitHub\comfy  (2026-09-12)

## Corpus Check
- Large corpus: 287 files · ~885,267 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 1493 nodes · 2692 edges · 103 communities (91 shown, 12 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 314 edges (avg confidence: 0.78)
- Token cost: 765,930 input · 0 output

## Community Hubs (Navigation)
- Orchestrator Control Plane
- Workflow Builder Canvas UI
- Reference Harvesters
- RunPod API And Provisioning
- Ongea Pesa Visual Systems
- Memory Store And Learning
- Workflow Builder Dependencies
- Postiz Publishing And Metrics
- Studio Client Dependencies
- End-to-End Test Suite
- Voice Transcription And Mux
- ComfyUI Client
- EPALLE Treatment And ASALI Styles
- Skill Curator And Task Runner
- RunPod Deployment Principles
- Content Studio Skill Routing
- Whop Course Publisher
- Architecture Design Decisions
- Ongea Pesa Calendar And Styles
- Publishing QA Lessons
- EPALLE Course And Model Stack
- Deterministic Compositor
- Creator Channels And Evidence
- Vision Reference Analysis
- WhatsApp Status Sender
- Paid Provider Safety Locks
- Monorepo Overview And Rights
- Image Router
- Brand Kit Loader
- TTS Voiceover Bake-Off
- Claim Safety And Memory Governance
- Licensing Constraints
- Treatment Shot Routing
- Planning And Grammar Concepts
- Blockers Register
- EPALLE Brand Kit And Arc
- Two Brands And Findings
- UGC Formats And Shot Taxonomy
- Typed Corpus Graph Builder
- Course Build And Download Tools
- Grammar Study Module
- Studio UI Workspace Config
- Ongea Pesa Claim-Safe Styles
- Graph Query And Provenance
- Content Planner
- Song To Treatment Builder
- EPALLE Cover Art Motifs
- Editorial Experimental Styles
- Secrets And Memory Deployment
- Research Library And Watcher
- EPALLE Mirror And Rival Imagery
- Scale-To-Zero And Send Safeguards
- Contract Pricing
- Graph Query CLI
- Crushed Blacks Drift Checks
- EPALLE Visual Language Violations
- A-Z Setup Guide
- SageAttention A100 Install
- Daily Source Watcher
- Film Poster Type Grammar
- Postiz VPS Deployment
- Jobs Page UI
- Composite The Logo Principle
- Grammar Not Images Principle
- Custom Node Pack And Licences
- Model Auditor
- SageAttention Generic Install
- Library Page UI
- ASALI Desire And Sweetness
- Standing Rules And Text Policy
- Faceless Protagonist Imagery
- Core Thesis Models Versus Code
- Workflow Importer
- Studio Home Page
- Workflow Listing Page
- Planned Model Downloader
- Sage-Free Retry Tool
- Workflow Runner
- DPAPI Secret Setter
- library/route.js
- compilerOptions
- presets
- Wedding-Funeral Interior Set (aisle,
- packages/orchestrator
- disable sage workflow nodes.py
- download-workflow-models.py
- start-serverless.sh
- runpod-status/route.js
- layout.js
- manifest.json
- setup-pod.sh
- start-comfy.sh
- eslint.config.mjs
- next.config.mjs
- postcss.config.mjs
- test local workers run

## God Nodes (most connected - your core abstractions)
1. `EPALLE Studio x Ongea Pesa Autonomous Content Company Design` - 44 edges
2. `RunPod` - 29 edges
3. `Content Studio skill` - 23 edges
4. `content-studio Skill` - 22 edges
5. `load_brand()` - 20 edges
6. `EPALLE Brand Kit` - 20 edges
7. `Ongea Pesa Brand Kit` - 19 edges
8. `Task` - 18 edges
9. `Blockers` - 18 edges
10. `EPALLE Studio x Ongea Pesa Monorepo` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Constraints are the point (infinite variety looks cheap)` --semantically_similar_to--> `Style grammar (fix the system, vary the subject)`  [INFERRED] [semantically similar]
  packages/publish/whop/lessons/04-01-epalle-visual-language.md → .agents/skills/content-studio/SKILL.md
- `Generation Route Decided at Shot-List Time` --semantically_similar_to--> `image-router backend routing (hosted vs comfy)`  [INFERRED] [semantically similar]
  packages/publish/whop/lessons/04-02-asali-treatment-and-animatic.md → .agents/skills/content-studio/SKILL.md
- `logo_policy: COMPOSITE_ONLY` --semantically_similar_to--> `Composite the Logo, Never Regenerate It`  [INFERRED] [semantically similar]
  brands/ongea-pesa/styles/cinematic_african_realism.yaml → .claude/skills/content-studio/SKILL.md
- `EPALLE Flower Vocabulary` --semantically_similar_to--> `EPALLE Stated Visual Language (charcoal / ivory / dust gold, never pure black)`  [INFERRED] [semantically similar]
  brands/epalle/styles/asali_05_gratitude.yaml → brands/epalle/assets/cover/MAIN COVER ART.png
- `Original Scenarios Only (never recreate an existing meme)` --semantically_similar_to--> `Take the Grammar, Never the Images`  [INFERRED] [semantically similar]
  brands/ongea-pesa/styles/kenyan_meme_original.yaml → docs/ABOUT.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Deterministic brand enforcement (generate loose, enforce in code)** — agents_skills_content_studio_skill_models_make_pictures_code_makes_brands, chama_logo_policy_composite_only, asali04_text_policy_none, agents_skills_content_studio_skill_compositor, chama_disclosure_field [INFERRED 0.85]
- **Song to shot list to generation route** — agents_skills_content_studio_skill_treatment_py, brands_epalle_calendar_treatment_ancestral_pulse, treatment_locked_values, treatment_route_segmented, treatment_profile_i2v_infinite, asali04_style [EXTRACTED 1.00]
- **Paid distribution licence risk surface** — docs_licensing_whop_paid_distribution, docs_licensing_gpl3_h3, docs_licensing_icekiub_workflows, hfpages_access_not_licence, hfpages_unverified_loras [INFERRED 0.85]
- **Brand-Safe Generation Pipeline (grammar → route → graph → composite)** — claude_skills_content_studio_skill_brandkit, agents_skills_content_studio_skill_image_router, agents_skills_content_studio_skill_comfy_client, agents_skills_content_studio_skill_compositor, agents_skills_content_studio_skill_style_grammar, claude_skills_content_studio_skill_composite_logo_never_regenerate [EXTRACTED 1.00]
- **Song to Music Video Flow (lock audio → arc → shot list → route → animatic)** — lesson_lock_audio_and_fps, asali_arc, lesson_generation_route, lesson_animatic, claude_skills_content_studio_skill_strategy_treatment, claude_skills_content_studio_skill_hero_vs_connective_pacing [EXTRACTED 1.00]
- **Reference Harvest → Measurement → Derived Grammar Governance** — agents_skills_content_studio_skill_ingest_harvesters, claude_skills_content_studio_skill_vision_analyze, claude_skills_content_studio_skill_strategy_study, claude_skills_content_studio_skill_twelve_sample_floor, brands_epalle_references_flowers_falling_footage_grammar_flowers_falling_footage, whop_structure_not_copy [INFERRED 0.85]
- **Generate -> Deterministic Composite -> Scheduled Publish Pipeline** — readme_pkg_brandkit, readme_pkg_image_router, readme_pkg_compositor, readme_pkg_publish, dockercompose_postiz_stack [EXTRACTED 1.00]
- **Model Renders No Text or Marks; Code Composites Them** — asali01_text_policy_none, crimson_logo_policy_composite_only, brands_ongea_pesa_styles_index_fix_system_vary_subject, readme_pkg_compositor, readme_standing_rules [EXTRACTED 1.00]
- **Harvest -> Graph -> Bitemporal Memory Learning Loop** — docs_setup_ingest_harvesters, docs_setup_graph_build, memory_store_py, learning00003_pearl_fatigue, readme_pkg_analytics [INFERRED 0.85]
- **Deterministic Identity Layer (text, logo, disclosure applied in code)** — docs_about_models_make_pictures_code_makes_brands, accstory_text_policy_none, accstory_logo_composite_only, accstory_disclosure_field, what_compositor [EXTRACTED 1.00]
- **Paid-Spend Containment Across Handler, Graph and Router** — lesson0501_dry_run_default, lesson0501_two_independent_locks, runpod_matrix_node_rejection, nodepacks_matrix_power_nodes, nodepacks_pricing_py, docs_about_dry_run_by_default [EXTRACTED 1.00]
- **Evidence Over Assertion (measure, source, and never infer success)** — docs_about_measure_dont_assume, what_evidence_of_claim, lesson0302_claim_sheet, brands_epalle_findings_twelve_sample_floor, docs_about_queued_is_not_success, runpod_model_integrity_check [INFERRED 0.85]
- **Models generate base visual only; copy and logo composited** — composite_only_rule, compositor_package, brands_ongea_pesa_brand, brands_epalle_brand, epalle_nodes [INFERRED 0.85]
- **Publishing path to Instagram/WhatsApp** — publish_package, postiz, openwa, instagram_business_requirement, packages_publish_whatsapp_py [EXTRACTED 1.00]
- **ASALI arc shot generation system** — brands_epalle_brand_asali_arc, epalle_styles_index, brands_epalle_styles_asali_03_doubt_style, brands_epalle_brand_palette, brands_epalle_brand_lighting_setups [EXTRACTED 1.00]

## Communities (103 total, 12 thin omitted)

### Community 0 - "Orchestrator Control Plane"
Cohesion: 0.06
Nodes (75): add_worker(), admit(), approve(), audit(), connect(), ControlError, finish(), main() (+67 more)

### Community 1 - "Workflow Builder Canvas UI"
Cohesion: 0.07
Nodes (61): fetchWorkflowData(), WorkflowPage(), WorkflowBuilderClient(), ApiNode(), outputHandles, AudioGeneration(), inputHandles, outputHandles (+53 more)

### Community 2 - "Reference Harvesters"
Cohesion: 0.08
Nodes (54): backend_ready(), _cli(), harvest(), HarvestError, _int(), _kind(), _opencli(), Any (+46 more)

### Community 3 - "RunPod API And Provisioning"
Cohesion: 0.07
Nodes (33): handler(), Single-owner RunPod worker; only installed API templates can run., request(), available_gpus(), create(), describe(), main(), Live availability in one datacenter, cheapest first. (+25 more)

### Community 4 - "Ongea Pesa Visual Systems"
Cohesion: 0.07
Nodes (49): Designed for Everyone Accessibility Section, Dark Green Brain2Qwerty Research Band, Floating Glassmorphic Status Cards Around Phone, Hero: The Future of Money Is Spoken + Phone Mock, ONGEA Light Marketing Landing Page Mockup, Six Natural Interface Cards (Voice, Mind, Vision, Gesture, Touch, AI), Request Demo / Explore the Interface Pill CTAs, Secure at the Core Line-Icon Row (+41 more)

### Community 5 - "Memory Store And Learning"
Cohesion: 0.09
Nodes (47): _confidence(), factor_effects(), fatigue(), Finding, load(), main(), power_report(), Any (+39 more)

### Community 6 - "Workflow Builder Dependencies"
Cohesion: 0.05
Nodes (42): autoprefixer, @babel/cli, @babel/preset-env, @babel/preset-react, dependencies, axios, react-hot-toast, react-icons (+34 more)

### Community 7 - "Postiz Publishing And Metrics"
Cohesion: 0.12
Nodes (37): AnalyticsError, attach_briefs(), collect_fixture(), collect_instagram(), collect_postiz(), _get(), instagram_insights(), instagram_media() (+29 more)

### Community 8 - "Studio Client Dependencies"
Cohesion: 0.06
Nodes (35): eslint, eslint-config-next, next, dependencies, axios, next, react, react-dom (+27 more)

### Community 9 - "End-to-End Test Suite"
Cohesion: 0.08
Nodes (23): date, load_brand(), fixture_posts(), Any, Fixture generator shared by the analytics tests. Wraps…, End-to-end tests for the studio. Runs the whole pipeline against real repo data…, An unclassified kind would default to whichever gate is convenient., A calendar pointing at a nonexistent grammar must fail loudly, not silently. (+15 more)

### Community 10 - "Voice Transcription And Mux"
Cohesion: 0.10
Nodes (30): _ass_time(), dimensions(), duration(), main(), mux(), MuxError, MuxResult, _need_ffmpeg() (+22 more)

### Community 11 - "ComfyUI Client"
Cohesion: 0.11
Nodes (20): _cli(), ComfyClient, ComfyError, _count_nodes(), Any, Backend, RuntimeError, ComfyUI execution client — one interface, four backends. local 127.0.0.1:8188… (+12 more)

### Community 12 - "EPALLE Treatment And ASALI Styles"
Cohesion: 0.09
Nodes (29): ASALI six-stage arc, EPALLE brand, Take the grammar, never the images, Shot count derived from stage length, study.py creator-grammar study, treatment.py song-to-shot-list, Composed original, never a reproduction, Style: shot_artefact_tableau (+21 more)

### Community 13 - "Skill Curator And Task Runner"
Cohesion: 0.12
Nodes (25): draft_candidate(), evaluate(), Evidence, gather(), is_protected(), main(), propose(), Any (+17 more)

### Community 14 - "RunPod Deployment Principles"
Cohesion: 0.09
Nodes (28): Dry-Run By Default, Queued Is Not Success, extra_model_paths.yaml pointing at volume models/, Accept a List of GPU Types, Not One, manifests/ — pinned node commits and pip freeze, Lesson 01-02 Persistent RunPod Architecture, Volume Recovery Drill, Separate the Machine from the Data (+20 more)

### Community 15 - "Content Studio Skill Routing"
Cohesion: 0.12
Nodes (22): RunPod serverless never completed a generation, ComfyUI client, Content Studio skill, Orchestrator control plane, image-router backend routing (hosted vs comfy), Local-first routing, Queued is not success, Agents create, code validates, humans approve (+14 more)

### Community 16 - "Whop Course Publisher"
Cohesion: 0.20
Nodes (16): check_auth(), find_by_title(), lesson_payload(), main(), print_plan(), publish(), RuntimeError, Walk a cursor-paginated list endpoint and return every item. (+8 more)

### Community 17 - "Architecture Design Decisions"
Cohesion: 0.13
Nodes (21): agent-reach, Codex CLI, packages/comfy-client (4 backends), EPALLE Studio x Ongea Pesa Autonomous Content Company Design, graph/ graphify Corpus Graph, ig_harvest, Image Provider Hierarchy, packages/image-router (OpenRouter) (+13 more)

### Community 18 - "Ongea Pesa Calendar And Styles"
Cohesion: 0.23
Nodes (20): Ongea Pesa brand, Palette provenance (measure, do not assume), Ongea Pesa Calendar Seed (30 ideas), Dignity over spectacle (no poverty stereotypes), AI-assisted imagery disclosure field, logo_policy COMPOSITE_ONLY, Ongea Pesa shared negative prompt, Style: chama_community_story (+12 more)

### Community 19 - "Publishing QA Lessons"
Cohesion: 0.11
Nodes (20): Dry-run by default, Comfy-Org SCAIL-2, Animation versus replacement, Verify audio sync at the end, not the start, Composition matching is the quality lever, Character identity checked as a contact sheet, Master exists and is archived; variants derive from it, Lesson: Publishing QA (+12 more)

### Community 20 - "EPALLE Course And Model Stack"
Cohesion: 0.15
Nodes (20): Standing Rules (Queued Is Not Success, Unknown Is Not OK, Dry-run Default), AI Ninja (creator reference), KiubAI (creator reference), Remove Duplicate Frames and Track Audio Sync at Joins, Reference Conditioning vs LoRA, Lesson 02-03 — MiniMax H3 References and Extension, Data Durability via Hashes and Manifests, EPALLE Creative Studio Project Summary (+12 more)

### Community 21 - "Deterministic Compositor"
Cohesion: 0.18
Nodes (19): FreeTypeFont, ImageDraw, _cli(), composite(), CompositeResult, CompositorError, contrast_ratio(), _cover_resize() (+11 more)

### Community 22 - "Creator Channels And Evidence"
Cohesion: 0.12
Nodes (20): Reference-Ad Numbers Are Evidence About Their Marketing, AiorBust — unresolved, Creator Channel Registry, DGI Kaos, Hearmeman (HearmemanAI) — unresolved, KiubAI (Icekiub), Subtitle Policy (en/sw/fr + faster-whisper fallback), Lesson 03-01 Ten UGC Formats (+12 more)

### Community 23 - "Vision Reference Analysis"
Cohesion: 0.22
Nodes (19): analyse_image(), analyse_video(), _aspect_name(), check_against_brand(), _dist(), Features, _ffprobe(), _hex() (+11 more)

### Community 24 - "WhatsApp Status Sender"
Cohesion: 0.24
Nodes (18): _base(), _headers(), key_for(), _load_state(), main(), _post(), preflight(), Any (+10 more)

### Community 25 - "Paid Provider Safety Locks"
Cohesion: 0.12
Nodes (18): Composite the Logo, Never Regenerate It, Unknown Is Not OK (three-state validation), Two Independent Locks on Paid Provider Nodes, CR Prompt List (batch driver, comfyroll), comfyui-h3-motion-context (GPL-3.0), comfyui-kjnodes (31 dependent workflows), docs/LICENSING.md, matrix-power-nodes (WaveSpeed paid provider surface) (+10 more)

### Community 26 - "Monorepo Overview And Rights"
Cohesion: 0.13
Nodes (18): packages/library/graph_build.py, The Creative Brief (performer, product, audience, language, claims, rights), Research Library as Private Study Material, Lesson: Safety, Rights and the Creative Brief, Reuse Structure, Not Expression, Synthetic Voice Consent Rules, Content Company Design Spec 2026-09-12, EPALLE Studio x Ongea Pesa Monorepo (+10 more)

### Community 27 - "Image Router"
Cohesion: 0.24
Nodes (16): GenRequest, Provider-agnostic request. The router maps this onto a concrete endpoint., choose(), _cli(), execute(), _execute_hosted(), _pick_comfy_profile(), Plan (+8 more)

### Community 28 - "Brand Kit Loader"
Cohesion: 0.23
Nodes (11): Brand, BrandError, build_prompt(), build_request(), _cli(), _load_yaml(), Any, Path (+3 more)

### Community 29 - "TTS Voiceover Bake-Off"
Cohesion: 0.30
Nodes (15): available(), bake_off(), _duration(), _edge_tts(), _elevenlabs(), main(), _openai(), _piper() (+7 more)

### Community 30 - "Claim Safety And Memory Governance"
Cohesion: 0.14
Nodes (15): AI-assisted imagery disclosure field, Agents Create, Code Validates, Humans Approve, Bitemporal Memory, Skill Curator Promotion Gates, Lesson 03-02 Claim-Safe Scripts, The Claim Sheet, Lines to Refuse Outright, Script Review Gate (confirmed rows, named approver, dated version) (+7 more)

### Community 31 - "Licensing Constraints"
Cohesion: 0.15
Nodes (15): FLUX.2 Klein 9B KV licence gate, UNVERIFIED three-state validation, Licensing, GPL-3.0 copyleft problem (work/h3), ComfyUI-H3-Motion-Context node pack, Icekiub workflow JSONs (unstated licence), MATRIX / WaveSpeed power nodes (MIT), Absence of a licence means no distribution rights (+7 more)

### Community 32 - "Treatment Shot Routing"
Cohesion: 0.17
Nodes (15): ASALI Six-Stage Arc, Dust Gold Withheld Until Gratitude, Style: asali_05_gratitude, Style: shot_connective_landscape, Hero Shots Held, Connective Shots Cut Short, strategy/treatment.py, 30-Second Animatic as Cheap Validation, Lesson 04-02 — Treatment and Animatic (ASALI pilot) (+7 more)

### Community 33 - "Planning And Grammar Concepts"
Cohesion: 0.15
Nodes (14): Experiment Variables (hook, first_slide, language, sheng_intensity, cta, subject), Format/ratio is a preference list, plan.py content planner, Portfolio policy 60/25/15 and one-dimension variation, Derived Grammar — Flowers Falling Footage (not derived), claim_class (standard / sensitive / pitch), Experiment variables (hook, language, sheng_intensity, cta...), strategy/plan.py (+6 more)

### Community 34 - "Blockers Register"
Cohesion: 0.19
Nodes (13): packages/analytics, carousel_pose Workflow, comfyui-scail-docker (pinned 0.3.26), Blockers, FLUX.2 Klein 9B KV (licence-gated), Instagram Business Account Requirement, Meta AI via OpenWA Deferred, Minimum 6 Posts per Grammar Before Learning (+5 more)

### Community 35 - "EPALLE Brand Kit And Arc"
Cohesion: 0.20
Nodes (13): EPALLE Brand Kit, ASALI Narrative Arc, EPALLE Song Catalogue, EPALLE Forbidden Looks, One Focal Length Per Piece, EPALLE Lighting Setups (downward_soft, raking_window, open_shade), EPALLE Three-Value Palette (charcoal/ivory/dust gold), Study Ethics: Take Grammar Not Shots (+5 more)

### Community 36 - "Two Brands And Findings"
Cohesion: 0.15
Nodes (14): ASALI (pilot song, no master on disk), EPALLE Vision Analysis Findings, Flowers Falling (cover art + 9 MOV clips), Frame Rate and Audio Master Lock, Grade to Palette as One Final Pass, Ancestral Pulse Treatment (177.3s, 48 shots), Dust Gold Withheld Until Gratitude, EPALLE (music project) (+6 more)

### Community 37 - "UGC Formats And Shot Taxonomy"
Cohesion: 0.17
Nodes (13): Fix the System, Vary Only Subject and Copy, yt_learn / pin_harvest / ig_harvest harvesters, Format-as-Contract (Proof / Visual Action / CTA), Lesson: Ten UGC Formats, Lock the Audio Master and Frame Rate Before Generating, Lesson: Long-form Assembly and Sound, Four-Role Shot Taxonomy (hero, connective, performance insert, cutaway), Ongea Pesa Pinterest Reference Seed List (+5 more)

### Community 38 - "Typed Corpus Graph Builder"
Cohesion: 0.28
Nodes (9): build(), Graph, main(), _norm_model(), _norm_pack(), Any, Typed knowledge graph over the ComfyUI corpus. Generic text graphing (the…, Canonical key for a model file so 'flux-2-klein-9b-fp8.safetensors' and the… (+1 more)

### Community 39 - "Course Build And Download Tools"
Cohesion: 0.23
Nodes (10): digest(), download(), SafeRedirect, build(), load_lessons(), main(), parse_frontmatter(), Path (+2 more)

### Community 40 - "Grammar Study Module"
Cohesion: 0.28
Nodes (12): _caption_shape(), _captions(), derive(), Grammar, _load(), main(), Any, Path (+4 more)

### Community 41 - "Studio UI Workspace Config"
Cohesion: 0.15
Nodes (12): name, private, scripts, build:app, build:lib, dev:app, install:all, version (+4 more)

### Community 42 - "Ongea Pesa Claim-Safe Styles"
Cohesion: 0.27
Nodes (12): Ongea Pesa Accessibility Story Grammar, Agency and Competence, Never Helplessness, COMPOSITE_ONLY Logo Policy, Negative: no telecom/bank branding, no real till numbers, Reserve Copy Zone / 4.5:1 Contrast, text_policy: NONE — all copy composited in code, Ongea Pesa Data Magazine Graphic Grammar, Ongea Pesa Kenyan Meme Original Grammar (+4 more)

### Community 43 - "Graph Query And Provenance"
Cohesion: 0.20
Nodes (12): vision/analyze.py offline reference analysis, Evidence of a claim, not proof it works, graph_query.py (deps / dependents / evidence), Reference harvesters (ig/pin/yt), Node packs have two ids (cnr_id / aux_id), Offline measurement enforces a brand, library/graph_build.py, comfy-core node pack (+4 more)

### Community 44 - "Content Planner"
Cohesion: 0.29
Nodes (11): Brief, build(), load_grammar(), main(), Any, Path, _ratio_for(), Content plan — briefs a generator can actually execute. Takes a brand, its… (+3 more)

### Community 45 - "Song To Treatment Builder"
Cohesion: 0.35
Nodes (11): audio_duration(), audio_energy(), build(), main(), Any, Path, Song -> treatment -> shot list, with a generation route per shot. Implements…, Per-section loudness, used to decide which stage ranges carry hero shots. Uses… (+3 more)

### Community 46 - "EPALLE Cover Art Motifs"
Cohesion: 0.31
Nodes (11): Centred Frontal Symmetry with Single Seated Anchor, Suspended Falling Petals, Floral Head Substitution Motif (bouquet replacing the face), COVER ART - 'Flowers Falling' Single Cover, Parental Advisory Badge, Lower-Left Corner, Seated Groom in Ivory Suit, Hands Clasped, Single Long-Stem Red Rose Held Between the Knees, Petal-Strewn Floor as Foreground Texture Field (+3 more)

### Community 47 - "Editorial Experimental Styles"
Cohesion: 0.25
Nodes (11): Style: crimson_monolith, Mode: editorial_experimental, Ongea Pesa Style Index (24 grammars), TUDOR.AI Poster-Prompt Method, Style: mythology_red_editorial, Style: retro_relic_print, Style: swiss_interleaved_type, AI-assisted Imagery Disclosure Field (+3 more)

### Community 48 - "Secrets And Memory Deployment"
Cohesion: 0.18
Nodes (11): Leaked Credential Rotation Step, Memory Layer Deployment Guide, Bitemporal Facts Model, Graphiti MCP Server (127.0.0.1:8010), Graphiti + Neo4j Projection, _scrub() Secret-Shaped Key Guard, packages/memory/store.py (SQLite bitemporal store), Windows DPAPI Secret Storage (+3 more)

### Community 49 - "Research Library And Watcher"
Cohesion: 0.29
Nodes (7): Lesson 05-02 Archive, Search and Daily Source Watch, A Documented Watcher Is Not Automation, Index Is Derived, Rebuild Often, Library SQLite FTS Index, EPALLE Creative Studio Library, Report Only Changes, Daily Source Watcher

### Community 50 - "EPALLE Mirror And Rival Imagery"
Cohesion: 0.27
Nodes (10): Turned-Away Bride and Dark-Suited Rival in Mid-Ground, Oval Mirror Reflection Revealing the Groom's Own Back, Three-Figure Background Triangle (bride, mirror-self, rival), Veiled Bride in Full Ivory Gown, Seen from Behind, Corridor Walk Toward a Blown-Out Window of Light, Gold-Accented Keyword Highlighting ('MYSELF', 'ME'), Mirror Confrontation - Face Meets Its Own Reflection, Four-Beat Narrative Sequence (rejection, search, recognition, cover) (+2 more)

### Community 51 - "Scale-To-Zero And Send Safeguards"
Cohesion: 0.20
Nodes (9): Dataset Workflow V1, EPALLE Studio (Next.js), Report Retrieved vs Expected Counts, Shot Acceptance Criteria (identity drift), RunPod Verification Summary, matrix-power-nodes (compiler-generated, MIT), Semantic Retry Guard Against Double Billing, epalle-studio-api Scale-to-Zero Endpoint (+1 more)

### Community 52 - "Contract Pricing"
Cohesion: 0.27
Nodes (9): gpt_image_2(), nano_banana_2(), nano_banana_pro(), Quote, Real provider pricing, transcribed from a dated route contract. Source:…, google/nano-banana-pro/edit — base $0.14, 4k multiplies by 12/7., google/nano-banana-2/edit — 0.5k is a flat $0.045; searches add $0.014 each., openai/gpt-image-2/edit — a quality x resolution table, plus $0.012 per extra… (+1 more)

### Community 53 - "Graph Query CLI"
Cohesion: 0.47
Nodes (9): dependents(), deps(), evidence(), _find(), load(), main(), Any, Query the corpus graph. The two questions the plan set as the Phase 3 gate:… (+1 more)

### Community 54 - "Crushed Blacks Drift Checks"
Cohesion: 0.36
Nodes (9): ASALI Stage 02 — Labour Grammar, EPALLE Shared Grammar Preamble (fashion film register), Negative: no pure black shadow without detail, Crushed Blacks Drift in Shipped Cover Art, palette.measured vs palette.as_shipped, packages/vision/analyze.py, EPALLE Cover Art Square Grammar, Measure, Don't Assume (palette provenance) (+1 more)

### Community 55 - "EPALLE Visual Language Violations"
Cohesion: 0.31
Nodes (9): Composed Stillness / Fashion-Film Restraint, Crushed Pure-Black Surround (detail-free frame edges), Oxblood / Ivory / Dust-Gold Three-Note Palette, Symmetrical Candelabra Flanking the Aisle, Heavy Corner Vignette Falloff to Zero Detail, Shadow Detail Loss - Violation of 'Never Pure Black', Single-Source Chiaroscuro Staging, EPALLE Stated Visual Language (charcoal / ivory / dust gold, never pure black) (+1 more)

### Community 56 - "A-Z Setup Guide"
Cohesion: 0.25
Nodes (9): Postiz API Rate Limit (90 posts/hour), MAIN_URL / NEXT_PUBLIC_BACKEND_URL Misconfiguration Pitfall, Postiz Self-Host Stack (Caddy + Postgres + Redis), flux-2-klein-9b / flux2-vae / qwen_3_8b model set, A-Z Setup Guide, Instagram Professional + Facebook Page Requirement, OpenWA v4.76.0 WhatsApp Status Publishing, RunPod Pod Provisioning (volume 7y7jyghmua) (+1 more)

### Community 57 - "SageAttention A100 Install"
Cohesion: 0.22
Nodes (8): CUDA_HOME, EXT_PARALLEL, MAX_JOBS, NVCC_APPEND_FLAGS, PATH, PIP_CONSTRAINT, install_sage_a100.sh script, TORCH_CUDA_ARCH_LIST

### Community 58 - "Daily Source Watcher"
Cohesion: 0.36
Nodes (8): download(), have_ytdlp(), known_ids(), list_remote(), main(), Everything already archived: the completion list plus what is on disk., Enumerate a source without downloading. Flat playlist keeps this cheap., reindex()

### Community 59 - "Film Poster Type Grammar"
Cohesion: 0.38
Nodes (7): Film-Poster Grammar (title stack over a still, logline, tagline footer), Letterspaced Small-Caps Logline ('a man attends the wedding-funeral...'), Distressed Ivory Serif Display Title Lockup, Full-Bleed Edge-to-Edge Title Word Mark, Dead-Black Negative Space Reserved for Type, Four-Up Vertical Panel Grid (9:16 stories laid on one sheet), Top-and-Bottom Caption Bands Over Empty Black Space

### Community 60 - "Postiz VPS Deployment"
Cohesion: 0.33
Nodes (7): Current Blockers (credentials, RunPod serverless, Klein KV licence, Postiz), Postiz on a Hostinger VPS, Backend URL Must Be Origin + /api, Instagram Publishing Prerequisites (Professional + Page + Meta App), packages/publish/postiz.py, Registration Disabled by Default, FLUX.2 Klein 9B (FP8 accepted, KV licence-gated)

### Community 61 - "Jobs Page UI"
Cohesion: 0.29
Nodes (4): card, muted, shell, STATUS_COLOR

### Community 62 - "Composite The Logo Principle"
Cohesion: 0.40
Nodes (6): Composite the logo, never regenerate it, Deterministic compositor, Models make pictures, code makes brands, Reserve copy zone / 4.5:1 contrast, Composite the Logo, Never Regenerate It, Blank Neutral-Grey Screen for UI Compositing

### Community 63 - "Grammar Not Images Principle"
Cohesion: 0.40
Nodes (6): packages/strategy/study.py, Twelve-Sample Floor for Grammar Derivation, Take the Grammar, Never the Images, Six-Posts-Per-Grammar Analytics Floor, strategy package, vision package

### Community 64 - "Custom Node Pack And Licences"
Cohesion: 0.33
Nodes (5): packages/compositor, CR Prompt List Node, epalle-nodes Custom Node Pack, work/h3 MiniMax H3 Nodes (GPL-3.0), Licence Conflict (GPL-3.0 h3 / MIT / unlicensed Icekiub)

### Community 65 - "Model Auditor"
Cohesion: 0.47
Nodes (4): extract(), folder_for(), main(), Return (node_type, model_filename) pairs from a UI-format or API-format graph.

### Community 66 - "SageAttention Generic Install"
Cohesion: 0.33
Nodes (5): EXT_PARALLEL, MAX_JOBS, NVCC_APPEND_FLAGS, install-sageattention.sh script, TORCH_CUDA_ARCH_LIST

### Community 67 - "Library Page UI"
Cohesion: 0.33
Nodes (3): card, muted, shell

### Community 68 - "ASALI Desire And Sweetness"
Cohesion: 0.50
Nodes (5): Mode: asali_arc, Reserve Copy Zone / 4.5:1 Contrast Rule, Style: asali_01_desire, Style: asali_06_sweetness, brandkit package

### Community 69 - "Standing Rules And Text Policy"
Cohesion: 0.50
Nodes (5): Text Policy NONE - copy composited in code, Logo Policy COMPOSITE_ONLY, RunPod Serverless Endpoint ugtmfoidpnh8pd (unproven), compositor package, Standing Rules (queued is not success, dry-run by default, composite the logo, humans approve)

### Community 70 - "Faceless Protagonist Imagery"
Cohesion: 0.40
Nodes (5): Clutched Red Bouquet at Chest Height, Slide 1 - Four-Panel Narrative Carousel Sheet, Red-Accented Keyword Highlighting in Caption Copy, Rose-Studded Cloth Blindfold Over the Eyes, Faceless Protagonist Device (identity obscured by flowers or cloth)

### Community 71 - "Core Thesis Models Versus Code"
Cohesion: 0.40
Nodes (5): Models Make Pictures, Code Makes Brands, Style Grammar (fix the system, vary the subject), TUDOR Poster Prompt Method, brandkit package, Content Studio Pipeline

### Community 72 - "Workflow Importer"
Cohesion: 0.60
Nodes (4): analyse(), main(), Path, strings()

### Community 73 - "Studio Home Page"
Cohesion: 0.40
Nodes (3): nodeData, sources, workflows

### Community 74 - "Workflow Listing Page"
Cohesion: 0.60
Nodes (3): getWorkflowDefs(), WorkflowList(), WorkflowListingClient()

### Community 75 - "Planned Model Downloader"
Cohesion: 0.83
Nodes (3): gpu_capability(), main(), needs_blackwell()

### Community 76 - "Sage-Free Retry Tool"
Cohesion: 0.83
Nodes (3): main(), replace_links(), request()

### Community 77 - "Workflow Runner"
Cohesion: 0.83
Nodes (3): get(), main(), post()

### Community 78 - "DPAPI Secret Setter"
Cohesion: 0.67
Nodes (3): Blob, main(), protect()

### Community 79 - "library/route.js"
Cohesion: 0.83
Nodes (3): GET(), listWorkflows(), openDb()

### Community 80 - "compilerOptions"
Cohesion: 0.50
Nodes (3): compilerOptions, baseUrl, paths

### Community 81 - "presets"
Cohesion: 0.50
Nodes (3): presets, @babel/preset-env, @babel/preset-react

### Community 82 - "Wedding-Funeral Interior Set (aisle,"
Cohesion: 1.00
Nodes (3): Candle Practicals as Warm Point Light Sources, Mourning-Opulence Mood (grief staged as ceremony), Wedding-Funeral Interior Set (aisle, chairs, candles, floral banks)

### Community 83 - "packages/orchestrator"
Cohesion: 0.67
Nodes (3): Hermes Agent (NousResearch), packages/orchestrator, Paperclip (paperclipai)

## Ambiguous Edges - Review These
- `ComfyUI-H3-Motion-Context node pack` → `Comfy-Org MiniMax H3`  [AMBIGUOUS]
  packages/library/manifests/hugging-face-pages.md · relation: conceptually_related_to
- `Leaked Credential Rotation Step` → `studio-ui Next.js Client README`  [AMBIGUOUS]
  docs/SETUP.md · relation: conceptually_related_to
- `Crushed Pure-Black Surround (detail-free frame edges)` → `Composed Stillness / Fashion-Film Restraint`  [AMBIGUOUS]
  brands/epalle/assets/cover/COVER ART.png · relation: conceptually_related_to
- `Film-Poster Grammar (title stack over a still, logline, tagline footer)` → `Dead-Black Negative Space Reserved for Type`  [AMBIGUOUS]
  brands/epalle/assets/cover/slide 1.png · relation: conceptually_related_to
- `Glowing Cyan Globe Mark with Green Money Swirl` → `Written Spec Claim: Emerald #30E0A8 Primary`  [AMBIGUOUS]
  brands/ongea-pesa/assets/logo/ongea-pesa-lockup-transparent.png · relation: conceptually_related_to
- `Near-White Ground with Deep Emerald Green Accent` → `Written Spec Claim: Emerald #30E0A8 Primary`  [AMBIGUOUS]
  brands/ongea-pesa/assets/reference/ongeapesa.jpeg · relation: semantically_similar_to

## Knowledge Gaps
- **161 isolated node(s):** `install-sageattention.sh script`, `TORCH_CUDA_ARCH_LIST`, `MAX_JOBS`, `EXT_PARALLEL`, `NVCC_APPEND_FLAGS` (+156 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `ComfyUI-H3-Motion-Context node pack` and `Comfy-Org MiniMax H3`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Leaked Credential Rotation Step` and `studio-ui Next.js Client README`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Crushed Pure-Black Surround (detail-free frame edges)` and `Composed Stillness / Fashion-Film Restraint`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Film-Poster Grammar (title stack over a still, logline, tagline footer)` and `Dead-Black Negative Space Reserved for Type`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Glowing Cyan Globe Mark with Green Money Swirl` and `Written Spec Claim: Emerald #30E0A8 Primary`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Near-White Ground with Deep Emerald Green Accent` and `Written Spec Claim: Emerald #30E0A8 Primary`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `load_brand()` connect `End-to-End Test Suite` to `Content Planner`, `Song To Treatment Builder`, `Deterministic Compositor`, `Vision Reference Analysis`, `Image Router`, `Brand Kit Loader`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._