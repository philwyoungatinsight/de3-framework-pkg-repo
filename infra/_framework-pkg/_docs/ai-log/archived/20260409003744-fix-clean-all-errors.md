# Fix make clean-all errors

## Summary

Debugged and fixed 7 distinct errors that caused `make clean-all` to fail or
emit errors. All five `make clean-all` iterations now exit cleanly with zero
errors.

## Fixes Applied

### 1. root.hcl — duplicate `exclude` blocks (Terragrunt v0.99.4 limit)

The previous session added three `exclude` blocks for `_wave_skip`,
`_skip_on_build`, and `_skip_on_clean`. Terragrunt only allows one.

- Consolidated into a single `exclude { if = ...; actions = ["all"] }`
- `_wave_skip` and `_skip_on_build` → exclude all actions (unit fully transparent)
- `_skip_on_clean` unit-level protection relies on wave-level skip (Python
  orchestrator skips the whole wave); this is documented in root.hcl comment
- Also fixed duplicate `locals` block that was introduced alongside the extra
  exclude blocks

### 2. root.hcl — missing `_cfg` alias

`all-config` units (e.g. `aws-pkg/examples/.../all-config/terragrunt.hcl`)
reference `include.root.locals._cfg` to upload package config as JSON to cloud
storage. This alias was dropped in the `default-pkg` elimination refactor.

Restored as `_cfg = local._package_cfg` (public config only; secrets excluded).

### 3. pwy-home-lab-pkg.yaml — missing `_tg_scripts_dir` on null proxmox path

`pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox` units (`configure-proxmox`,
`configure-proxmox-post-install`) use scripts from `proxmox-pkg/_tg_scripts/`
but `_tg_scripts_dir` was only set on the `_stack/proxmox/` path, not `_stack/null/`.

Added `_tg_scripts_dir: proxmox-pkg/_tg_scripts` at
`pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox`.

### 4. proxmox-pkg `_proxmox_deps.hcl` — stale dependency path

`_proxmox_deps.hcl` in `proxmox-pkg/_stack/proxmox/examples/pwy-homelab/`
pointed to `proxmox-pkg/_stack/null/pwy-homelab/proxmox/configure-proxmox`
which doesn't exist. Fixed to `proxmox-pkg/_stack/null/examples/pwy-homelab/...`.

### 5. maas-pkg force-release — SSH failure on unreachable MaaS

`infra/maas-pkg/_tg_scripts/maas/force-release/run` used `set -euo pipefail`
and SSH'd directly to the MaaS server. During clean-all (no MaaS running),
SSH fails and the before_hook blocks terraform destroy.

Added a reachability pre-check: if the MaaS host is unreachable, log and
exit 0 (best-effort in destroy path per CLAUDE.md convention).

### 6. pwy-home-lab-pkg.yaml — missing `_provider_proxmox_endpoint` on ms01-01

`pve-nodes/ms01-01` (cloud_public_ip: 10.0.10.116) had no
`_provider_proxmox_endpoint`. Its `isos/ubuntu-24` and `snippets/guest-agent`
units failed with "expected endpoint url to not be empty".

Added `_provider_proxmox_endpoint: https://10.0.10.116:8006`.

### 7. Config YAML cleanup

- **null-pkg.yaml**: `config_params` was incorrectly nested under
  `providers."null".config_params`; moved to top-level `null-pkg.config_params`
- **demo-buckets-example-pkg.yaml**: removed stale `cat-1/gcp`, `cat-2/gcp`,
  `cat-3/aws` entries (old path format pre-dating `<pkg>/_stack/` convention);
  these entries also used non-underscore `provider: gcp/aws` keys
