# config-mgr implementation

## What changed

Implemented the config overlay system designed in `infra/default-pkg/_docs/ai-plans/config-overlay-options.md`.

### Phase 1 — `config_source` declarations
- Added `config_source: pwy-home-lab-pkg` to all 11 external packages in `framework_packages.yaml`.

### Phase 2 — config-mgr tool (new)
- Created `infra/default-pkg/_framework/_config-mgr/` with Python package `config_mgr`:
  - `packages.py` — load framework_packages.yaml, resolve config_source chains (cycle detection)
  - `merger.py` — interleave/source_only merge strategies
  - `generator.py` — generate pre-merged, pre-decrypted output into `$_CONFIG_DIR`
  - `writer.py` — write config_params to correct source file via config_source routing
  - `sops.py` — SOPS subprocess helpers
  - `main.py` — argparse CLI: generate, get, set, set-raw, move subcommands
- Two entry points: `run` (sources set_env.sh) and `generate` (does NOT source set_env.sh, avoids infinite recursion)
- Key design: output files are filtered to only contain config_params keys belonging to each package (`pkg_name/` prefix). No cross-package key pollution.

### Phase 3 — set_env.sh
- Added `export _CONFIG_DIR="$_DYNAMIC_DIR/config"` 
- Added `"$_CONFIG_DIR"` to `mkdir -p` in `_set_env_create_dirs`
- Added `"$_FRAMEWORK_DIR/_config-mgr/generate" >&2` to `_set_env_run_startup_checks` (blocking, before validate-config)

### Phase 4 — validate-config.py
- Added RULE 6: config_source chain validation — checks existence and cycle-freedom for all config_source declarations in framework_packages.yaml.

### Phase 5 — root.hcl
- Replaced `sops_decrypt_file()` calls with plain `yamldecode(file(...))` reads from `$_CONFIG_DIR`
- Package config path: `${_config_dir}/${p_package}.yaml`
- Secrets path: `${_config_dir}/${p_package}.secrets.yaml` (plain YAML, mode 600)
- `_config_dir = get_env("_CONFIG_DIR")` — errors if set_env.sh was not sourced

### Phase 6 — unit-mgr
- Added `_read_framework_packages()` and `_resolve_config_source()` to `main.py`
- Phase 3 (Package detection) now resolves config_source so config_params reads/writes go to the correct file

### Phase 7 — glob consumers
- `generate_ansible_inventory.py`: replaced `infra/*/_config/*.yaml` glob with `$_CONFIG_DIR/*.yaml`; updated config loading to read flat `config_params` format (was incorrectly looking for old `providers.*` format)
- `config_base/tasks/main.yaml`: replaced `find infra/*/_config/` with `find $_CONFIG_DIR`; removed `community.sops.load_vars` (config-mgr pre-decrypts secrets); simplified to two `include_vars` loops

### Phase 8D — pkg-mgr
- Added `_maybe_regenerate_config()` helper at dispatch; calls `config-mgr generate` after sync, import, remove, rename, copy commands.

## Key design decisions

- Output files filtered by package prefix: `$_CONFIG_DIR/proxmox-pkg.yaml` only contains `proxmox-pkg/` prefixed config_params. This prevents cross-package pollution and ensures no duplicate keys across output files.
- set_env.sh calls `generate` entry point (not `run`) to avoid circular source.
- SOPS errors are hard failures — config-mgr exits non-zero, set_env.sh propagation blocks the shell source.
- Mtime manifest in `$_CONFIG_DIR/.manifest` for fast stale detection on every set_env.sh source.

## Phase 8A/8B (external de3-runner changes) not yet implemented
- 4x `sops --set` calls in maas-pkg and proxmox-pkg tg-scripts need migration to `config-mgr set --sops`
- 3x direct Python reads of source config files need migration to `$_CONFIG_DIR/<pkg>.yaml`
- These require changes to the de3-runner repo.
