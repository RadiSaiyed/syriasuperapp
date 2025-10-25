locals {
  pubkey = var.ssh_public_key != null && length(var.ssh_public_key) > 0 ? var.ssh_public_key : file(var.ssh_public_key_path)
}

resource "hcloud_ssh_key" "default" {
  name       = var.ssh_key_name
  public_key = local.pubkey
}

resource "hcloud_firewall" "web" {
  name = "superapp-web"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "app" {
  name        = var.server_name
  server_type = var.server_type
  image       = var.server_image
  location    = var.server_location
  ssh_keys    = [hcloud_ssh_key.default.id]

  # Attach firewall
  firewall_ids = [hcloud_firewall.web.id]

  # Optional cloud-init (pass via -var or tfvars)
  user_data = var.user_data
}

output "server_ipv4" { value = hcloud_server.app.ipv4_address }
output "server_ipv6" { value = hcloud_server.app.ipv6_address }
output "server_status" { value = hcloud_server.app.status }

############################
# DNS (Hetzner DNS provider)
############################

locals {
  chosen_ipv4 = var.a_ipv4 != null && length(var.a_ipv4) > 0 ? var.a_ipv4 : try(hcloud_server.app.ipv4_address, "")
  chosen_ipv6 = var.aaaa_ipv6 != null && length(var.aaaa_ipv6) > 0 ? var.aaaa_ipv6 : try(hcloud_server.app.ipv6_address, "")
}

# Manage or lookup the DNS zone
resource "hetznerdns_zone" "zone" {
  count = var.manage_zone && var.base_domain != null && length(var.base_domain) > 0 ? 1 : 0
  name  = var.base_domain
  ttl   = var.ttl
}

data "hetznerdns_zone" "zone" {
  count = (!var.manage_zone) && var.base_domain != null && length(var.base_domain) > 0 ? 1 : 0
  name  = var.base_domain
}

locals {
  zone_id = var.base_domain == null || length(var.base_domain) == 0 ? null : (
    var.manage_zone ? hetznerdns_zone.zone[0].id : data.hetznerdns_zone.zone[0].id
  )
}

# A records for each hostname
resource "hetznerdns_record" "a_records" {
  for_each = local.zone_id != null && length(local.chosen_ipv4) > 0 ? toset(var.hostnames) : []
  zone_id  = local.zone_id
  name     = "${each.value}.${var.base_domain}"
  type     = "A"
  value    = local.chosen_ipv4
  ttl      = var.ttl
}

# AAAA records for each hostname
resource "hetznerdns_record" "aaaa_records" {
  for_each = local.zone_id != null && length(local.chosen_ipv6) > 0 ? toset(var.hostnames) : []
  zone_id  = local.zone_id
  name     = "${each.value}.${var.base_domain}"
  type     = "AAAA"
  value    = local.chosen_ipv6
  ttl      = var.ttl
}
