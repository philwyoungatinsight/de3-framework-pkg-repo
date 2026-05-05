# Fix fw-repo-mgr pkg-mgr --sync shim: use caller's _FRAMEWORK_PKG_DIR

## Summary

Fixed a bug in `fw-repo-mgr`'s `build_repo()` step 4 where the temporary `set_env.sh`
shim used to run `pkg-mgr --sync` exported `_FRAMEWORK_PKG_DIR` pointing at the target
repo's `infra/_framework-pkg` symlink — which is dangling before the sync runs. Now the
shim bakes in the caller's `_FRAMEWORK_PKG_DIR` (always valid) so `pkg-mgr` can locate
`framework_packages.yaml` via its fallback config lookup.

## Changes

- **`infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr`** — read caller's
  `_FRAMEWORK_PKG_DIR` from `os.environ` and bake it into the shim instead of
  `$_SHIM_ROOT/infra/_framework-pkg`. The target repo's `infra/_framework-pkg`
  is a dangling symlink until `pkg-mgr --sync` completes, so the old shim caused
  pkg-mgr's config fallback lookup to fail on first build.

## Root Cause

`pkg-mgr` sources `set_env.sh` on startup (line 3) to get `_FRAMEWORK_PKG_DIR`.
The shim set this to `$_SHIM_ROOT/infra/_framework-pkg`, which is a symlink that
doesn't resolve until after `pkg-mgr --sync` creates it. pkg-mgr's `_fw_cfg()`
then falls back to `$_FRAMEWORK_PKG_DIR/_config/_framework_settings/` — a path
under the dangling symlink — causing it to fail to find `framework_packages.yaml`.

## Notes

- The caller is always running from a fully-synced repo (fw-repo-mgr itself runs
  inside a live framework environment), so `_FRAMEWORK_PKG_DIR` from the caller's
  env is always a valid, resolved path.
- `_FRAMEWORK_MAIN_PACKAGE_DIR` in the shim still correctly points at the target
  repo's embedded package dir (`$_SHIM_ROOT/infra/{config_pkg}`), which is
  physically present in the repo (not a symlink) — this path is valid pre-sync.
