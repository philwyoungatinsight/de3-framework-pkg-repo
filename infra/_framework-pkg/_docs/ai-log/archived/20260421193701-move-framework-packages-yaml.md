# Move framework_packages.yaml to config/

## Summary

Moved `framework_packages.yaml` from `infra/_framework-pkg/_config/` to `config/`.
The prior "bootstrap anchor" rationale was stale — `find_framework_config_dirs()` does
not read `framework_packages.yaml` to discover dirs; it only needs `$_FRAMEWORK_PKG_DIR`
and git root, both already known. The two-path lookup works fine here.
`infra/_framework-pkg/_config/` now contains only `_framework-pkg.yaml`.

## Changes

- **`infra/_framework-pkg/_framework/_config-mgr/config_mgr/packages.py`** —
  `load_framework_packages()` now uses `_fw_cfg_path()` instead of hardcoded path
- **`infra/_framework-pkg/_framework/_pkg-mgr/run`** — `FRAMEWORK_PKGS_CFG` now
  assigned via `_fw_cfg()` helper
- **`config/framework_packages.yaml`** — moved from `infra/_framework-pkg/_config/`
- **`infra/_framework-pkg/_docs/framework/config-files.md`** — updated: removed
  "hardcoded paths" table (no longer any), updated location inventory
