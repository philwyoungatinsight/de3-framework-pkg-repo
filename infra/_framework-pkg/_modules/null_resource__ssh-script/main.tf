locals {
  # If host is provided directly, use it. Otherwise pick the first non-loopback,
  # non-link-local IPv4 from ipv4_addresses (proxmox provider list-of-lists format).
  # Falls back to "" when ipv4_addresses is empty (e.g. QEMU agent timed out);
  # the resource is skipped in that case via count = 0.
  _candidates = var.host != "" ? [var.host] : [
    for ip in flatten(var.ipv4_addresses) : ip
    if !startswith(ip, "127.") && !startswith(ip, "169.254.")
  ]
  _host = length(local._candidates) > 0 ? local._candidates[0] : ""
}

resource "null_resource" "this" {
  # Skip when no reachable host IP is known (QEMU agent not yet available).
  count = local._host != "" ? 1 : 0
  # Re-run the script only when its content changes.
  triggers = {
    script_hash = sha256(var.script)
  }

  connection {
    type  = "ssh"
    host  = local._host
    user  = var.user
    agent = var.ssh_agent

    # Optional jump/bastion host (e.g. for VMs on isolated VLANs)
    bastion_host  = var.bastion_host != "" ? var.bastion_host : null
    bastion_user  = var.bastion_host != "" ? (var.bastion_user != "" ? var.bastion_user : var.user) : null
  }

  # Write the script to ~/tg-setup.sh using base64 so that shell ~ expansion works
  # reliably and no special characters in the script content can cause quoting issues.
  # (The file provisioner uses SFTP and cannot expand ~ or $HOME.)
  provisioner "remote-exec" {
    inline = [
      "printf '%s' '${base64encode(var.script)}' | base64 -d > ~/tg-setup.sh",
      "chmod +x ~/tg-setup.sh",
      "~/tg-setup.sh",
      "rm -f ~/tg-setup.sh",
    ]
  }
}
