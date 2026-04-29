# Fix ai-only-scripts after config_params refactor

## Summary

Reviewed all `scripts/ai-only-scripts/` after the recent config_params restructuring
(providers → config_params, default-pkg elimination, path format changes).

## Changes

### Deleted
- `scripts/ai-only-scripts/fix-sops-pkg-keys/` — one-time migration script to rename
  SOPS top-level keys from `<pkg>:` to `<pkg>_secrets:`. Migration is complete; script
  was obsolete.

### Fixed: `_MAAS_TASKS_DIR` env var (never exported from set_env.sh)

All four playbooks used `lookup('env', '_MAAS_TASKS_DIR')` to include shared MaaS task
files. This variable was never exported from `set_env.sh`, so all four scripts would have
failed at runtime. Replaced with hardcoded `_INFRA_DIR`-relative paths:

- `push-debian-preseed/playbook.yaml` → `maas-pkg/_tg_scripts/maas/configure-server/tasks/`
  (needs both `capture-config-fact.yaml` and `deploy-debian-preseeds.yaml`)
- `fix-ms01-interface-link/playbook.yaml` → `maas-pkg/_tg_scripts/maas/configure-server/tasks/`
  (needs `capture-config-fact.yaml` for server-level config)
- `recover-ms01-network/playbook.yaml` → `maas-pkg/_tg_scripts/maas/configure-machines/tasks/`
  (needs `capture-config-fact.yaml` for machine-level config)
- `reset-ms01-01/playbook.yaml` → `maas-pkg/_tg_scripts/maas/configure-machines/tasks/`
  (same)

### Fixed: stale unit paths in `reset-ms01-01/playbook.yaml`

Terraform state-rm tasks referenced old `proxmox-pkg` example paths:
- `proxmox-pkg/_stack/null/examples/pwy-homelab/proxmox/install-proxmox`
  → `pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox/install-proxmox`
- `proxmox-pkg/_stack/null/examples/pwy-homelab/proxmox/configure-proxmox-post-install`
  → `pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox/configure-proxmox-post-install`

### Fixed: stale wave names in comments (recover-ms01-network, reset-ms01-01)
- `on_prem.maas.machines` → `pxe.maas.machine-entries`
- `on_prem.proxmox.install` → `hypervisor.proxmox.install`

### Updated README
- Removed `fix-sops-pkg-keys` from the table.
