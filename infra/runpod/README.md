# EPALLE RunPod deployment

## Provisioned resources

- Persistent network volume: `epalle-studio` (`7y7jyghmua`), 200 GB, US-KS-2.
- Development Pod: `eeoldxyxnd0o1z`, RTX A6000 48 GB. It is stopped when idle.
- Serverless template: `epalle-comfy-serverless-v1` (`s7eg4zafj9`).
- Scale-to-zero endpoint: `epalle-studio-api` (`ugtmfoidpnh8pd`), minimum workers 0 and maximum workers 1.
- ComfyUI 0.34.0 and CUDA were validated on the development Pod.
- Twelve model files (103.25 GB) were verified by exact size and SHA-256 and remain on persistent storage.

The 200 GB network volume continues to cost about USD 14 per month at the configured USD 0.07/GB/month rate. The stopped Pod does not incur hourly GPU runtime charges.

## SSH access

The generated private key is `../epalle_runpod_ed25519`; the public key is `../epalle_runpod_ed25519.pub`. Keep the private key private.

After starting the Pod, obtain its current public IP and TCP mapping for port 22 from RunPod, then connect from this directory:

```powershell
ssh -i ..\epalle_runpod_ed25519 -p <PORT> root@<PUBLIC_IP>
```

RunPod may assign a new public address or mapped port each time the Pod starts, so fetch the current values before connecting.

## Runtime layout

- `/workspace/epalle/ComfyUI`: ComfyUI runtime
- `/workspace/epalle/models`: persistent model store
- `/workspace/epalle/workflows`: reviewed workflow library
- `/workspace/epalle/workflow-api`: workflows admitted by the serverless handler
- `/workspace/epalle/state`: idempotency and job state

The serverless handler accepts only named workflows installed in `workflow-api`. Requests default to `dry_run=true`. MATRIX paid provider nodes are rejected by the serverless handler; the original MATRIX graph also starts with `live=false`.

## Verification status

- ComfyUI startup and `/system_stats`: passed on the RTX A6000 Pod.
- Model integrity: passed for all twelve files.
- Next.js studio production build: passed.
- Serverless endpoint creation and persistent-volume attachment: passed.
- Scale-zero dry request: still queued because no compatible worker capacity was admitted during verification. Treat this as an unresolved capacity test, not a successful generation.
- Development Pod resume on 2026-09-06: RunPod reported no free GPU on the assigned host. Creating a replacement 48 GB Pod in US-KS-2 also reported no available instance. The existing network volume remains attached and intact.
- Capacity retry: the existing EPALLE heartbeat temporarily retries every 15 minutes. On success it installs the expanded node set and SageAttention, syncs all 32 library workflows, validates the runtime, stops the development Pod, and restores its daily source-watch schedule.

No paid WaveSpeed generation was started.
