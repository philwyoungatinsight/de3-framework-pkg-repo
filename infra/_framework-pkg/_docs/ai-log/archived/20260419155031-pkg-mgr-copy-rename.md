# Add rename/copy commands to pkg-mgr and unit-mgr fixes

## Summary

Added `rename` and `copy` commands to `framework/pkg-mgr/run` for renaming or copying
packages (both local real-directory packages and imported symlink packages). Also renamed
`framework/manage-unit` → `framework/unit-mgr` and fixed a pre-existing relative import
bug in its `run` script. Added GUI dialog with Rename/Copy buttons in the Packages panel.

## Changes

- **`framework/pkg-mgr/run`** — added `_gcs_bucket`, `_check_gcs_locks_for_pkg`,
  `_migrate_pkg_gcs_state`, `_rename_pkg_yaml_keys` helpers; `_cmd_rename` (7-phase local,
  symlink-only for imported) and `_cmd_copy` (requires explicit `--skip-state` or
  `--with-state`); updated dispatch and usage text
- **`framework/pkg-mgr/README.md`** — added rename/copy rows to Commands table, examples,
  and new "## Rename and Copy" section with full phase documentation
- **`framework/unit-mgr/`** — renamed from `framework/manage-unit/`; bulk-replaced all
  references to `manage-unit`/`manage_unit` in run script, main.py, README.md
- **`framework/unit-mgr/run`** — fixed invocation from `python3 path/to/main.py` to
  `cd "${SCRIPT_DIR}" && exec python3 -m unit_mgr.main "$@"` so relative imports resolve
- **`homelab_gui.py`** — renamed `_find_manage_unit_run`/`_parse_manage_unit_json` helpers;
  added 8 AppState fields for pkg_op dialog; added 6 event handlers (`begin_pkg_rename`,
  `begin_pkg_copy`, `close_pkg_op`, `set_pkg_op_dst`, `set_pkg_op_state_flag`, `run_pkg_op`);
  added `_float_pkg_op_dialog()` modal component; added Rename/Copy buttons to `_pkg_card()`
  expanded header; wired dialog into main layout

## Root Cause (unit-mgr import fix)

`python3 framework/unit-mgr/unit_mgr/main.py` fails with
`ImportError: attempted relative import with no known parent package` because Python needs
the working directory to be the package root for `-m` invocation to resolve relative imports.

## Notes

- `_cmd_copy` requires the user to explicitly pass `--skip-state` or `--with-state` — no
  default — because silently inheriting GCS state would be operationally dangerous.
- SOPS file rename uses decrypt→edit-temp→`git mv`→`sops --encrypt --output`→`rm` pattern
  to honour the "never use `>` on .sops.yaml" rule and keep the rename atomic.
- unit-mgr is intentionally NOT used for whole-package renames: it triggers cross-package
  logic that splits config files, which is wrong at this scope.
