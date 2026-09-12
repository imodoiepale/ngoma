# Postiz on a Hostinger VPS

One container (frontend + backend + workers + cron), plus Postgres, Redis and Caddy for
TLS. Nothing but 80/443 is exposed.

## Sizing

Postiz wants **2 GB RAM minimum, 4 GB comfortable**. The build is memory-hungry; on a 2 GB
plan add swap before first start or the container will be OOM-killed mid-boot:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 1. DNS first

Point an A record at the VPS public IP **before** starting the stack — Caddy requests a
certificate on boot and will fail loudly if the name does not resolve to this machine.

```
postiz.yourdomain.com.  A  <VPS_IP>
```

## 2. Docker

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker
```

## 3. Configure

```bash
cd infra/postiz
cp .env.example .env && chmod 600 .env
openssl rand -hex 32          # -> POSTIZ_JWT_SECRET
openssl rand -hex 24          # -> POSTGRES_PASSWORD
nano .env
```

`MAIN_URL`, `FRONTEND_URL` and `NEXT_PUBLIC_BACKEND_URL` are derived from `POSTIZ_DOMAIN`
in the compose file. Backend URL **must** be the origin plus `/api`. Getting that wrong is
the most common self-host failure: the UI loads and every API call 404s.

## 4. First boot

```bash
docker compose up -d
docker compose logs -f postiz      # wait for the migrations to finish
```

Registration is **disabled by default** in the compose file. To create your first account,
set `DISABLE_REGISTRATION: "false"`, `docker compose up -d postiz`, register, then set it
back to `"true"` and restart. Leaving registration open on a public host means anyone who
finds the URL can sign up.

## 5. Firewall

```bash
sudo ufw allow 22,80,443/tcp && sudo ufw enable
```

Postgres (5432) and Redis (6379) are deliberately not published — they are reachable only
on the internal compose network.

## 6. Connect Instagram

Instagram auto-publishing goes through the Meta Graph API. Three things must all be true:

1. The Instagram account is a **Professional** account (Business or Creator).
2. It is **linked to a Facebook Page**.
3. You have a Meta app with `instagram_content_publish`, `pages_show_list` and
   `instagram_basic`, and the app is live rather than in development mode.

Put the app id/secret in `.env`, restart, then connect the channel in the Postiz UI.
**This is the step that blocks publishing today** — see `docs/BLOCKERS.md`.

## 7. API key

Settings → Public API in the UI. Then on your workstation:

```bash
uv run infra/runpod/set_secret.py postiz
export POSTIZ_URL=https://postiz.yourdomain.com/api
uv run packages/publish/postiz.py channels
```

`channels` lists your connected integrations and their ids — those ids are what
`--integration-id` wants.

## 8. Backups

The database holds your scheduled queue and channel tokens. Losing it means reconnecting
every channel.

```bash
docker compose exec -T postiz-postgres pg_dump -U postiz postiz | gzip > postiz-$(date +%F).sql.gz
```

Put that in cron and copy the result off the VPS.

## Upgrades

```bash
docker compose pull && docker compose up -d
```

Take a backup first. `:latest` means an upgrade can arrive whenever you pull; pin a digest
in production once you have a version that works.
