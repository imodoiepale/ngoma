# Roadmap: from built to live and learning

Everything below is ordered by dependency, not by importance. A step cannot start until the
gate before it is met. Most steps are yours, because the code is done and what remains is
accounts, licences, money, decisions and time.

Owner key: **YOU** = needs a login, payment, decision or account. **ME** = code or config.

Commands are written for plain `python`; `uv` is not on PATH on this machine. Set
`PYTHONIOENCODING=utf-8` in the shell first.

---

## Stage 0: Security, day 1, gates everything

Three live credentials sit in plaintext in the old Codex tree. They were never copied into
this repo, but they are still valid and still on disk.

| # | Step | Owner | Command / action |
|---|---|---|---|
| 0.1 | Revoke the Whop API key | YOU | Whop dashboard, API keys, revoke `apik_…` |
| 0.2 | Revoke the RunPod API key | YOU | RunPod console, Settings, API Keys, revoke `rpa_…` |
| 0.3 | Replace the SSH keypair | YOU | `ssh-keygen -t ed25519 -f ~/.ssh/epalle_runpod` then put the new `.pub` on the pod |
| 0.4 | Delete the old plaintext files | YOU | `outputs/course/.env.whop`, `outputs/studio-ui/client/.env.local`, both `epalle_runpod_ed25519` |
| 0.5 | Store new secrets in DPAPI | YOU | `python infra/runpod/set_secret.py runpod` |
| 0.6 | Confirm the repo is clean | YOU | `python studio.py check` prints `no secrets tracked` |

**Gate:** the three old credentials fail when used. Test one; do not assume.

---

## Stage 1: First real post, days 2 to 4, no GPU needed

The fastest path to something live uses hosted image models, which need only an API key.

| # | Step | Owner | Command / action |
|---|---|---|---|
| 1.1 | Get an OpenRouter key and add credit | YOU | openrouter.ai/keys; $10 covers roughly 40 flagship 4K stills |
| 1.2 | Store it | YOU | `python infra/runpod/set_secret.py openrouter` |
| 1.3 | Plan the month, costs nothing | ME | `python packages/image-router/router.py --plan-all` |
| 1.4 | Generate one single-still post | YOU | `python packages/image-router/router.py --idea 6 --backend hosted --live` |
| 1.5 | Composite the brand onto it | ME | `python packages/compositor/compositor.py --base out/<file>.png --idea 6 --ratio 4:5` |
| 1.6 | Look at it: spelling, logo, contrast, palette | YOU | open `out/ongea-pesa-idea06_4x5.png` |

**Gate:** one finished, on-brand 3072 by 3840 master you would actually post.

> Pick a `single` idea for 1.4, not a carousel or reel. Carousels and reels route to ComfyUI
> because they need identity preserved across slides, which hosted endpoints cannot do
> reproducibly, so they wait for Stage 3.

---

## Stage 2: Publishing infrastructure, days 3 to 10, the real blocker

This is the stage everything else waits on. Start 2.1 on day 1: Meta's review is the
longest lead time in the whole roadmap and it runs in parallel with everything else.

### 2A. Instagram Business, YOU, start immediately

| # | Step | Detail |
|---|---|---|
| 2.1 | Convert the Ongea Pesa IG account to Professional | IG, Settings, Account type, Business |
| 2.2 | Link it to a Facebook Page | Create a Page for Ongea Pesa if none exists; Meta Business Suite, Settings, Accounts |
| 2.3 | Create a Meta app | developers.facebook.com, Create app, Business |
| 2.4 | Request permissions | `instagram_content_publish`, `instagram_basic`, `pages_show_list`, `instagram_manage_insights` |
| 2.5 | Take the app live | Development mode cannot publish to real accounts. Needs a privacy policy URL |

> Prove it on a throwaway Business account first. A mistake while wiring publishing should
> not land on the real brand's feed.

### 2B. Postiz on the Hostinger VPS

| # | Step | Owner | Command / action |
|---|---|---|---|
| 2.6 | Size check: 2 GB RAM minimum, 4 GB comfortable | YOU | add 2 GB swap on a small plan; see `infra/postiz/README.md` |
| 2.7 | Point DNS before first boot | YOU | `postiz.yourdomain.com  A  <VPS_IP>`; Caddy needs it to get a cert |
| 2.8 | Install Docker | YOU | `sudo apt install -y docker.io docker-compose-plugin` |
| 2.9 | Configure | YOU | `cd infra/postiz && cp .env.example .env && chmod 600 .env` |
| 2.10 | First boot | YOU | `docker compose up -d && docker compose logs -f postiz` |
| 2.11 | Create your account, then re-disable registration | YOU | flip `DISABLE_REGISTRATION` to `false`, register, flip it back |
| 2.12 | Firewall | YOU | `sudo ufw allow 22,80,443/tcp && sudo ufw enable` |
| 2.13 | Connect Instagram in the Postiz UI | YOU | needs 2.1 to 2.5 done |
| 2.14 | Get the API key and channel id | YOU | Postiz, Settings, Public API; then `python packages/publish/postiz.py channels` |

**Gate:** `postiz.py channels` lists the Instagram integration with an id.

### 2C. First draft through the pipeline

| # | Step | Owner | Command / action |
|---|---|---|---|
| 2.15 | Dry run the payload | ME | `python packages/publish/postiz.py send --plan <plan.json> --limit 1` |
| 2.16 | Send as draft | YOU | add `--live --integration-id <id>`; type defaults to `draft` |
| 2.17 | Review it inside Postiz, then schedule from there | YOU | never `--type now` for the first one |

**Gate:** one post live on the test account, published through the pipeline end to end.

---

## Stage 3: The open-source GPU path, days 5 to 14

Carousels, reels, character consistency, batches and video all need ComfyUI.

| # | Step | Owner | Command / action |
|---|---|---|---|
| 3.1 | Accept the FLUX.2 Klein 9B KV licence | YOU | its HuggingFace model page. Unblocks `carousel_pose`, which the batch pattern and four persona ideas depend on |
| 3.2 | Raise the engine budget above 0 | YOU | `brands/_presets/engine.yaml` `budget_usd`; see `docs/BLOCKERS.md` item 14 |
| 3.3 | Rotate-and-restore RunPod access | YOU | uses the new key from Stage 0 |
| 3.4 | Provision a pod on the existing volume | ME | `python infra/runpod/provision_pod.py`; volume `7y7jyghmua` already holds the models |
| 3.5 | Find what each workflow is missing | ME | `python infra/runpod/audit_models.py` |
| 3.6 | Download the gap, on the pod | ME | `python infra/runpod/download_planned.py` |
| 3.7 | Probe and validate | ME | `python packages/comfy-client/client.py validate --all --backend pod` |
| 3.8 | Every engine step has a port map | ME | `python packages/engine/cli.py ports-check` |
| 3.9 | Prove serverless with the trivial graph | ME | `python packages/comfy-client/client.py smoke --backend serverless --live` |
| 3.10 | Generate the first real carousel | YOU | `client.py run workflows/icekiub/Carousel_Pose_changer.json --backend pod --live` |

**Gate:** `validate` reports `OK`, not `UNVERIFIED`, and the smoke test returns outputs.

> Serverless has never completed a generation; the only recorded result is `IN_QUEUE`.
> Queued is not success. Do not schedule anything that depends on serverless until 3.9
> genuinely returns an image.
>
> SageAttention compiles for one GPU architecture into a venv on a shared volume. A pod on a
> different card imports it fine and fails at runtime. Keep the same card family, or re-run
> `infra/runpod/install_sage_a100.sh`.

---

## Stage 4: Director, the general creative studio, in progress

The design (`docs/superpowers/specs/2026-09-20-general-creative-studio-design.md`) turns the
two-brand tool into a studio for any workspace. Five workstreams run in parallel with
explicit file ownership; each is done when its acceptance commands pass.

| # | Workstream | Owner | Done when |
|---|---|---|---|
| 4.1 | W1 Premium UI: home, explore, `/w/<key>`, batches, jobs; capability cards with Ready / Needs setup / Gap badges; no EPALLE literal outside workspace data | ME | `npm run build --prefix packages/studio-ui` and `npm run lint --prefix packages/studio-ui` pass; the pages render |
| 4.2 | W2 Describe to workflow: `cli.py describe`, `/api/describe`, the seven intent gaps, `extend()`, the `uv`-free spawn helper | ME | the spec's example sentence yields `[reference-images, character-swap@each, carousel@each, compositor, export]` with `slides == 10` |
| 4.3 | W3 Batch runtime: per-item loop, seeds, `partial`, `posts/<group>/` export, `max_items`, cost with items, the run-time rights gate, three port maps, the batch template | ME | a dry run of the template writes `items[]` of length 3 against `brands/epalle/references/red-dress` |
| 4.4 | W4 The 50 ideas: close the gap groups G1 to G9 in bulk or state the exact blocker per idea | ME | `workflow_author.py --all-ideas && --check`, `workflow_catalog.py --check`, `cli.py ports-check` pass, with a before-and-after gap table |
| 4.5 | W5 Workspaces and docs: `workspace.py new / list / check`, `brands/_kit/`, docs and skills speak of workspaces | ME | `python packages/strategy/workspace.py new demo-brand --name "Demo Brand" --dry-run` prints the plan; `python -m pytest -q tests/test_workspace.py tests/test_docs_commands.py` is green |
| 4.6 | ~~Confirm the product name, and that "Wavy AI" means Weavy~~ done 2026-09-20: **Director**, and **Weavy.ai** | YOU | `docs/BLOCKERS.md` item 16 |
| 4.7 | Decide credits versus per-deliverable pricing | YOU | `docs/BLOCKERS.md` item 18 |
| 4.8 | Confirm the real-person face swap policy | YOU | `docs/BLOCKERS.md` item 19 |
| 4.9 | Decide whether `adult: true` nodes appear in Explore behind the 18+ gate or stay hidden | YOU | `docs/BLOCKERS.md` item 20 |

**Gate:** the integration gate after all five merge: `python -m pytest -q`,
`python packages/strategy/workflow_author.py --check`, `python packages/engine/cli.py ports-check`,
`python studio.py check`, `npm run build --prefix packages/studio-ui`, `graphify update .`.

Status at 2026-09-20: W5 delivered (this document, `workspace.py`, `brands/_kit/`). The
`@each` contract and the `character-swap` alias are in place and tested. W1 to W4 are in
progress on their own files.

---

## Stage 5: Volume, weeks 2 to 8, the gate you cannot rush

The learning loop is built and tested. It will not say anything trustworthy until there is
enough data, and it is right to refuse: at 3 posts per grammar it once reported a
deliberately under-performing grammar as +28%.

| # | Step | Owner | Detail |
|---|---|---|---|
| 5.1 | Narrow the rotation to 4 to 6 grammars | YOU + ME | the analysis needs 6 or more posts per grammar; 30 posts across 13 grammars teaches nothing |
| 5.2 | Post consistently, daily or every other day | YOU | through Postiz drafts, approved by you |
| 5.3 | Keep adjacent posts to one changed factor | ME | `plan.py` already enforces this; do not override it by hand |
| 5.4 | Clear the approval queue weekly | YOU | `python packages/orchestrator/control.py queue` |
| 5.5 | Check power weekly | ME | `learn.py` prints how many more posts it needs before claims are possible |

**Gate:** `learn.py` reports `can_support_claims` for at least two grammars.

**Honest timeline:** 6 grammars times 6 posts is 36 posts. At one a day, 5 to 6 weeks.

---

## Stage 6: The loop closes, weeks 6 to 10

| # | Step | Owner | Command / action |
|---|---|---|---|
| 6.1 | Store the Instagram insights token | YOU | `python infra/runpod/set_secret.py ig-token`, then `ig-user` |
| 6.2 | Pull real metrics | ME | `python packages/analytics/collect.py instagram --plan <plan.json>` |
| 6.3 | Derive learnings into memory | ME | `python packages/analytics/learn.py --data <file> --write` |
| 6.4 | Read what memory believes | YOU | `python packages/memory/store.py believed` |
| 6.5 | Re-plan using what was learned | ME | `plan.py` picks up the new facts |
| 6.6 | Repeat 6.2 to 6.5 every 2 weeks | ME | each run supersedes the previous facts rather than duplicating |

**Gate:** a learning derived from real data changes the next plan.

> Expect the skill curator to say NOT ELIGIBLE for months. It needs 3 repeated wins across 3
> or more days and 2 contexts. That is the gate working, not failing: a learning loop's real
> failure mode is confidently learning noise.

---

## Stage 7: WhatsApp Status, optional, your risk to accept

WhatsApp supports Status through no API, including the official Business Platform. OpenWA is
unofficial and can get a number restricted.

| # | Step | Owner | Detail |
|---|---|---|---|
| 7.1 | Decide whether it is worth the risk | YOU | if WhatsApp is business-critical, it is not |
| 7.2 | Get a dedicated number you can afford to lose | YOU | never your personal one, never the customer line |
| 7.3 | Deploy OpenWA bound to localhost | YOU | `infra/openwa/`; an exposed OpenWA is a hijacked account |
| 7.4 | Pair by QR | YOU | `docker compose logs -f openwa` |
| 7.5 | Send with confirmation | YOU | `whatsapp.py send ... --live --i-mean-it`; capped at 8 a day |

---

## Stage 8: EPALLE music, parallel track, any time after Stage 3

Two decisions block this, and both are yours.

| # | Step | Owner | Detail |
|---|---|---|---|
| 8.1 | Decide on the covers | YOU | they crush 30 to 47% to pure black, which EPALLE's own visual language forbids. Regrade the art, or amend the rule |
| 8.2 | Lock one frame rate | YOU | the live footage is 29.97fps; treatments default to 24. Hero footage: generate at 30. B-roll: conform to 24 once, first |
| 8.3 | Build the Ancestral Pulse treatment | ME | `treatment.py --audio "Ancestral Pulse.wav" --fps <chosen>`; it has a master on disk, ASALI does not |
| 8.4 | Generate hero shots first | ME | `still_push` and `performance` routes |
| 8.5 | Grade once, over everything | YOU | lesson 04-01: cohesion is only visible as a contact sheet |

---

## Stage 9: Scale the organisation, optional, when more than one person is involved

| # | Step | Owner | Detail |
|---|---|---|---|
| 9.1 | Install Hermes | YOU | `iex (irm https://hermes-agent.nousresearch.com/install.ps1)`, not `pip install` |
| 9.2 | Merge its config | YOU | `python packages/orchestrator/hermes.py config` prints it; merge, do not overwrite |
| 9.3 | Sync skills into Hermes | ME | `hermes.py sync-skills --live` |
| 9.4 | Deploy Paperclip | YOU | `npx paperclipai onboard --yes`; the npm package is `paperclipai`, not `paperclip` |
| 9.5 | Mirror the control plane | ME | `paperclip.py mirror --live`; one-way, `control.py` stays authoritative |

> Something on your machine already owns port 3100, Paperclip's default. Set `PAPERCLIP_URL`
> to another port or find what is there first.

---

## What you owe, in one list

1. Rotate the three credentials, day 1
2. Start Meta Business verification, day 1, longest lead time
3. OpenRouter key and credit
4. Accept the Klein KV licence
5. Raise `budget_usd` above 0 before any live GPU stage
6. ~~Confirm the product name and that "Wavy AI" means Weavy~~ — done: **Director**, and Weavy.ai (BLOCKERS 16)
7. Decide credits versus per-deliverable pricing
8. Confirm the real-person face swap policy: never without a written release
9. Decide whether the `adult: true` nodes are offered behind the 18+ gate or hidden
10. Enable the OpenCLI browser extension (for Instagram reference harvesting)
11. Decide EPALLE's cover grade and frame rate
12. Working URLs for AiorBust and Hearmeman, if you still want them
13. Your Pinterest script, if it does something `pin_harvest.py` doesn't
14. Five to six weeks of consistent posting

Everything else is built, tested (`python -m pytest -q`; the count moves while the Stage 4
workstreams land, and `docs/BLOCKERS.md` records the last clean run), and waiting.
