# Hetzner Deployment Playbook

This walkthrough hardens the Payments service for a first production landing on Hetzner Cloud. Repeat the same pattern for the other FastAPI services (they now share the same CORS + schema bootstrapping controls).

## 0. Hetzner env + keys from .env

Secrets from `hetzner_keys/` are now stored in the repo `.env` as:

- `HETZNER_API_TOKEN`
- `HETZNER_SSH_PRIVATE_KEY_B64` (Base64‑encoded OpenSSH private key)
- `HETZNER_SSH_PUBLIC_KEY`
- `HETZNER_IPV4`, `HETZNER_IPV6`, `HETZNER_IPV6_NETWORK`

Load them and prepare the SSH key file with:

```bash
source ops/deploy/hetzner/env.sh   # exports HCLOUD_TOKEN and writes .ssh key files

# Example usages:
hcloud server list                 # uses $HCLOUD_TOKEN
ssh -i "$HETZNER_SSH_PRIVATE_KEY_FILE" root@"$HETZNER_IPV4" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new
```

Notes:

- The script aliases `HCLOUD_TOKEN=${HETZNER_API_TOKEN}` for the Hetzner CLI / Terraform.
- The private key is written to `ops/deploy/hetzner/.ssh/id_hetzner_ed25519` (git‑ignored) with `0600` perms.

### DNS via Terraform

Add your Hetzner DNS API token to `.env`:

```
HETZNER_DNS_API_TOKEN=...   # create at https://dns.hetzner.com/settings/api-token
```

Optionally add your base domain at repo root `.env` to auto‑wire TF vars:

```
BASE_DOMAIN=example.com
```

Then apply DNS records (A/AAAA) for common subdomains (payments, taxi, chat, ...):

```bash
make hetzner-env
make hetzner-tf-plan     # shows DNS and server changes
make hetzner-tf-apply    # creates zone (if manage_zone=true) and records

# Variables (via env or -var):
# - TF_VAR_base_domain (or BASE_DOMAIN in .env)
# - TF_VAR_a_ipv4 / TF_VAR_aaaa_ipv6 (defaults to server outputs if present)
# - TF_VAR_manage_zone=true to create the zone (else it must exist)
```

### Make targets

Convenience wrappers exist in the root `Makefile`:

```bash
make hetzner-env       # load env, prep SSH key
make hetzner-hcloud    # hcloud server list
make hetzner-ssh       # SSH into the IPv4 from .env (default user root)

# Terraform helpers (see below)
make hetzner-tf-init
make hetzner-tf-plan
make hetzner-tf-apply
```

### Terraform (optional)

Minimal Terraform scaffold lives in `ops/deploy/hetzner/terraform/`.

- Provider uses `HCLOUD_TOKEN` from `env.sh`.
- Uploads the public key from `../.ssh/id_hetzner_ed25519.pub` or `TF_VAR_ssh_public_key`.
 - Creates an SSH key, a basic firewall (22/80/443), and one server.
 - Variables: `server_name`, `server_type` (e.g., cx31), `server_image` (ubuntu-22.04), `server_location` (hel1/fsn1/nbg1).
 - Cloud‑init: optional via `TF_VAR_user_data`. Ensure SSH keys in user_data match your `.env` public key or use root key injection via Hetzner (we already upload your SSH key).

Run:

```bash
make hetzner-tf-init
make hetzner-tf-plan   # review changes
make hetzner-tf-apply  # apply when ready

# Optional: see the outputs (IPv4/IPv6/status)
terraform -chdir=ops/deploy/hetzner/terraform output

# Optional: pass cloud-init inline (example)
# Beware of quoting; prefer a tfvars file instead.
# terraform -chdir=ops/deploy/hetzner/terraform apply -var "user_data=$(cat ../../../cloud-init.rendered.yml)"

# Recommended: render from .env and apply via TF_VAR
make hetzner-cloud-init
make hetzner-tf-apply-cloudinit
```

## 1. Provision infrastructure

1. **Server**: Ubuntu 22.04 LTS CX31 (2 vCPU / 8 GB) is a good starting point. Attach a floating IP.
2. **Storage**: Add a separate volume for database data if you plan to run Postgres yourself, otherwise use **Hetzner Managed PostgreSQL** (recommended) and **Managed Redis**.
3. **Firewall**: Allow inbound `80/443` (reverse proxy) and `22` (SSH). For internal services (Postgres/Redis) restrict to the private network CIDR only.

## 2. Install runtime

```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" |
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Log out and back in so the `docker` group takes effect.

## 3. Prepare application files

```bash
git clone <your-fork> ~/syria-superapp
cd ~/syria-superapp/apps/payments
cp .env.example .env
```

Edit `.env` and replace every placeholder:

```dotenv
ENV=prod
APP_HOST=0.0.0.0
APP_PORT=8080                         # published port (match compose mapping)
DB_URL=postgresql+psycopg2://user:pass@10.0.0.5:5432/payments   # Managed Postgres IP (private network)
REDIS_URL=redis://:<password>@10.0.0.6:6379/0                   # Managed Redis
JWT_SECRET=<64+ hex random>            # prod-only
INTERNAL_API_SECRET=<64+ hex random>
ADMIN_TOKEN=<admin bearer secret>
ALLOWED_ORIGINS=https://superapp.example.com,https://merchant.example.com
AUTO_CREATE_SCHEMA=false
DEV_ENABLE_TOPUP=false
DEV_RESET_USER_STATE_ON_LOGIN=false
OTP_MODE=redis
UVICORN_WORKERS=4
# optional: UVICORN_EXTRA_ARGS=--proxy-headers --forwarded-allow-ips='*'
```

For services that integrate with Payments (commerce, taxi, etc.) set `PAYMENTS_BASE_URL` to the internal service DNS / IP and copy the same `PAYMENTS_INTERNAL_SECRET`.

## 4. Launch the stack

The production compose file now lives at `apps/payments/docker-compose.yml` and disables auto‑reload while waiting on healthy Postgres/Redis.

```bash
docker compose up -d        # runs migrations on startup via entrypoint.sh
docker compose ps
docker compose logs -f api
```

### Optional: systemd unit

Create `/etc/systemd/system/payments.service`:

```ini
[Unit]
Description=Payments API
After=network-online.target docker.service
Requires=docker.service

[Service]
WorkingDirectory=/home/superapp/syria-superapp/apps/payments
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
Restart=always
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable with `sudo systemctl daemon-reload && sudo systemctl enable --now payments`.

## 5. Reverse proxy / TLS

* Terminate TLS with Traefik or Caddy (see `ops/deploy/compose-traefik/` for a template).  
* Point the reverse proxy to `http://127.0.0.1:8080`.  
* Enforce HTTPS redirects and inject `Forwarded` headers – `entrypoint.sh` exposes `UVICORN_EXTRA_ARGS` so you can pass `--proxy-headers`.

## 6. Backups and observability

* Postgres: enable automated snapshots on the managed instance or schedule `pg_dump` to object storage (Hetzner Storage Box / Backblaze).  
* Redis: enable AOF persistence or configure managed Redis with daily snapshots.  
* Metrics: the `/metrics` endpoint is Prometheus ready; you can scrape it with Hetzner Monitoring or self-hosted Prometheus (see `ops/observability`).  
* Logs: ship container logs with `docker logs` → journald, or run Vector/Fluent Bit.

## 7. Scaling the rest of the super-app

All FastAPI services now share the same production guards:

* `ALLOWED_ORIGINS` must be explicit for production, otherwise the service refuses to boot.  
* `AUTO_CREATE_SCHEMA` defaults to `false` when `ENV=prod`; run Alembic migrations instead.  
* Dev toggles (top-up/reset helpers, OTP dev mode) are blocked in prod.

Replay steps 3–5 for each vertical. For shared deployment you can:

1. Place each service inside `apps/<service>` and run `docker compose` from that directory, or  
2. Craft a higher level compose bundle that references the hardened service compose files and a shared Traefik + Postgres + Redis stack.

## 8. Checklist

- [ ] Secrets rotated (JWT, admin, internal HMAC).  
- [ ] `ENV=prod`, `ALLOWED_ORIGINS` set, dev toggles disabled.  
- [ ] Postgres/Redis reachable over private network with firewall rules in place.  
- [ ] Traefik/Caddy serving HTTPS with valid certificates.  
- [ ] Backups & monitoring in place.  
- [ ] Smoke tests (health check, login, transfer) pass against the Hetzner endpoint.
