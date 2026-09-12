---
chapter: Operations
title: API jobs and cost control
lesson_type: text
embed_type: null
embed_id: null
---

# API jobs and cost control

Interactive work is where you decide what to make. API work is where you make it repeatedly.
This lesson covers the handoff and the guardrails that keep a repeatable job from becoming a
repeatable bill.

## The promotion gate

A graph is not an API job because it runs. It becomes an API job when it passes a checklist:

- Every node class resolves on a clean environment.
- Every model path resolves on the persistent volume.
- Dimensions, frame rate, and audio handling are explicit, not inherited from defaults.
- Outputs land in a known location with a predictable filename.
- It survives a restart — run it, restart the runtime, run it again, compare.

"It worked in my browser" is not any of these. The restart test in particular catches the most
common failure: a graph that depends on state living only in memory.

## Named graphs, not arbitrary graphs

The API accepts a **workflow name**, and resolves that name to a template file in a dedicated
directory. It does not accept an arbitrary graph from the caller.

This matters for two reasons. It prevents a malformed or hostile payload from executing
whatever it likes on your GPU, and it means the set of things your endpoint can do is a list
you can read. Validate the name against a strict character pattern and require the template
to exist. If the name does not resolve, reject — do not fall back.

## Dry run by default

Requests default to a dry run. A dry run validates the name, loads the template, checks that
the graph's nodes and models resolve, and returns without executing.

Defaulting to dry run means the expensive path requires an explicit opt-in on every call.
Inverting that default is how people discover they have run a hundred renders from a retry
loop.

## Blocking paid provider nodes

Graphs containing paid external provider nodes are **rejected outright** by the API handler,
regardless of the dry-run flag. Those graphs are for interactive use, where a human is looking
at the cost, and they carry their own `live=false` default on top.

The general principle: a step that spends money outside your own compute budget should never
be reachable from an automated caller. Two independent locks — handler rejection and the
graph's own default — is not redundancy, it is the correct number.

## Idempotency

Distributed jobs fail in the middle, and callers retry. Without protection, a retry after a
lost response bills you twice for one result.

The pattern used here: each job takes an **exclusive-create lock** keyed by its semantic
identity, written to persistent state. Creating the lock file fails if it already exists, so a
duplicate submission is refused rather than executed. The lock lives on the network volume, so
it survives a worker dying.

The important consequence: after an indeterminate submit, **check what actually happened
before retrying**. An indeterminate submit may already have produced — and been billed for — a
result.

## Result handling

- Hash every output. It is your only defence against a truncated or corrupted transfer.
- Inline small results as encoded data; return references for anything large. Inlining a large
  video is how you time out a request.
- Rewrite output filename prefixes per job so concurrent jobs cannot collide.

## Cost control

**Compute.**
- Minimum zero workers, so idle costs nothing.
- A short idle timeout, so a finished worker shuts down rather than lingering.
- An execution timeout that reflects your longest legitimate render. Without one, a hung job
  bills until someone notices.
- Stop the development pod when you step away. This is the largest single saving available and
  the easiest to forget.

**Storage.** Persistent volume cost is continuous and independent of GPU use. It is the price
of not re-downloading a model library, which is worth paying — but audit it. Delete
intermediate frames and superseded renders; they accumulate faster than models.

**External API spend.** Per-operation, no batching, no refunds. Enable a small subset, verify,
then scale. Check the provider dashboard rather than inferring spend from your own logs, since
your logs cannot see an operation whose response you lost.

## A weekly ten-minute audit

- Are any pods running that should not be?
- What is the volume actually holding, and how much is disposable?
- Does the provider dashboard match what you think you spent?
- Any jobs stuck in a queue?

Ten minutes weekly is cheaper than one surprise invoice.

## Deliverable

One graph promoted through the full checklist, one successful dry run, one real run polled to a
terminal status, and a written cost estimate per run.
