# Organize Framework Config Files — Deployment Overrides via `config/`

## Summary

Moved 11 deployment-specific `framework_*.yaml` files (plus `waves_ordering.yaml`,
`gcp_seed.yaml`, `gcp_seed_secrets.sops.yaml`) from `infra/_framework-pkg/_config/` to
`config/` at the git root. Extended `load_framework_config()` to search both the framework
dir and `config/` so all tools find files in their new location. No new env vars; no
deployment package names hardcoded in framework code.

## Changes

- **`infra/_framework-pkg/_framework/_utilities/python/framework_config.py`** — added
  `find_framework_config_dirs()` returning `[_framework-pkg/_config/, config/]`; updated
  `load_framework_config()` to accept a list of dirs (later overrides earlier); kept
  `find_framework_config_dir()` as backward-compat wrapper
- **`infra/_framework-pkg/_framework/_git_root/run`** — updated import and call to use
  `find_framework_config_dirs()`
- **`infra/_framework-pkg/_framework/_clean_all/run`** — replaced inline framework config
  glob with `load_framework_config(find_framework_config_dirs(GIT_ROOT))`; added sys.path
  setup to import from `_utilities/python`
- **`infra/_framework-pkg/_framework/_utilities/python/validate-config.py`** — updated to
  use `find_framework_config_dirs()`
- **`infra/_framework-pkg/_framework/_git_root/root.hcl`** — `framework_backend.yaml` now
  found via `fileexists()` two-path lookup: `config/` first, `_framework-pkg/_config/` fallback
- **`infra/_framework-pkg/_framework/_git_root/set_env.sh`** — `_GCS_BUCKET` export now
  checks `config/framework_backend.yaml` first, falls back to old path
- **`infra/_framework-pkg/_framework/_pkg-mgr/run`** — `_gcs_bucket()` function updated
  with the same two-path lookup
- **`config/`** — 11 files moved here from `infra/_framework-pkg/_config/`:
  `framework_backend.yaml`, `framework_ansible_inventory.yaml`, `framework_clean_all.yaml`,
  `framework_ephemeral_dirs.yaml`, `framework_external_capabilities.yaml`,
  `framework_manager.yaml`, `framework_pre_apply_unlock.yaml`,
  `framework_validate_config.yaml`, `gcp_seed.yaml`, `gcp_seed_secrets.sops.yaml`,
  `waves_ordering.yaml`
- **`infra/_framework-pkg/_config/_framework-pkg.yaml`** — bumped to 1.4.3

## Notes

The `waves_ordering.yaml` file is not a `framework_*.yaml` file so it is not loaded by
`load_framework_config()` — it continues to be discovered directly by the `run` script
via its existing `config/waves_ordering.yaml` check (already handled before this change).

`_framework-pkg/_config/` now contains only 5 files: `_framework-pkg.yaml`,
`framework_config_mgr.yaml`, `framework_package_management.yaml`,
`framework_package_repositories.yaml`, and `framework_packages.yaml`.
