# Standardize set_env.sh Bootstrap Calls Across Framework Scripts

## Summary

Documented the definitive four-category standard for how framework scripts source
`set_env.sh`, and fixed the four scripts that deviated from it: `ramdisk-mgr`,
`write-exit-status`, `sops-mgr`, and `clean-all`. The standard was established during
the bootstrap env-var refactor but had not been fully back-applied to these scripts.

## Changes

- **`infra/_framework-pkg/_docs/set-env-bootstrap-standard.md`** — created; defines
  categories A/B/C/D with copy-paste examples and a quick-reference table
- **`_ramdisk-mgr/ramdisk-mgr`** — renamed `_SCRIPT_DIR` → `SCRIPT_DIR`; moved
  `. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"` to top of script (before argument parsing);
  removed redundant `GIT_ROOT=...` + `source set_env.sh` lines from setup and teardown
  mode blocks
- **`tg-scripts/write-exit-status/write-exit-status`** — replaced bare
  `git rev-parse --show-toplevel` with Category B pattern: `SCRIPT_DIR` + `${_FRAMEWORK_PKG_DIR:?}` guard
- **`_sops-mgr/sops-mgr`** — updated `_source_env()` to check `_FRAMEWORK_PKG_DIR`
  first before falling back to `git rev-parse` (Category D)
- **`_clean_all/clean-all`** — updated `_git_root()` to check `_FRAMEWORK_PKG_DIR`
  first before falling back to `git rev-parse` (Category D)

## Notes

- `ramdisk-mgr` sourcing `set_env.sh` at top is safe because `set_env.sh` is idempotent
  (returns immediately if already sourced via the `_FRAMEWORK_PKG_DIR` + `_UTILITIES_DIR` guard)
- After all fixes, `grep -r "git rev-parse" infra/_framework-pkg/_framework/` returns zero hits
