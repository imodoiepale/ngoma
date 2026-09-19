# "alexya-batch-api" skill: what we take, what we leave

Source file: `source/alexya-batch.skill`, a 47 KB ZIP (magic bytes `PK`) downloaded
2026-09-19, kept byte for byte (SHA-256 `1CBC04B9...631697`). Study material only; see
`docs/LICENSING.md`. Hand-written notes; `docs/creators/CREATOR-INTEL.md` is generated and
does not cover this file.

## What it is

A Claude agent skill (Anthropic `SKILL.md` format with `name:` / `description:` frontmatter,
`version: 1.2.0`), written in French, for a hosted image service called Alexya
(`https://alexya.ai/api/v1`). No author is named anywhere in the archive, so the folder slug
is the product name. Contents:

| File | Size | What it is |
| --- | --- | --- |
| `alexya-batch-api/SKILL.md` | 9.7 KB | the skill: rules, API cheat sheet, execution discipline, onboarding and batch flows, error table |
| `alexya-batch-api/references/alexya_client.py` | 19.8 KB | Python client (`requests`): balance, avatar upload via presigned PUT, async generate plus polling, 5-way thread pool, checkpoint file, `fcntl` lockfile |
| `alexya-batch-api/references/identity-template.md` | 2.1 KB | a per-persona markdown template: API key, avatar CDN URL, archetype, approved places, outfits, moments, batch history |
| `alexya-batch-api/references/photo-system.md` | 14.2 KB | the prompt kit: two shot types, structures, mandatory "amateur iPhone" words, banned "pro" words, emotion bank, imperfection bank, light bank with quotas, four worked prompts, batch assembly procedure |

What the skill does: an "AI influencer" photo-pack generator. The agent asks for an API key
and one avatar photo, uploads the photo once to Alexya's CDN, proposes places, outfits and
moments for the persona, writes N prompts (exactly half hand-held selfies, half mirror
selfies, all "amateur iPhone"), submits them five at a time, downloads the results and
presents them. Every prompt ends with the line "Use the reference image to accurately
reproduce her facial features, body shape, proportions, and curves." Pricing is 55 credits
per high-quality image and 31 per fast one; the skill makes the agent confirm the cost
before running.

Assumptions: Claude with a bash tool on a Linux box (`nohup`, `pgrep`, `fcntl`, paths under
`/mnt/user-data/outputs` and `/home/claude`); Python 3 with `requests`; an Alexya account
with an `aph_live_` key holding `image:generate` and `account:read` scopes; a sibling
skill `alexya-amateur-photos` (not in the archive) for prompt-only use.

## Safety review of the script

`alexya_client.py` was read in full and was not run or installed.

- Network: it calls only its own `base_url` (default `https://alexya.ai`), PUTs the avatar to
  whatever `upload_url` the presign endpoint returns, and GETs the finished image from
  whatever `output_url` the generation record returns. No other hosts, no telemetry, no
  remote code download or `exec`.
- Secrets: the API key is sent as a Bearer header. The skill and `identity-template.md`
  suggest saving the key in plain text inside a markdown file that is then added to the
  Claude project. That is the one thing to flag: a live key in a doc that travels with the
  project. The template itself warns "never push to GitHub".
- Filesystem: writes only under the caller's `output_dir` and `checkpoint_path`, plus a
  `.batch.lock` file it deletes at the end.
- Portability: `import fcntl` fails on Windows; the lockfile design does not run here at
  all.
- Cost control is real: exponential backoff on 429 and 5xx, a lockfile so a second run on
  the same output folder raises before spending, a checkpoint so a restart skips finished
  files, and a documented incident (a wrapper printed an error while the process kept
  running, the agent relaunched, four images were billed twice) that motivates the "check
  process, checkpoint and output folder before relaunching" rule.

## Licence

None stated in any file. No copyright line, no LICENSE, no terms in the frontmatter. Treated
as internal study material; nothing from it is redistributed.

## People and likenesses

No real person is named. The whole method is nonetheless a likeness pipeline: it uploads one
photo of a face and body and instructs the model to reproduce that face and body in every
image. The archive does not say whose photo. The emotion bank ("seductive lip bite",
"lingering gaze") and the body-reproduction tail line place it in the OFM-style persona
market that `docs/proposals/x01-fictional-18-persona-subscription.md` describes as
compliance-gated.

## Repo rules that override it

- **No person's name or likeness in any prompt.** The tail line "reproduce her facial
  features, body shape, proportions, and curves" from an uploaded photo is exactly what the
  rule forbids unless the character is owned or fictional with the release on file. Our
  version binds identity by role to a character sheet the studio made
  (`shot-prompt-architect` rule 1: "the woman from the character sheet"), never to a photo
  of a person. Note that `packages/engine/presets.py` `FORBIDDEN` does not catch this
  sentence (it matches names and "look-alike"/"face of" phrases), so the skill has to
  refuse it by procedure.
- **Hosted image models are not adapters.** Alexya is a hosted generator behind an API. Our
  stills route is ComfyUI on the pod (`packages/comfy-client/client.py`, workflows in
  `workflows/manifest.json`), and the batch seam is `CR Prompt List` injection or the
  `PromptListFromFolder` node in `workflows/icekiub/nodes/icynodes/`. The client is not
  ported and no `alexya` backend is added.
- **Secrets live in the vault, never in a doc.** `packages/common/vault.py` and `.env`
  (gitignored). The identity template's "API key in the markdown" pattern is not adopted.
- **Dry-run by default, budget checked before work, queued is not success.** The skill's
  "confirm cost, wait for yes" and "never relaunch blind" rules already exist here as
  `client.py --live`, `control.py propose --estimate` and the standing rules in
  `content-studio`. We keep them and point at ours.
- **18+ persona work is gated.** Fictional adults only, disclosed, separate entity and
  accounts, never on Ongea Pesa or EPALLE infrastructure (X01 hard gates). The source skill
  has no such gate and generates whatever the user's persona file says.
- **Plain prose in docs**: the source is in French with emojis in the progress callback;
  our restatement is English, no emojis, no em dashes.

## What we take

The prompt kit and the batch discipline, restated in our words in
`.claude/skills/persona-photo-batch/SKILL.md`:

- **Phone-camera realism is a set of imperfections, not a quality setting.** Every prompt
  names the capture ("amateur phone selfie", "mirror selfie taken with a phone"), the
  rawness ("raw, unedited, spontaneous", "slightly imperfect framing", occasional grain,
  compression, slight over or under exposure) and one or two concrete flaws (hair strand
  across the lens, fingerprints on the mirror, clutter on the counter, a tilted frame,
  motion blur at the arm). Words that read as a professional shoot ("studio lighting",
  "DSLR", "editorial", "bokeh", "model pose", "fierce gaze") are struck.
- **Two shot types with fixed grammar.** Hand-held selfie: arm visible or cut at the bottom
  edge, shoulders or mid-body framing, angle variants. Mirror selfie: phone visible at chest
  or waist, the room in the reflection, full or mid-body. A fixed split across the batch
  (the source says 50/50; ours is a parameter with 50/50 default).
- **Variety is enforced with quotas, not hoped for.** At least eight distinct expressions for
  twenty or more images, five for ten to twenty; no two images with the same place, outfit
  and expression; no three consecutive images in the same light; no two consecutive mirror
  selfies in the same room; at most five in bright daylight and three in golden hour per
  twenty; at least two or three in "ugly" light (tungsten, fluorescent, direct flash),
  because ugly light is what reads as amateur.
- **Expression as behaviour**: the emotion bank maps a feeling to what the face does
  ("cheeks puffed, eyes wide and amused"), which is the same rule `shot-prompt-architect`
  applies to performance in video.
- **The persona file.** One markdown per character with approved places, outfits and
  moments and a batch history. Ours lives under `brands/<client>/references/<character>/`
  next to the character sheet, without any credential in it.
- **Batch execution discipline**: confirm the count and the cost before anything runs; run
  the batch as a single submission, not N separate runs; before re-running anything, look at
  the queue, the run manifest and the output folder; keep a per-file ledger so a resumed
  batch skips what is done; report count made, count failed, cost, and the failed prompts,
  nothing else.

## What we leave

- `alexya_client.py` and the Alexya API (hosted model, not our route; POSIX-only lock;
  credit pricing specific to one vendor).
- The onboarding flow that collects an API key and an avatar photo from the user.
- The tail line binding identity to an uploaded photo.
- The "iPhone 12/14" brand words in prompts; ours say "phone" so the look, not the product,
  is described.
- French, `tutoiement`, the emoji progress labels.

## What this changes in the tool

| Where | Change |
| --- | --- |
| `.claude/skills/persona-photo-batch/SKILL.md` | new skill: plan, write and run a batch of consistent phone-realism stills of one owned or fictional character on our route |
| `docs/LICENSING.md` | one row |
| `docs/creators/alexya/` | this file and the source archive |

Not changed, worth deciding later: an `amateur-phone` entry in `brands/_presets/directors.yaml`
(the ten `GRAMMAR_KEYS`, via the `style-block` skill) would let the Director Engine compose
the same realism into its angle prompts; and `client.py` has no `--image` flag, so the
reference image for `Carousel_Pose_changer` is set in the workflow JSON or on the studio
canvas, not from the command line.
