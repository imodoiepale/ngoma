# EPALLE Studio UI

This project adapts the MIT-licensed Vibe-Workflow codebase into an EPALLE-specific node canvas for character datasets, SCAIL-2 replacement, MiniMax H3 music videos and localized UGC.

## Local start

1. Copy `.env.example` to `.env.local`.
2. Put the RunPod token only in `.env.local` as `RUNPOD_API_KEY`. Never commit it.
3. From this folder, run `npm install`, then `npm run build:lib`, then `npm run dev:app`.
4. Open `http://localhost:3000`.

The UI sends requests through its server route so the RunPod token is not exposed to browser JavaScript. The current Run button performs a dry-run capability check. Production render buttons should be enabled only for reviewed API-format workflow templates.

## Current boundary

The canvas, workflow switching, prompt editing, language selection and server-side RunPod bridge are implemented. The four visible studio graphs are operating templates for the EPALLE system; full drag-to-connect editing remains available in the underlying Vibe-Workflow `/workflow` surface. The MATRIX graph remains live=false and is excluded from the serverless handler.

Original base: https://github.com/SamurAIGPT/Vibe-Workflow
