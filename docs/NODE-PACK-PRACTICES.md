# How to build a custom node pack that people can trust

Lessons from studying MATRIX LAB's public releases
([MATRIX-LAB-Nodes 0.4.0](https://github.com/JsonMatrixLab/MATRIX-LAB-Nodes) and
[MATRIX Krea 2 Workflow 1.1.0](https://github.com/JsonMatrixLab/MATRIX-Krea2-Workflow), read on 2026-09-14),
written in our own words.

## What we may and may not take

Both repositories are **proprietary**, even though they are public on GitHub:

- The node pack's licence grants no permission to copy, modify, distribute, sublicense, publish **or use**
  the software without a separate written agreement with MATRIX LAB.
- The workflow's licence grants no permission to redistribute, publish, sublicense or sell it; use is subject
  to an agreement with MATRIX LAB.

So none of their code, workflow JSON, screenshots or guides are in this repo, and the studio does not install
the pack. The release zips sit in `Documents\COMFY\MatrixLab` for reference only. What follows is engineering
practice, described independently. If we want to run their Krea 2 workflow, we ask MATRIX LAB for an agreement
first (their paid Skool community is the likely route).

The public model locations their docs name (Hugging Face repos for the Krea 2 encoder, eye detector and human
segmentation) are facts, not their material; `infra/runpod/plan_models.py` now searches those repos.

## The practices worth adopting

### 1. A node is a thin, generated declaration over a versioned core block

Each node file only declares its sockets, widgets, defaults and batch policy, then hands off to a shared
executor. The behaviour lives in a separate core block with its own version and content hash. The pack's entry
point is generated, not hand-written.

**For us:** when we build `epalle-nodes`, keep node classes as declarations and put logic in plain, testable
Python modules (the way `packages/compositor` already works). Generate the registration file from one list.

### 2. A machine-readable manifest is the truth about an artifact

A `MANIFEST.json` lists every block with version and content hash, and every registered class ID. Installation
fails if the installed manifest does not show exactly the expected registrations.

**For us:** the same idea as `workflows/manifest.json` (sha256 per workflow) and `register_workflow.py`
(attribution from `NODE_CLASS_MAPPINGS`, never guessed). Extend it to our own node pack: a test that the
registered class IDs equal the manifest.

### 3. Contracts are enforced at the socket boundary

Inputs are checked when they enter a node: an IMAGE must be a 4-dimensional float tensor in 0..1, a MASK
3-dimensional, a LATENT must carry `samples`, scalars must be the exact type. Tiny out-of-range values from VAE
decoders are clamped with a log line; anything bigger is an error that names the violation. A missing widget
in an older saved graph falls back to its declared default instead of crashing.

**For us:** matches "unknown is not OK". Our comfy-client validation should report contract violations by name,
and our nodes should never silently coerce a wrong type.

### 4. Failures are classified by the user's next safe action

Provider errors are named classes (auth, insufficient funds, moderation, rate limit, transient, permanent
rejection, empty success, **indeterminate submit**, timeout, context length), each marked retryable or not and
with a billability field. An HTTP failure maps to exactly one class. Error detail is redacted (URLs, keys,
tokens) and truncated before it reaches a user.

**For us:** the most useful single idea here. `image-router`, `publish` and the RunPod client should raise
named failures like this, and an ambiguous submit must be recorded as *possibly billed*, never as failed or
succeeded. It is the formal version of "queued is not success".

### 5. Model assets are pinned: exact path, pinned revision, size and SHA-256

The model guide gives each file's destination, a download URL pinned to a revision, its byte size and its
SHA-256, and says to stop on any mismatch. A matching filename is explicitly not enough. Nodes that need
detector weights look them up by role in a registry and refuse unverified files.

**For us:** `download-plan.json` has repo and path; add `revision`, `bytes` and `sha256` when a file is first
fetched, and have `download_planned.py` verify them. `plan_models.py` already refuses to substitute a
lookalike for a creator's private LoRA.

### 6. Compatibility aliases keep old saved workflows loading

When a class ID is renamed, the old ID is registered as an alias subclass of the new one, so saved graphs still
open. The alias is counted in the manifest and documented, and a migration guide covers anything the alias
cannot preserve.

**For us:** never rename a registered node type in place. Alias, test that both IDs resolve, and note the
migration.

### 7. A declared, honest verification boundary

Each release says exactly what was verified: ComfyUI version and core commit, frontend version, PyTorch/CUDA,
GPU model, which resolutions ran, what was *not* run (the paid prompt provider, LoRAs, Nodes 2.0), and that
save, reload and the API export matched. No universal hardware claim.

**For us:** the proposals already say "no step has been run end to end on a GPU yet". When a pod run happens,
record the same boundary next to the workflow: commit, GPU, resolution, what was skipped.

### 8. An install contract written for AI agents

A separate `AGENT-INSTALL.md` tells an automation agent exactly what it may do: pinned inputs, the procedure,
the expected registrations, which collisions to report, and hard limits (no provider calls, no paid actions,
never fill prompts, never queue a render, never put a token in a URL or file, disable conflicting packs only
recoverably and with the user's authority).

**For us:** write `AGENT-INSTALL.md` for the pod setup (`infra/runpod`) in this style, so any agent setting up
ComfyUI follows the same gates as `shared-skills/approved/content-studio/SKILL.md`.

### 9. Paid actions need explicit intent, and credentials never serialise

Ordinary graph execution never calls a paid provider. A prompt-assist button calls it only after credentials
are configured and the user explicitly asks, with a warning that charges may apply. Credentials are stored
outside workflow JSON.

**For us:** same as our dry-run default and DPAPI vault. Any node we write that can spend money needs an
explicit action separate from queueing, and reads secrets through `packages/common/vault.py`, never widgets.

### 10. Privacy-safe output as a first-class node

A saver strips prompt and workflow metadata from shared images, and the docs say plainly that its output is not
a workflow backup.

**For us:** the compositor's masters are what we publish. Add a metadata-strip step before publishing client
work, and keep the full-metadata copy internally.

### 11. Small operator conventions that prevent mistakes

- Every image-path switch means the same thing: ON applies the stage, OFF passes the image through unchanged.
- Released workflows ship with the user-facing prompt fields blank, so no one generates someone else's prompt.
- Separate offline tests (Python) and frontend syntax checks run in CI on two Python versions, without a GPU.

**For us:** adopt the ON/OFF convention for canvas steps that can be bypassed, ship client templates with empty
briefs, and keep our suite runnable with no key, GPU or network (it already is).

## What to build next, in order

1. Named provider failures with billability in `image-router`, `publish` and the RunPod client (practice 4).
2. `revision`, `bytes` and `sha256` in the pod download plan, verified on download (practice 5).
3. `infra/runpod/AGENT-INSTALL.md` for pod setup (practice 8).
4. A metadata-strip step before publishing (practice 10).
5. When `epalle-nodes` is built: generated registration, manifest test and socket contracts (practices 1-3, 6).
