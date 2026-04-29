# Add _DEFAULT_PKG_DIR / _FRAMEWORK_DIR / _WRITE_EXIT_STATUS env vars

**Date**: 2026-04-19
**Session**: add-default-pkg-env-vars

## Summary

Added `_DEFAULT_PKG_DIR`, `_FRAMEWORK_DIR`, and `_WRITE_EXIT_STATUS` env vars to `set_env.sh`.
Updated `set_env.sh` to derive `_UTILITIES_DIR`, `_CONFIG_TMP_DIR`, `_GENERATE_INVENTORY`, and the
`_ephemeral/run` invocation from these new vars instead of hardcoded paths.

Fixed `root.hcl` `after_hook "exit_status_write"` to use `get_env("_WRITE_EXIT_STATUS")` instead of
`get_repo_root()` — this fixes the hook path resolution bug that showed `./default-pkg/...` instead
of an absolute path.

Updated all Python and bash scripts that hardcoded `infra/default-pkg/` to prefer the `_DEFAULT_PKG_DIR`
(or `_FRAMEWORK_DIR`) env var with structural fallback, ensuring paths stay correct regardless of where
the framework directory is mounted.

## Files changed

- `set_env.sh` — added `_DEFAULT_PKG_DIR`, `_FRAMEWORK_DIR`, `_WRITE_EXIT_STATUS`; derived downstream vars from them
- `root.hcl` — `exit_status_write` hook uses `get_env("_WRITE_EXIT_STATUS")` for absolute path
- `infra/default-pkg/_framework/_ephemeral/run` — use `$_FRAMEWORK_DIR`
- `infra/default-pkg/_framework/_pkg-mgr/run` — use `$_FRAMEWORK_DIR` / `$_DEFAULT_PKG_DIR`
- `infra/default-pkg/_framework/_clean_all/run` — use `$_FRAMEWORK_DIR`
- `infra/default-pkg/_framework/_human-only-scripts/purge-gcs-status/run` — use `$_FRAMEWORK_DIR`
- `infra/default-pkg/_framework/_unit-mgr/unit_mgr/main.py` — prefer `_DEFAULT_PKG_DIR` env var
- `infra/default-pkg/_framework/_utilities/bash/gcs-status.sh` — use `$_FRAMEWORK_DIR`
- `infra/default-pkg/_framework/_utilities/python/framework_config.py` — prefer `_FRAMEWORK_DIR` env var
- `infra/default-pkg/_framework/_utilities/python/gcs_status.py` — prefer `_FRAMEWORK_DIR` env var
- `infra/default-pkg/_framework/_utilities/python/validate-config.py` — prefer `_DEFAULT_PKG_DIR` env var
