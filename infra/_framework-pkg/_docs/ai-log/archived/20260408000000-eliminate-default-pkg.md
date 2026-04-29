# Eliminate default-pkg: distribute to null-pkg, framework/, pwy-home-lab-pkg

**Date:** 2026-04-08
**Task:** Refactor — eliminate `infra/default-pkg` by distributing its contents to better homes.

## What was done

### Step 1 — `config/framework.yaml`
Moved the framework-level keys (`backend`, `ansible_inventory`, `ssh_config`, `clean_all`, `pre_apply_unlock`, `external_capabilities`) from `infra/default-pkg/_config/default-pkg.yaml` into a new `config/framework.yaml` file with top-level key `framework:`.

### Step 2 — Updated framework config readers
Four files that hardcoded the default-pkg config path were updated:
- **`run`** (Python, repo root): now discovers `config/framework.yaml` first, falls back to `infra/*/_config/framework.yaml`. Reads `framework` key instead of `default-pkg`. `setup_packages()` now runs `null-pkg/_setup/run` first.
- **`root.hcl`**: `_framework_cfg` now reads from `config/framework.yaml`[`framework`].
- **`framework/clean-all/run`**: `_load_merged_config()` now reads `config/framework.yaml` for framework settings. `_find_stack_config()` updated.
- **`framework/generate-ansible-inventory/generate_ansible_inventory.py`**: `resolve_config_path()` now returns the framework.yaml path.

### Step 3 — `infra/null-pkg/`
Created new `infra/null-pkg/` package:
- `_providers/null.tpl` and `_providers/null.entry.tpl` — null provider template (copied from default-pkg)
- `_setup/run` — tool setup script (copied from default-pkg, `_setup_dev_workstation` and `_setup_ssh_config` functions removed)
- `_config/null-pkg.yaml` — minimal config with skip: true on example units

### Step 4 — `root.hcl` module/provider fallback updates
- Provider template last-resort: `default-pkg/_providers/` → `null-pkg/_providers/`
- Extra providers entry.tpl last-resort: `default-pkg/_providers/` → `null-pkg/_providers/`
- Module resolution: null provider and final fallback now use `framework/_modules/` instead of `default-pkg/_modules/`
- Added `_modules_dir_resolved` helper that normalises legacy `"default-pkg/_modules"` override values to `framework/_modules` — preserves backward compat for existing YAML config_params entries

### Step 5 — `framework/_modules/`
Moved shared modules via `git mv`:
- `infra/default-pkg/_modules/null_resource__run-script/` → `framework/_modules/`
- `infra/default-pkg/_modules/null_resource__ssh-script/` → `framework/_modules/`
- `infra/default-pkg/_modules/.modules-root` → `framework/_modules/`

### Step 6 — pwy-home-lab-pkg absorbs local.updates
- `git mv infra/default-pkg/_tg_scripts/local/ infra/pwy-home-lab-pkg/_tg_scripts/local/`
- `local.updates` wave definition moved to `pwy-home-lab-pkg.yaml` under `waves:`
- Deleted the duplicate example unit `infra/default-pkg/_stack/` (the real unit is at `pwy-home-lab-pkg/_stack/null/pwy-homelab/local/update-ssh-config/`)

### Step 7 — check-maas-machines to maas-pkg
- `git mv infra/default-pkg/_wave_scripts/common/ infra/maas-pkg/_wave_scripts/common/`

### Step 8 — Delete remaining default-pkg content
Removed: `configure-dev-host/`, `update-ssh-config/`, `_providers/null.tpl`, `_providers/null.entry.tpl`, `_setup/run`, `_config/default-pkg.yaml`.

### Step 9 — CLAUDE.md
Updated `check-maas-machines` path reference from `wave-scripts/default/common/` to `infra/maas-pkg/_wave_scripts/common/`.

## Verification
`python3 run --list-waves` outputs all 20 waves correctly, including `local.updates`.
