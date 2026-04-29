# AI Log: Framework Config Files in Named Package

**Date:** 2026-04-21  
**Plan:** `framework-config-in-package` (archived)

## What Was Done

Implemented three-tier framework config lookup, enabling all deployment-specific
`framework_*.yaml` files to live in a named package's `_config/` directory rather
than in the top-level `config/`.

### New file

- `config/_framework.yaml` — declares which package holds framework config:
  ```yaml
  _framework:
    config_package: pwy-home-lab-pkg
  ```

### Modified files

- `set_env.sh` — reads `config/_framework.yaml`; exports `_FRAMEWORK_CONFIG_PKG`
  and `_FRAMEWORK_CONFIG_PKG_DIR`; pre-existing env var wins (dev/CI override);
  updated `_fw_backend` block to three-path check
- `framework_config.py` — `find_framework_config_dirs()` now returns three dirs:
  `_framework-pkg/_config/` → `_FRAMEWORK_CONFIG_PKG/_config/` → `config/`
- `packages.py` — `_fw_cfg_path()` updated to three-path lookup
- `pkg-mgr/run` — `_fw_cfg()` shell function updated to three-path lookup
- `root.hcl` — `_fw_backend_path` updated to three-tier `fileexists()` chain
- `config-files.md` — updated to document three-tier lookup and `_framework.yaml` anchor
- `_framework-pkg.yaml` — bumped to version 1.4.6

### Verified

- `_FRAMEWORK_CONFIG_PKG=pwy-home-lab-pkg` after sourcing `set_env.sh`
- `_FRAMEWORK_CONFIG_PKG_DIR=.../infra/pwy-home-lab-pkg` correctly derived
- Three dirs returned by `find_framework_config_dirs()`
- `pkg-mgr --status` works correctly
- Pre-existing `_FRAMEWORK_CONFIG_PKG` env var overrides `_framework.yaml`
