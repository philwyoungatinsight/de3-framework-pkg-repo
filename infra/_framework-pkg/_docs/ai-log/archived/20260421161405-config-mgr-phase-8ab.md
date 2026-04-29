# config-mgr Phase 8A/8B — external consumers migrated

## What changed

Completed the remaining phases of the config overlay system. All sops --set calls and
direct config file reads in de3-runner external packages now go through config-mgr.

### Phase 8A — sops --set → config-mgr set --sops

**writer.py**: Extended `set_config_param` to support dot-separated nested keys in the
`key` argument (e.g. `token.id` → `config_params[path]["token"]["id"]`). Both SOPS and
plain YAML paths handle nesting. Required for proxmox token writes.

**de3-runner maas-pkg** (3 files):
- `sync-api-key/playbook.yaml`
- `configure-region/tasks/install-maas.yaml`
- `configure-server/tasks/install-maas.yaml`

All three had the same pattern: build `_pkg`, `_secrets_key`, `_cp_path`, `_secrets_file`
vars and call `sops --set '["<pkg>_secrets"]["config_params"][...] "<value>"' <file>`.
Replaced with: `config-mgr run set <_maas_cp_path> _provider_maas_api_key <value> --sops`.
config-mgr resolves the config_source chain to find the correct target secrets file
automatically — no need to construct the file path manually.

**de3-runner proxmox-pkg**:
- `configure-api-token.yaml`

Was writing to old nested format: `["proxmox-pkg_secrets"]["providers"]["proxmox"]["config_params"][path]["token"]["id"]`
in `proxmox-pkg/_config/proxmox-pkg_secrets.sops.yaml`.

Replaced with two `config-mgr run set <pve_config_path> token.id/token.secret --sops` calls.
config-mgr resolves proxmox-pkg's config_source (pwy-home-lab-pkg) and writes to the
deployment package's secrets file in the flat config_params format.

### Phase 8B — direct config file reads → $_CONFIG_DIR

**de3-runner maas-pkg** `fetch-maas-state/run`:
- `_MAAS_CONFIG="${_INFRA_DIR}/maas-pkg/_config/maas-pkg.yaml"` → `"${_CONFIG_DIR}/maas-pkg.yaml"`

**de3-runner de3-gui-pkg** `de3-gui/run`:
- `PKG_CONFIG_FILE="$_INFRA_DIR/de3-gui-pkg/_config/de3-gui-pkg.yaml"` → `"$_CONFIG_DIR/de3-gui-pkg.yaml"`

**local pwy-home-lab-pkg** `update-ssh-config/run`:
- `PKG_CONFIG="$_INFRA_DIR/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml"` → `"$_CONFIG_DIR/pwy-home-lab-pkg.yaml"`

config-mgr generate (run by set_env.sh) preserves all non-config_params top-level keys
(vars, config, ssh_config, etc.) in the output files, so all downstream reads continue
to work with the same key paths.

## Key design decisions

- config-mgr routes via config_source at write time — callers don't need to know which
  package is the config_source terminal. This is the primary value of Phase 8A.
- Dot-separated nested keys in `set_config_param` are purely additive — plain keys still
  work as before; dots trigger nested navigation only when present.
- Phase 8C (de3-runner's own infra/default-pkg/ framework copy) is NOT yet implemented.
  de3-runner standalone deployments still use the old code path. That is a separate scope.
