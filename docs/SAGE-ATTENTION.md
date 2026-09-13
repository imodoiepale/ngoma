# SageAttention: what the AxiomGraph video teaches, and how it fits this studio

**Source:** AxiomGraph, *How to Install Sage Attention 2.2 on Latest ComfyUI Portable And
Desktop Version | Python 3.13 & 3.14*. Published 2025-10-29, 10:07 long, about 43k views.
Link: https://www.youtube.com/watch?v=9APXcBMpbgU

The subtitles and mined facts are in `packages/library/corpus/youtube/axiomgraph/`.
To check any claim against the video with timestamps:

```bash
uv run packages/library/graph_query.py evidence "sage attention"
```

To add another video the same way:

```bash
uv run --with pyyaml packages/ingest/yt_learn.py --video "<youtube link>"
```

## What the video covers

SageAttention is a faster attention kernel for ComfyUI on **NVIDIA GPUs under Windows**. It
mostly speeds up video models such as WAN, LTX and SCAIL. The steps below are summarised in
our own words. Timestamps point to the place in the video.

| When | Step | Why it matters |
|---|---|---|
| 00:16 | SageAttention needs Triton. Triton needs Python's C headers and libs, which ComfyUI **portable**'s embedded Python does not include. | This is the root cause of the common "failed to find Python libs" and Triton compile errors. |
| 00:53 | Check the embedded Python version: `python_embeded\python.exe -V`. The video shows 3.13.6. | The headers must come from the *same* Python version. |
| 01:08 | Install the full Python installer of that exact version into a separate folder. Copy its `include` and `libs` folders into `python_embeded`. | This gives Triton what it needs without changing ComfyUI's Python. |
| 02:30 | `python_embeded\python.exe -m pip install triton-windows` | Windows build of Triton. |
| 02:50 | `python.exe -m pip show torch` shows torch 2.9.0 built for CUDA 13.0. | This picks the SageAttention wheel. |
| 03:11 | Download a wheel from the woct0rdho/SageAttention GitHub releases. **Torch and CUDA must match** ComfyUI's. `cp39-abi3` in the file name means any Python 3.9 or newer works. A different CUDA *minor* version is fine (a cu129 install can use the cu128 wheel). | Picking the wheel is where most installs go wrong. |
| 04:32 | `python.exe -m pip install <wheel URL>` | |
| 05:03 | **Option 1, global flag:** add ComfyUI's `--use-sage-attention` after `--windows-standalone-build` in `run_nvidia_gpu.bat`. The console confirms SageAttention is active at startup. | Every model uses it. |
| 05:46 | **Option 2, per workflow:** add KJNodes' *Patch Sage Attention KJ* between the model (after any LoRA loader) and the KSampler. Set mode to `auto`, or pick a specific kernel (`sageattn_qk_int8_pv_fp16_cuda`, or the Triton one). | Can be turned on or off per workflow. The terminal logs the patch while the workflow runs. |
| 07:26 | **ComfyUI Desktop:** in the presenter's test, no header copy was needed. Use the built-in terminal. The video shows Python 3.12.8 and torch 2.8.0 on CUDA 12.9, so the cu128 wheel. Install the wheel, then `triton-windows`. The KJ node is recommended. | |

Not captured: the exact command list the video links to on pastebin. Everything above is
from the spoken transcript.

## How this fits what we run

**1. This PC cannot use SageAttention.** Its only GPU is Intel Graphics, with no NVIDIA card
or driver. SageAttention and Triton here are CUDA-only. On this machine, the `local` ComfyUI
backend is for building and validating graphs, not generating video. The video's steps
apply only if an NVIDIA Windows machine joins the setup. They can then be followed as
written.

**2. RunPod pods already follow the same rule, built from source.** The pods run Linux, so
the Windows wheels do not apply. The rule is the same one the video teaches: match torch
and CUDA, and build for the GPU.
- `infra/runpod/install_sage_a100.sh` pins torch 2.9.1 on CUDA 12.8 and compiles for
  compute capability 8.0 (A100).
- `infra/runpod/install-sageattention.sh` actually runs a SageAttention kernel on the pod's
  GPU and rebuilds if it fails. This matters because the venv sits on a shared volume.

**3. Prefer the KJ node (option 2) to the global flag (option 1) on pods.** Our Icekiub
workflows already use *Patch Sage Attention KJ*. `infra/runpod/guard_kjnodes_sage.py`
bypasses that node on torch 2.11 or newer, where SageAttention 2.2 breaks, and falls back to
PyTorch SDPA. The guard can only intercept the node. A global `--use-sage-attention` flag
would skip the guard and crash those runs. **Do not add the flag to pod or serverless
launch commands.**

**4. Updating ComfyUI can silently break SageAttention.** A ComfyUI update can bring in a
new torch version. The installed wheel then no longer matches, and the failure appears at
generation time, not install time. After any update, re-check `pip show torch`. On pods,
re-run `install-sageattention.sh`, which tests that the kernel actually runs.

## Making it all work — the order

1. **YOU:** rotate the leaked keys, then store them:
   `uv run infra/runpod/set_secret.py runpod` and `uv run infra/runpod/set_secret.py openrouter`.
2. **ME:** prove serverless before relying on it:
   `uv run packages/comfy-client/client.py smoke --backend serverless --live`.
   It passes only when the job finishes and returns files.
3. **ME:** make `client.py validate` report whether SageAttention will really run on the
   target. That means checking the backend's torch version against the 2.11 guard and
   whether the kernel probe passes. Today a workflow can be marked OK while its Sage node is
   being bypassed. That is slower, not broken, but it should be visible.
4. **ME:** rebuild the serverless image with the same pinned stack as the A100 pods (torch
   2.9.x on CUDA 12.8, SageAttention built for the endpoint's GPU type). This keeps
   serverless and pod speeds comparable.
5. **YOU, optional:** if you want local generation, add an NVIDIA Windows machine (RTX
   30-series or newer) and follow the table above. The `local` backend picks it up at
   `http://127.0.0.1:8188`.
