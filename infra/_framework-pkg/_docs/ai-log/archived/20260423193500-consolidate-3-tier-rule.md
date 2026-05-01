# feat(config-mgr): add fw-setting subcommand; consolidate 3-tier resolution

**Date**: 2026-04-23
**Plan**: consolidate-3-tier-rule (archived)

## What changed

### `config-mgr` — new `fw-setting` subcommand

`config-mgr fw-setting <name>` resolves a framework settings filename through the
canonical 3-tier lookup and prints the absolute path of the winning file:
  1. `$GIT_ROOT/config/<name>.yaml`                                    (per-dev override)
  2. `$_FRAMEWORK_CONFIG_PKG_DIR/_config/_framework_settings/<name>.yaml`  (consumer pkg)
  3. `$_FRAMEWORK_PKG_DIR/_config/_framework_settings/<name>.yaml`         (framework default)

Accepts the filename with or without `.yaml` suffix. Exits 1 if no file found.

- `config_mgr/main.py`: added `cmd_fw_setting`, imported `_fw_cfg_path` from packages,
  added `fw-setting` subparser, added dispatch entry
- The underlying `_fw_cfg_path()` already existed in `packages.py` — this exposes it
  as a CLI so bash scripts can use it without duplicating the logic

### `ramdisk-mgr` — removed both inline 3-tier bash blocks

Both setup mode and teardown mode previously had copy-pasted 9-line if/elif/else blocks.
Both replaced with:
```bash
RAMDISK_YAML="$("$_CONFIG_MGR" fw-setting framework_ramdisk)"
```

### `_utilities/python/framework_config.py` — added `fw_cfg_path()`

New public `fw_cfg_path(root, filename)` function (without leading underscore) available
to any Python tool that imports from the shared utilities. Same 3-tier logic as
`packages.py::_fw_cfg_path()` but accessible without depending on config-mgr internals.

### `unit-mgr/unit_mgr/main.py` — fixed `_read_framework_backend()`

Was reading from `$_FRAMEWORK_PKG_DIR/_config/framework_backend.yaml` — wrong path
(missing `_framework_settings/`) and no 3-tier resolution. Now calls `fw_cfg_path()`
from the shared utilities. Also updated two stale error messages that referenced the
old hardcoded path.

## Verification

```
config-mgr fw-setting framework_ramdisk
→ .../pwy-home-lab-pkg/_config/_framework_settings/framework_ramdisk.yaml  ✓ consumer wins

config-mgr fw-setting framework_ansible_inventory
→ .../_framework-pkg/_config/_framework_settings/framework_ansible_inventory.yaml  ✓ fallback to default

ramdisk-mgr --setup  →  "non-interactive context, skipping."  ✓
```
