# Fix: Multiple bugs in pxe.maas.machine-entries wave

**Date:** 2026-04-09  
**Waves affected:** `pxe.maas.machine-entries` (wave 10)  
**Files modified:**  
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/capture-config-fact.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/capture-config-fact.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/discover-amt-ips.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/power-on-unenrolled-machines.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`
- `infra/maas-pkg/_tg_scripts/maas/sync-api-key/playbook.yaml`
- `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`

## Bug 1: `merged.skip` vs `merged._skip_on_build` (ROOT CAUSE)

### Root Cause

`capture-config-fact.yaml` (in both `configure-server` and `configure-machines`) discovers
unit paths by matching against keys in `_tg_providers['null']['config_params']` and filtering
out skipped units:

```jinja2
{%- if not (merged.skip | default(false)) -%}
```

The skip mechanism uses `_skip_on_build: true` (with underscore prefix), NOT `skip`. So
`merged.skip` was always falsy, meaning the filter never worked — example paths in
`maas-pkg/_stack/null/examples/` (which inherit `_skip_on_build: true` from their parent)
were NOT filtered out.

Since `maas-pkg/_stack/null/examples/pwy-homelab/configure-physical-machines` comes
alphabetically before `pwy-home-lab-pkg/_stack/null/pwy-homelab/configure-physical-machines`,
the example path was always selected as `_cpm_path`. The example had old `machine_paths`
with prefix `maas-pkg/_stack/...` instead of `pwy-home-lab-pkg/_stack/...`, so
`_tg_providers.maas.config_params[machine_path]` returned `{}` (no such key) for every
machine — merged dicts had only `path` and `name`, no `power_type`.

### Fix

Changed `merged.skip` → `merged._skip_on_build` in both capture-config-fact.yaml files.

## Bug 2: `selectattr('power_type', 'equalto', ...)` AttributeError in Ansible 2.20

### Root Cause

In Ansible 2.20, `selectattr('power_type', 'equalto', 'amt')` raises `AttributeError:
object of type 'dict' has no attribute 'power_type'` when any item in the list lacks the
`power_type` key (rather than treating it as non-matching, as older Ansible did).

This was triggered by Bug 1 above (merged dicts had no `power_type`). But even with Bug 1
fixed, items could theoretically lack `power_type` (e.g., if config is incomplete).

### Fix

Added `selectattr('power_type', 'defined')` guard before `selectattr('power_type', 'equalto', ...)`
in `discover-amt-ips.yaml` and `power-on-unenrolled-machines.yaml`.

## Bug 3: Wrong `machine_paths` prefix in `pwy-home-lab-pkg.yaml`

### Root Cause

`machine_paths` in `pwy-home-lab-pkg.yaml` referenced machines with prefix `maas-pkg/_stack/...`
instead of `pwy-home-lab-pkg/_stack/...`. These paths don't exist in
`_tg_providers.maas.config_params`, so merged dicts lacked all machine-specific config.

### Fix

Changed all `machine_paths` entries in both `configure-physical-machines` and the
test-playbooks config from `maas-pkg/_stack/...` to `pwy-home-lab-pkg/_stack/...`.

## Bug 4: SOPS key mismatch for MaaS API key

### Root Cause

`install-maas.yaml` (task "Store MaaS API key in SOPS secrets") wrote the API key to:
```
["pwy-home-lab-pkg_secrets"]["config_params"]["..."]["api_key"]
```

But `root.hcl` reads:
```hcl
API_KEY = try(local.unit_secret_params["_provider_maas_api_key"], "")
```

The mismatch caused the MaaS Terraform provider to authenticate with a stale key → 401 Unauthorized.
`sync-api-key/playbook.yaml` had the same bug.

### Fix

Changed `api_key` → `_provider_maas_api_key` in both `install-maas.yaml` and
`sync-api-key/playbook.yaml`. Also manually updated the SOPS file with the current MaaS API key
via `sops --set`.

## State after fixes

- Wave 9 (pxe.maas.seed-server): succeeded before these fixes were applied
- Machines commissioning: ms01-02, ms01-03, nuc-1 started commissioning in current run
- ms01-01: TF apply got 401 (SOPS updated too late); will succeed on next restart
- configure-physical-machines: will succeed on next restart with all bugs fixed
