provider "hcloud" {
  # Uses env var HCLOUD_TOKEN from ops/deploy/hetzner/env.sh
}

provider "hetznerdns" {
  # Uses env var HETZNER_DNS_API_TOKEN from .env via env.sh
}
