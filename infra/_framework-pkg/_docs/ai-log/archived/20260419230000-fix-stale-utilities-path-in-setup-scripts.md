# Fix stale `utilities/python/install-requirements.sh` path in setup scripts

**Date**: 2026-04-19
**Session**: fix-stale-utilities-path-in-setup-scripts

## What was done

Fixed three scripts that still referenced the old repo-root `$GIT_ROOT/utilities/python/install-requirements.sh` path, which no longer exists. The script was consolidated into `infra/default-pkg/_utilities/` (and later moved to `infra/default-pkg/_framework/_utilities/`) during earlier migrations. `set_env.sh` already exports `$_UTILITIES_DIR` pointing to the correct location, so these scripts can use it directly.

## Files changed

- `infra/de3-gui-pkg/_application/de3-gui/run` — `_deps()` function uses `$_UTILITIES_DIR/python/install-requirements.sh`
- `infra/default-pkg/_setup/run` — `_INSTALL_REQS` uses `$_UTILITIES_DIR/python/install-requirements.sh`
- `infra/de3-gui-pkg/_setup/run` — `_INSTALL_REQS` uses `$_UTILITIES_DIR/python/install-requirements.sh`
- `README.md` — updated path reference to reflect current location

## Root cause

The `utilities/` directory at the repo root was consolidated into `infra/default-pkg/_utilities/` (now `_framework/_utilities/`) but these three scripts were not updated during that migration. The breakage manifested as `./run -A de3-gui` failing because `make` calls `./run --build` → `_deps` → missing path.

## No rules violated
