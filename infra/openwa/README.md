# OpenWA — WhatsApp Status

Postiz has no WhatsApp provider, so Status posting runs here instead.

## Read this before deciding to use it

This is an **unofficial** automation path. WhatsApp does not support Status posting through
any official API, including the WhatsApp Business Platform. Automating it risks the number.

Mitigations built into `packages/publish/whatsapp.py`:

- one session, one number, one job at a time
- a hard cap of 8 sends/day and a 10-minute minimum gap
- explicit human confirmation per send (`--i-mean-it`)
- a persisted idempotency key per item, because there is no server-side dedupe
- the batch stops on the first failure rather than retrying into a rate limit

Never run OpenWA and Evolution API against the same number. Pick one.

Use a **dedicated number** you can afford to lose, not your personal one and not the number
customers already use to reach you.

## Deploy

```bash
cd infra/openwa
cp .env.example .env && chmod 600 .env
openssl rand -hex 24          # -> OPENWA_API_KEY
nano .env
mkdir -p sessions media
docker compose up -d
```

## Pair the session

The QR appears in the container logs. It expires in seconds, so have the phone ready.

```bash
docker compose logs -f openwa
```

WhatsApp → Settings → Linked Devices → Link a Device. Session data persists in
`./sessions/`, so this is a one-time step unless you unlink or the volume is lost.

## Verify

The port is bound to localhost, so tunnel in from your workstation:

```bash
ssh -L 8002:127.0.0.1:8002 user@your-vps
```

Then locally:

```bash
export OPENWA_URL=http://127.0.0.1:8002
export OPENWA_API_KEY=...            # same value as the VPS .env
uv run packages/publish/whatsapp.py status
```

A reachable server with no paired session silently accepts calls and posts nothing, which
is why `status` checks for `CONNECTED` rather than just a 200.

## Send

```bash
uv run packages/publish/whatsapp.py send --kind image \
    --media out/ongea-pesa-idea01_9x16.png \
    --caption "Ongea Pesa — speak, send, done." \
    --title "Mandazi Payment"            # dry run

uv run packages/publish/whatsapp.py send ... --live --i-mean-it
```

## Back up the session

Losing `./sessions/` means re-scanning the QR.

```bash
tar czf openwa-sessions-$(date +%F).tgz sessions/
```
