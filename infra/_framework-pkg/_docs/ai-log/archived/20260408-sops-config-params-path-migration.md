# 2026-04-08 SOPS secrets config_params path migration

## Summary

Updated `config_params` path keys in three SOPS secrets files from the old
`cat-hmc/...` format to the new `<pkg>/_stack/...` format, matching the public
config_params keys updated in earlier refactors. Also updated Ansible tg-scripts
that hardcoded the old paths.

## Problem

After the config_params refactor (b5c7c47), public config_params use
`<pkg>/_stack/...` path keys. The secrets SOPS files still used `cat-hmc/...`
keys. Ansible scripts that look up per-machine secrets by path
(`_tg_providers_secrets.maas.config_params[item]`) were failing to match because
`item` comes from the public config (new format) but the secrets used the old format.

## SOPS files updated

| File | Keys changed |
|------|-------------|
| `infra/proxmox-pkg/_config/secrets.sops.yaml` | 3 keys: `cat-hmc/proxmox/pwy-homelab/pve-nodes/{ms01-01,pve-1,pve-2}` |
| `infra/maas-pkg/_config/secrets.sops.yaml` | 6 keys: `cat-hmc/maas/pwy-homelab` and 5 machine paths |
| `infra/mesh-central-pkg/_config/secrets.sops.yaml` | 1 key: `cat-hmc/null/pwy-homelab/mesh-central/configure-server` |

All top-level credential values (`admin_password`, `db_password`, `machine_deploy_password`,
`proxmox_power`, `api_key`, etc.) left unchanged at `providers.<name>.*` — required by
the current Ansible `capture-config-fact.yaml` merge pattern.

## Ansible tg-scripts updated

12 files updated across `maas-pkg/_tg_scripts/`, `mesh-central-pkg/_tg_scripts/`,
and `scripts/ai-only-scripts/` — both live Jinja2 path lookups and comments referencing
the old `cat-hmc/` format.

## Note: stale age key in .sops.yaml

The repo `.sops.yaml` has a stale age public key that doesn't match any private key on
this machine. Re-encryption used the working key directly (`SOPS_AGE_KEY_FILE`).
This is a latent issue — `.sops.yaml` should be updated to reflect the current key.

## Next

The top-level credential pattern (`providers.maas.admin_password` etc.) and the
`_tg_providers` / `_tg_providers_secrets` aggregation in `config_base` are being
replaced. Ansible will implement the same ancestor-merge algorithm as root.hcl,
resolving unit params by path prefix from the flat `config_params` structure.
