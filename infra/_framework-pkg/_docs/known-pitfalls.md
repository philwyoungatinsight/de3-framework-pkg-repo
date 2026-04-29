# Known Pitfalls and Fixes

- **NEVER use directory symlinks as Terraform module sources**: `get_parent_terragrunt_dir()` resolves the symlink target, causing `stack_root`-relative paths to double up (e.g. `.../lab_stack/deploy/tasks/.../lab_stack/`). Copy `.tf` files or hardcode the real module path instead.

- **NEVER `stop` a network service on a remote host via Ansible**: Stopping `systemd-networkd` drops the DHCP lease and kills the SSH connection. Use `masked: true` only. The host keeps its IP until reboot. See `configure-linux-bridge.yaml` for the correct mask + reboot pattern.

- **AMT vs smart plug power priority**: Always use `power_type: smart_plug` when a machine has a smart plug. AMT is unreliable on MS-01 (BMC task queue errors). Never set `power_type: amt` when a smart plug is configured.

- **cloud_init_gateway** must match the real gateway (`10.0.10.1`). Wrong gateway → cloud-init apt-get fails → no qemu-guest-agent. Fix in YAML, re-apply, reboot.

- **qemu-guest-agent absent**: installed via cloud-init vendor-data. If absent, cloud-init failed. Check `cloud-init status --long`. Fix YAML config, apply, reboot.

- **pxe-test-vm-1** has no OS until MaaS deploys one. Guest agent will be absent until after `pxe.maas.*` waves complete. Expected behavior.

- **`proxmox_virtual_environment_download_file` upload timeout**: default 600s is too short for ISOs >1 GB. Always set `upload_timeout = 1800` for large ISOs.

- **Packer clone VMs inherit CD-ROM references**: if referenced ISO is absent when VM starts, `qmstart` fails with "volume does not exist". Add a `dependency` block in the clone VM's `terragrunt.hcl` pointing to the ISO download unit.

- **MaaS network interfaces after commissioning**: MaaS leaves interfaces unconfigured. Deploy fails with `400 Bad Request: Node must be configured to use a network`. Fix: `commission-and-wait.sh` calls `_configure_interfaces` post-commissioning. For stuck machines, run `scripts/ai-only-scripts/force-maas-ready`.

- **MaaS deploy timeout** (`deploy_timeout = 3h`): large images (e.g. Proxmox) can exceed 90 min. If `maas_instance` times out with "context deadline exceeded", the machine may still be deploying. Wait for MaaS to show "Deployed" (or run `force-maas-deployed` if curtin/cloud-init completed) then re-run make.
