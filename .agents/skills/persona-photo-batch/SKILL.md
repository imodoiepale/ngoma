---
name: persona-photo-batch
description: Use when a client wants a batch of consistent stills of one owned or fictional character that read as phone photos rather than a shoot ("30 selfies of the persona", "a month of mirror selfies", "UGC-looking photos for the ad pack", "seed a dataset for the character", "the pack looks too polished", "every photo has the same light"), when planning the shot mix of such a pack, when writing the N prompts, or when running or resuming the batch on the pod. Plans the mix with hard variety quotas, writes phone-realism prompts with named imperfections and no person's likeness, drives the batch through CR Prompt List on our ComfyUI route with dry-run, budget gate and a resume ledger, and says what is a gap.
---

# Persona photo batch

Turns "N photos of this character" into a planned, varied, costed batch of stills that look
like they came off a phone, generated on our route, with a ledger that survives a restart.
Method restated from the "alexya-batch-api" skill (`docs/creators/alexya/NOTES.md`), with
its hosted API, its identity-from-a-photo binding and its credential handling removed.
Where that file and this one disagree, this one wins.

Sibling skills: `style-block` for a stylised look instead of phone realism;
`shot-prompt-architect` for the video prompts that follow; `content-studio` for the standing
rules every live run obeys.

## Repo rules, before anything else

1. **Owned or fictional characters only.** The character is a studio-made character sheet
   under `brands/<client>/references/<character>/` with `rights: owned` or `fictional`. A
   photo of a real person, a "based on" account, or a look-alike is a declared gap, not a
   batch. Never write "reproduce her facial features, body shape, proportions and curves
   from the reference image"; bind identity by role ("the woman from the character sheet")
   and let the workflow's reference ports carry the sheet. No person's name anywhere:
   `packages/engine/presets.py` `FORBIDDEN` catches names and "look-alike" phrases, run it
   over every prompt (step 5), and refuse by hand what it does not catch.
2. **Our route only.** Stills are ComfyUI workflows on the pod, driven by
   `packages/comfy-client/client.py`. Hosted image APIs are not adapters and their clients
   are not ported. The batch seam is the `CR Prompt List` node (`client.py` injects
   `--prompt` values into it) or the `PromptListFromFolder` node from
   `workflows/icekiub/nodes/icynodes/` (one `.txt` per prompt, the graph runs once per file).
3. **Dry-run by default, cost before count.** `client.py run` submits nothing without
   `--live`. The cost is confirmed with the person before `--live`, and recorded as a task
   with `control.py propose --estimate` so the budget check happens before work starts.
4. **Queued is not success.** Only a completed history with output files counts. A returned
   prompt id, an `IN_QUEUE`, a printed error from the wrapper: none of them says anything
   about whether the batch ran. Look before re-running (step 7).
5. **18+ persona work is gated** (idea X01): fictional adults only, disclosed, separate
   entity and accounts, never on Ongea Pesa or EPALLE infrastructure. The studio workflow
   carries `consent_required: true`; say so.
6. **Plain punctuation, English prompts, no phone brand names.** "Amateur phone selfie",
   not a product model.

## What to ask for, once

The character (folder name); the client; N; the shot-type split (default half hand-held
selfie, half mirror selfie; odd N rounds the extra one to hand-held); aspect ratio (default
9:16; the workflow decides what it accepts); the persona file's approved places, outfits and
moments, or the weights the person wants across them ("balanced", or "70% bedroom"). One
sharp question if something is unclear, never more than two. A person may ask for an extreme
mix (one room for all N); do it and vary every other axis harder.

## The persona file

`brands/<client>/references/<character>/persona.md`, next to the character sheet. Sections:
archetype and one contradiction; one unique detail; approved places (with two or three
concrete props each); approved outfits (each tied to a place or moment); approved moments;
a batch history table (date, batch id, N, workflow, cost, notes). **No credential of any
kind in it.** Keys live in the vault (`packages/common/vault.py`) or `.env`. Create it on
the first batch, append to it on every later one.

## Procedure

1. **Split the shot types**, then distribute places, outfits and moments by the weights.
2. **Assign light** per image from the bank below, under the quotas.
3. **Assign an expression** per image from the bank, under the variety minimum.
4. **Assign one or two imperfections** per image, matched to the shot type.
5. **Assemble each prompt** with the grammar below, then check the whole set against the
   ledger rules and the forbidden list, and run the name filter:
   `python -c "import sys; sys.path.insert(0,'packages/engine'); import presets; [print('FORBIDDEN:', p) for p in open('<prompts.txt>', encoding='utf-8').read().splitlines() if presets.FORBIDDEN.search(p)]"`
   Nothing printed means no name or look-alike phrase; it does not mean the prompt is
   clean, read it.
6. **Cost, validate, propose, run** (commands below).
7. **Report**: N made, N failed, real cost, the failed prompts, the output folder. Do not
   open the images in chat unless asked; give the folder.

## Prompt grammar

Each prompt has the same seven parts, in this order, and nothing else:

```
<capture>, <angle or pose>, <expression as behaviour>, <outfit>, <place with one or two props>, <light>. <one or two imperfections>. <rawness line>. <framing line>. The woman from the character sheet, same face, hair and build in every image.
```

Hand-held selfie:

- capture: `Amateur phone selfie`
- angle: one of `straight on`, `slightly high angle`, `side angle, three-quarter view`,
  `close-up, face fills the frame`, `arm extended, mid-body framing`, `low angle from below`
  (rare, only with a reason)
- framing line: `Slightly imperfect framing, arm partially visible at the bottom edge.`
- rawness line: `Raw, unedited, spontaneous.`

Mirror selfie:

- capture: `Mirror selfie taken with a phone`
- pose: standing or sitting, `phone held at chest level` or `at waist level`, `full body` or
  `mid-body visible in the mirror reflection`
- place: the mirror is the environment (bathroom, bedroom wall mirror, open wardrobe,
  lift, gym changing room, shop fitting room, hotel room, small round wall mirror)
- rawness line: `Raw, unedited, authentic social media mirror selfie.`

Rawness words to rotate so no two prompts share the same set: `subtle film grain`,
`light compression artifacts`, `slightly overexposed`, `slightly underexposed`, `casual
composition`, `slight motion blur` (at most two per twenty).

**Struck on sight**: professional photography, studio lighting, softbox, ring light (unless
the place is a gym or dressing room and it is the actual light), DSLR, mirrorless,
editorial, magazine, cover shoot, high fashion, runway, glamour shot, boudoir, perfectly
composed, cinematic composition, model pose, poses for the camera, serious gaze, fierce,
intense stare, bokeh, shallow depth of field, creamy background blur.

### Expression bank (behaviour, not a label)

| Feeling | Write |
| --- | --- |
| playful | playful pout, slight nose scrunch, eyes squinted with a smile |
| silly | cheeks puffed out, eyes wide and amused |
| cheeky | tongue out to one side, one eye winked, eyes crinkled |
| kissy | exaggerated kissy face, lips pushed forward, eyes laughing |
| wink | wink, half smile, head tilted slightly |
| real laugh | head tilted back a little, eyes crinkled, mouth open mid laugh |
| smirk | subtle smirk, one corner of the mouth lifted, knowing eyes |
| soft flirt | slight lower lip bite, half smile, gaze held on the lens |
| warm | intense soft gaze into the lens, lips slightly parted, head tilted |
| teasing | one eyebrow raised, mischievous half smile |
| surprised | wide eyes, mouth in a soft "oh", eyebrows up |
| dreamy | gaze slightly off the lens, soft pensive half smile, hand near the chin |
| conspiratorial | warm genuine smile, leaning toward the lens |
| self-mocking | exaggerated eye roll, amused smirk, hand on the forehead |
| bored chic | relaxed neutral face, hand propping the chin or playing with hair |
| calm confidence | calm gaze, subtle smile, chin slightly lifted |
| sleepy | sleepy soft eyes, gentle smile, tousled hair, hand near the face |

### Imperfection bank

Mirror: toothpaste streaks on the mirror; fingerprints on the glass; clutter on the counter
(bottles, a hair tie, mascara); unmade bed in the reflection; clothes piled on a chair; a
worn phone case or a sticker on it; a smudge on the lens; mirror frame slightly tilted;
part of another room visible behind her.

Hand-held: a strand of hair across the frame; a fingertip at the edge of the lens; tilted
framing; blurred edge from arm motion; window flare on the lens; lens smudge; pillow or
sheet creases at the edge.

Any: natural skin texture with light grain, not airbrushed; flyaway hair; slightly chapped
lips (rare); light circles under the eyes (rare).

### Light bank

| Light | Write |
| --- | --- |
| soft morning | soft morning light from a window, slightly diffused |
| daylight | bright daylight; overcast diffuse light; flat midday light |
| golden hour | warm late afternoon sun, long shadows |
| dusk | soft dusk light, blue hour tones |
| indoor night | warm lamp light; harsh tungsten ceiling light; mixed light from a TV and a lamp |
| night through a window | street lamp glow through the window, ambient city light |
| phone flash | harsh direct phone flash, slight grain |
| bathroom | harsh overhead bathroom light; mixed daylight from a frosted window and a bulb |
| gym or changing room | harsh fluorescent light, slightly overexposed |
| fitting room | warm yellow shop light, overhead glare |

## The variety ledger

Keep a table with one row per image: index, type, place, outfit, moment, light, expression,
imperfections, prompt, filename (`001_selfie_bedroom.png` style, zero-padded so the output
sorts). The rules the ledger must pass before anything runs:

- No two rows share the same place, outfit and expression.
- At least eight distinct expressions when N is twenty or more; at least five when N is
  between ten and twenty.
- No three consecutive rows in the same light; per twenty rows, at most five in bright
  daylight, at most three in golden hour, at least two in ugly light (tungsten,
  fluorescent, direct flash). Ugly light is what reads as amateur.
- No two consecutive mirror selfies in the same room.
- No two rows with the identical rawness word set.
- Every row ends with the character-sheet binding line; none contains a struck word.

Write the ledger as `brands/<client>/runs/<batch-id>/ledger.json` (the `runs/` folder is
gitignored operational output) so a resumed batch can read it.

## Running the batch

Workflows with a `CR Prompt List` seam, from `workflows/manifest.json`:

- `workflows/icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-_Subs_-_Icekiub_v2.json`
  (dataset of one character; the P06 and X01 templates use it)
- `workflows/icekiub/Carousel_Pose_changer_-_Icekiub_V1.7.json` (poses of one character
  from a reference; its `LoadImage` nodes take the sheet)

Character sheet first if there is none: `workflows/icekiub/icy_ref_character_sheet_for_minimax.json`
or the engine's `character_sheet` step; the sheet specification sentence is in
`style-block`.

```bash
python packages/comfy-client/client.py probe --backend pod
python packages/comfy-client/client.py validate workflows/icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-_Subs_-_Icekiub_v2.json --backend pod
python packages/orchestrator/control.py propose --brand <client> --kind generate_draft --title "<character> batch <id>, N stills" --estimate <usd>
python packages/comfy-client/client.py run workflows/icekiub/INFLUENCER_Dataset_AIO_-_Klein_Revamped_-_Subs_-_Icekiub_v2.json --backend pod --seed <seed> --prompt "<prompt 1>" --prompt "<prompt 2>"
python packages/comfy-client/client.py run <same> --backend pod --seed <seed> --prompt ... --live
```

`--prompt` repeats; every value lands in the one `CR Prompt List`. If the run log says
`WARNING: no CR Prompt List node found`, the graph has no seam and the prompts were not
injected; stop, do not pass `--live`. `validate` reporting `UNVERIFIED` means the pod could
not be reached; `--live` refuses in that state by design.

Cost estimate for the proposal: `brands/_business/ideas.yaml` records 444 Klein images per
GPU-hour measured on the pod and an assumed A100 rate of $1.64 per hour, so N images cost
about `N / 444 * 1.64` dollars plus the pod's idle minutes. Say "assumed" for the rate until
a live run replaces it, and write the real figure into the persona file's batch history.

Local ComfyUI alternative: write each prompt as `brands/<client>/runs/<batch-id>/prompts/<filename>.txt`,
point a `PromptListFromFolder` node (icynodes, sort `name`) at that folder, and the graph
runs once per file; `filenames` on the node carries the label through.

## Resuming and never running twice

The source skill's own incident: a wrapper printed an error while the batch kept running,
the agent relaunched, and every image in flight was paid for twice. Before any re-run:

1. The pod's queue and history for the prompt id the first run printed (`client.py` waits
   on history; a completed history with outputs is the only success).
2. `brands/<client>/runs/<batch-id>/` for files already written.
3. The ledger: mark each filename that exists as done.

If any of the three shows activity, wait and poll; do not resubmit. When a re-run is
justified, submit only the ledger rows not marked done, under a new run id, and note the
re-run in the persona file's batch history.

## After the batch

`python packages/vision/analyze.py --brand <client> --path brands/<client>/runs/<batch-id>`
measures palette, warm ratio, subject quadrant and symmetry for every file offline. Use it
to check the variety the ledger promised actually happened (twenty near-identical warm
ratios means the light quota failed in the model even if it passed on paper). Failed rows go
back through the expression or imperfection bank, not through more adjectives.

## Gaps

- `client.py` has no `--image` flag; the character sheet for `Carousel_Pose_changer` is set
  in the workflow JSON or on the studio canvas, not on the command line.
- No `amateur-phone` preset exists in `brands/_presets/directors.yaml`; until one is added
  through `style-block`, the Director Engine cannot compose this realism into its angle
  prompts, and this skill's grammar is applied by hand.
- No per-file checkpoint is written by `client.py`; the ledger above is kept by whoever
  runs the skill.
- `FORBIDDEN` does not catch "reproduce her features from the reference image"; that line
  is refused by rule 1, not by code.
