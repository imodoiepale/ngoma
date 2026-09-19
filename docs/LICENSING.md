# Licensing

Three different licences are in play. This matters because the Whop course
(`packages/publish/whop/`) is a **paid distribution**, and two of these components are
required for the workflows it teaches to actually run.

| Component | Licence | Where the source lives | Status |
|---|---|---|---|
| `work/h3/` — ComfyUI H3 Motion Context MultiRef (37 nodes) | **GPL-3.0** | `Codex\...\work\h3\` | NOT in this repo |
| `work/matrix-power-nodes/` — MATRIX / WaveSpeed nodes | MIT (Matrix Lab, 2026) | `Codex\...\work\matrix-power-nodes\` | NOT in this repo |
| MATRIX-LAB-Nodes 0.4.0 and MATRIX Krea 2 Workflow 1.1.0 (JsonMatrixLab on GitHub) | **proprietary**: no copy, modify, distribute or *use* without a written agreement | `Documents\COMFY\MatrixLab` (reference only) | NOT in this repo; practices only, see `docs/NODE-PACK-PRACTICES.md` |
| `packages/studio-ui/` | MIT (forked from SamurAIGPT/Vibe-Workflow) | here | ported |
| Icekiub workflow JSONs and node packs (`workflows/icekiub/`) | **unstated**: bought on Skool, 2026-09-14 | here | internal use only, see below |
| `workflows/icekiub/nodes/icynodes/` (merged pack, 2026-09-16) | **MIT** per its `pyproject.toml`; the only Icekiub artefact with a stated licence | here | the standalone folders it merges stay unstated |
| AiKAMI "AI Creator Series" guides, Days 1 to 7 (`docs/creators/aikami/source/`) | free public guides by @buck_the_aikami, no licence stated | here | study material, internal reference only, never redistributed |
| PJ Accetturo's Nexus skill (`docs/creators/pjaccetturo/`) | published publicly as a paste-in prompt, no licence stated | here | study material; our skills restate the method in our own words |
| "alexya-batch-api" Claude skill, v1.2.0 (`docs/creators/alexya/source/alexya-batch.skill`) | no author and no licence stated; hosted-API client for alexya.ai | here | study material, internal reference only, never redistributed; the client is not run or ported |
| This repo's own code | choose one — currently unlicensed | here | **decide** |

## The GPL-3.0 problem

`work/h3/` is a fork of `NikoDemon80/ComfyUI-H3-Motion-Context`, GPL-3.0, copyright 2026
NikoDemon80. Ten workflows in the graph depend on it (`graph_query.py dependents
comfyui-h3-motion-context`).

GPL-3.0 is copyleft. If you **distribute** that code — bundling it in a course download, a
Docker image, a paid template pack, a RunPod image customers pull — you must ship the
complete corresponding source under GPL-3.0 and preserve the copyright notice.

What is safe:
- Running it yourself, including on your own RunPod pod, to make content you sell. Output
  of a GPL program is yours; using the program is not distribution.
- Telling course students to install it themselves from the upstream repo.

What is not safe without complying:
- Shipping a Docker image or zip that contains it.
- Rolling it into a proprietary node pack.

**Recommendation:** keep `h3` as an install-time dependency students fetch themselves, and
never vendor it into a distributed artefact. If it must be bundled, ship it as a separate
GPL-3.0 component with its licence and source, kept at arm's length from your own code.

## The Icekiub workflows

`workflows/icekiub/` came from paid Patreon/Skool packs and carry **no stated licence**.
Absence of a licence means no distribution rights by default — not permission.

They are fine as a private reference and as something you run. Do **not** redistribute them
in the course, a template pack, or a public repo without the author's permission. If this
repo ever goes public, they must come out or be replaced with graphs built from scratch.

Two practical notes from the 2026-09-19 import:

- `icynodes` registers the same node classes as `betterimage_loader`, `ICYLM`,
  `icymegapixelresize` and `ComfyUI-IcyHider-icekiub`. Install one or the other in a ComfyUI,
  never both.
- `captioning_workflow.json` ships with the Icy LM Studio node pointed at Icekiub's own LAN
  (`http://192.168.2.20:8080`). Re-point it at your LM Studio server before running; it will
  not, and must not, reach his machine.

## Your own code

This repo has no LICENSE file. Pick one before publishing anything. Note that a
`matrix-power-nodes`-derived pack must stay MIT-compatible, and anything linking `h3` at
distribution time inherits GPL-3.0.

## Attribution already recorded

- `h3` → NikoDemon80, forked by seitanism; AV masking design credits Barish Ozbay
  (`drozbay`) and ComfyUI PR #15375
- `studio-ui` → SamurAIGPT/Vibe-Workflow (MIT)
- `matrix-power-nodes` → Matrix Lab (MIT)
- workflow packs → Icekiub; UGC format curriculum → DGI Kaos
