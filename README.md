# EPALLE Studio × Ongea Pesa — Autonomous Content Company

Monorepo for a voice-driven content studio: brief → strategy → generation (OpenRouter / ComfyUI on RunPod) → deterministic brand compositing → scheduled publishing (Postiz, WhatsApp Status) — with a graphified corpus and temporal memory.

Design spec: `docs/superpowers/specs/2026-09-12-epalle-ongea-content-company-design.md`

Standing rules: queued is not success · dry-run by default, allowlists not arbitrary input · composite the logo, never regenerate it · agents create, deterministic code validates, humans approve.

Secrets live in Windows DPAPI via `infra/runpod/set_secret.py`. No `.env` with real values is ever committed.
