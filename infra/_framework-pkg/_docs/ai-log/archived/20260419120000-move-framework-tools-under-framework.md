# Move framework tools under infra/default-pkg/_framework/

**Date**: 2026-04-19

## What was done

Moved 6 directories from `infra/default-pkg/` into `infra/default-pkg/_framework/` using `git mv`:

- `_clean_all`         → `_framework/_clean_all`
- `_ephemeral`         → `_framework/_ephemeral`
- `_generate-inventory`→ `_framework/_generate-inventory`
- `_pkg-mgr`           → `_framework/_pkg-mgr`
- `_unit-mgr`          → `_framework/_unit-mgr`
- `_utilities`         → `_framework/_utilities`

## Files already updated (pre-migration)

The following files already had the new `_framework/` paths before the move:

- `set_env.sh` — `_UTILITIES_DIR`, `_GENERATE_INVENTORY`, and `_EPHEMERAL_DIR` already pointed to `_framework/`
- `run` (repo root) — `GENERATE_INVENTORY`, `NUKE_ALL`, `INIT_SH` already pointed to `_framework/`
- `CLAUDE.md` — Reference section already listed `infra/default-pkg/_framework/` as the tool location
- `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — `_PKG_MGR` (line 3001) and `_find_unit_mgr_run()` (line 10550) already used `_framework/` paths

## File fixed during migration

- `infra/default-pkg/_framework/_ephemeral/run` — Had stale `infra/default-pkg/_ephemeral/ephemeral.sh` path; updated to `infra/default-pkg/_framework/_ephemeral/ephemeral.sh`

## Result

All framework tools now live under `infra/default-pkg/_framework/` as documented in CLAUDE.md and the `_framework/README.md`.
