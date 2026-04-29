# Move Remaining Framework Config Files to config/

## Summary

Moved the three remaining deployment-specific framework config files
(`framework_config_mgr.yaml`, `framework_package_management.yaml`,
`framework_package_repositories.yaml`) from `infra/_framework-pkg/_config/` to
`config/`. Updated `packages.py` and `pkg-mgr/run` to use two-path lookup (same
pattern as the previous commit). `infra/_framework-pkg/_config/` now contains only
two files: `framework_packages.yaml` (bootstrap anchor) and `_framework-pkg.yaml`
(version file).

## Changes

- **`infra/_framework-pkg/_framework/_config-mgr/config_mgr/packages.py`** — added
  `_fw_cfg_path()` helper for two-path lookup; `load_framework_config_mgr()` uses it
  instead of hardcoding `_framework-pkg/_config/`
- **`infra/_framework-pkg/_framework/_pkg-mgr/run`** — added `_fw_cfg()` shell
  function; `PKG_REPOS_CFG` and `PKG_MGMT_CFG` now assigned via `_fw_cfg()`;
  `FRAMEWORK_PKGS_CFG` remains hardcoded (anchor file)
- **`config/`** — three files moved here from `infra/_framework-pkg/_config/`
- **`infra/_framework-pkg/_docs/framework/config-files.md`** — new section documenting
  discovery pattern, hardcoded paths table, and full location inventory for all
  framework config files

## Notes

`framework_packages.yaml` is the one file that will never move — it is the bootstrap
anchor that must be found before any discovery logic can run. This is documented in
`config-files.md` with a rationale.
