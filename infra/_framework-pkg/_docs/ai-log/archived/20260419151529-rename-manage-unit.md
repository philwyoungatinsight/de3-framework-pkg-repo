---
date: 2026-04-19T15:15:29
task: rename-manage-unit
---

# Rename framework/manage-unit → framework/unit-mgr

Renamed the framework tool directory and Python package to match the `pkg-mgr` naming convention.

## What changed

- `framework/manage-unit/` → `framework/unit-mgr/` (git mv)
- `framework/unit-mgr/manage_unit/` → `framework/unit-mgr/unit_mgr/` (git mv)
- `framework/unit-mgr/run` — updated Python invocation path; also fixed pre-existing bug: changed from `python3 path/to/main.py` to `cd "${SCRIPT_DIR}" && python3 -m unit_mgr.main` so relative imports resolve correctly
- `framework/unit-mgr/unit_mgr/main.py` — updated module docstring and `argparse` `prog` name
- `framework/unit-mgr/README.md` — bulk-replaced all `manage-unit`/`manage_unit` occurrences
- `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — renamed helper functions `_find_manage_unit_run` → `_find_unit_mgr_run`, `_parse_manage_unit_json` → `_parse_unit_mgr_json`, and updated all call sites, docstrings, path strings, and comments

## Verification

- No remaining `manage-unit` or `manage_unit` references in live code
- `python3 -m py_compile homelab_gui.py` passes
- `framework/unit-mgr/run` prints correct `usage: unit-mgr ...` help text
