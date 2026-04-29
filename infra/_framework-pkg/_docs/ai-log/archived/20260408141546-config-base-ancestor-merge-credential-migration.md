# 2026-04-08 config_base ancestor-merge + credential migration

## Summary

Redesigned Ansible `config_base` to read from top-level `config_params` (same
algorithm as `root.hcl`), added `ancestor_merge` filter plugin, migrated all
top-level credentials from SOPS files into path-keyed `config_params`, and updated
all scripts to use the new pattern.

## Problem

Two related bugs:

1. **config_base was broken**: All packages migrated their data to top-level
   `config_params` (e.g. `maas-pkg.config_params`), but `config_base` was still
   reading from `providers.<prov>.config_params` (nested inside the providers key).
   This made `_tg_providers.*` and `_tg_providers_secrets.*` empty for all providers.

2. **Top-level credentials existed only for Ansible**: SOPS secrets files had top-level
   keys like `providers.maas.{admin_password, api_key, db_password, machine_deploy_password,
   proxmox_power}` and `providers.unifi.{username, password}` that were not in
   `config_params`. These had no path-based ancestry — they were accessed as a flat
   dict merged over the unit config, which was a design inconsistency.

## Changes

### New filter plugin: `utilities/ansible/roles/config_base/filter_plugins/lab_config.py`

Adds `ancestor_merge(path, config_params)` Jinja2 filter — mirrors the HCL logic
in `root.hcl`:
- Generate all ancestor path prefixes for `path` (top-down)
- Merge each matching `config_params` entry (deeper overrides shallower)

### config_base redesign: `utilities/ansible/roles/config_base/tasks/main.yaml`

New aggregation tasks replace the old `_tg_providers` / `_tg_providers_secrets` tasks:

| New fact | Source |
|---|---|
| `_all_config_params` | Top-level `config_params` from all `*-pkg` vars (with `${var}` interpolation) |
| `_all_secret_params` | Top-level `config_params` from all `*-pkg_secrets` vars (+ old `providers.<prov>.config_params` for backward compat) |
| `_tg_providers` | `_all_config_params` split by `_provider` (via ancestor-merge) |
| `_tg_providers_secrets` | `_all_secret_params` split by `_provider` |

Scripts continue using `_tg_providers.maas.config_params[path]` unchanged.
New scripts use `path | ancestor_merge(_all_config_params)` for full unit-merged params.

### SOPS file restructuring

All four secrets files migrated from `providers.<prov>.*` to top-level `config_params`:

| File | Change |
|---|---|
| `maas-pkg` | `providers.maas.{api_key,admin_password,db_password,machine_deploy_password,proxmox_power}` → `config_params` at correct paths; stale test `machine_deploy_password` removed |
| `proxmox-pkg` | `providers.proxmox.config_params` → top-level `config_params` |
| `mesh-central-pkg` | `providers.null.config_params` → top-level `config_params` |
| `unifi-pkg` | `providers.unifi.{username,password}` → `config_params.unifi-pkg/_stack/unifi/examples/pwy-homelab` |

Credential placement:
- `api_key` at the maas provider root (`*/_stack/maas/<env>`) — inherited by all machine paths
- `admin_password`, `db_password`, `machine_deploy_password`, `proxmox_power` at the
  configure-server null path (`*/_stack/null/<env>/maas/configure-server`)
- UniFi `username`/`password` at the unifi provider root (`*/_stack/unifi/<env>`)

### Script updates

**`maas/configure-server/tasks/capture-config-fact.yaml`**:
- Discovers `_cs_path` dynamically (non-skipped path matching `.*/maas/configure-server$`)
- `maas_config` now built via `ancestor_merge` on both public and secret params
- Derives `_maas_cp_path` (maas provider root) for SOPS api_key writes

**`maas/configure-server/tasks/install-maas.yaml`** and **`sync-api-key/playbook.yaml`**:
- SOPS `--set` path updated from `providers.maas.api_key` to
  `config_params[_maas_cp_path].api_key` — derived dynamically from `_cs_path`

**`maas/configure-machines/tasks/capture-config-fact.yaml`**:
- `_cs_path` and `_cpm_path` discovered dynamically (non-skipped matches)

**`maas-server-seed-test`**: MaaS IP/port discovered dynamically from the maas
provider root (entry with `maas_server_ip` defined) instead of hardcoded path.

**`maas-machines-test` and `maas-machines-precheck`**:
- Wave name fixed: `on_prem.maas.machines` → `pxe.maas.machine-entries`
- Filesystem path fixed: `$_INFRA_DIR/cat-hmc/...` → `$_INFRA_DIR/{{ item.path }}`
  (using `path` field now included in `_wave_machines` entries)

**`image-maker/build-images/tasks/capture-config-fact.yaml`**:
- MaaS config discovered dynamically (entry with `maas_server_ip` defined)

**`unifi verify-unifi-networking` and `network-validate-config`** capture-config-fact:
- UniFi root path discovered dynamically (entry with `_provider_api_url` defined)
- Sub-paths (device, network, port-profile) discovered by path suffix match
- `_unifi_secrets` from `_tg_providers_secrets.unifi.config_params[root_path]`

**`mesh-central install` and `update`** playbooks:
- `_mc_cs_path` discovered dynamically (non-skipped `.*/mesh-central/configure-server$`)
- Config built via `ancestor_merge` on both public and secret params
