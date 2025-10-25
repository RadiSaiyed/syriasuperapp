variable "ssh_key_name" {
  description = "Name for the uploaded SSH key"
  type        = string
  default     = "superapp"
}

variable "ssh_public_key" {
  description = "Public key content (overrides ssh_public_key_path if set)"
  type        = string
  default     = null
}

variable "ssh_public_key_path" {
  description = "Path to public key if ssh_public_key is not provided"
  type        = string
  default     = "../.ssh/id_hetzner_ed25519.pub"
}

variable "server_name" {
  description = "Name of the Hetzner server"
  type        = string
  default     = "superapp-node-1"
}

variable "server_type" {
  description = "Hetzner server type (e.g., cx31, cx21)"
  type        = string
  default     = "cx31"
}

variable "server_image" {
  description = "Base image (e.g., ubuntu-22.04)"
  type        = string
  default     = "ubuntu-22.04"
}

variable "server_location" {
  description = "Location (hel1, fsn1, nbg1)"
  type        = string
  default     = "hel1"
}

variable "user_data" {
  description = "Optional cloud-init user_data"
  type        = string
  default     = null
}

variable "base_domain" {
  description = "Base DNS zone (e.g. example.com)"
  type        = string
  default     = null
}

variable "hostnames" {
  description = "Subdomains to create A/AAAA records for"
  type        = list(string)
  default     = [
    "payments",
    "taxi",
    "automarket",
    "bus",
    "chat",
    "commerce",
    "doctors",
    "food",
    "freight",
    "jobs",
    "stays",
    "utilities",
  ]
}

variable "ttl" {
  description = "DNS TTL seconds"
  type        = number
  default     = 300
}

variable "manage_zone" {
  description = "If true, create DNS zone; otherwise, use existing"
  type        = bool
  default     = false
}

variable "a_ipv4" {
  description = "IPv4 address for A records (overrides detected server IPv4)"
  type        = string
  default     = null
}

variable "aaaa_ipv6" {
  description = "IPv6 address for AAAA records (overrides detected server IPv6)"
  type        = string
  default     = null
}
