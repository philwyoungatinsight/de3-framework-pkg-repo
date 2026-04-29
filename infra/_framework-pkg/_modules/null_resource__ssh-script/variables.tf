# ── Required ──────────────────────────────────────────────────────────────────

variable "host" {
  description = "IP address or hostname of the target machine. If empty, derived from ipv4_addresses."
  type        = string
  default     = ""
}

variable "ipv4_addresses" {
  description = "List of IP address lists per NIC (proxmox provider format). Used to derive host when host is empty: picks first non-loopback, non-link-local address."
  type        = list(list(string))
  default     = []
}

variable "user" {
  description = "SSH username to connect as."
  type        = string
}

variable "script" {
  description = "Shell script content to upload and run on the remote host. Re-runs when content changes."
  type        = string
}

# ── Optional ──────────────────────────────────────────────────────────────────

variable "ssh_agent" {
  description = "Use the local SSH agent for authentication."
  type        = bool
  default     = true
}

variable "bastion_host" {
  description = "Optional SSH bastion/jump host IP or hostname. When set, Terraform connects to the target host through this bastion."
  type        = string
  default     = ""
}

variable "bastion_user" {
  description = "SSH username for the bastion host. Defaults to var.user when empty."
  type        = string
  default     = ""
}
