# pkg-mgr: remove local_overrides

## What changed

Removed the `local_overrides` feature from pkg-mgr. The feature allowed per-developer
git_ref overrides in `framework_package_management.yaml`, but added complexity without
sufficient benefit.

- Deleted `_read_local_git_ref` helper function
- `_cmd_sync`: removed local override application; uses `git_ref` from config directly
- `_cmd_clean` orphan detection: simplified Python block — no longer reads local_overrides
- `_cmd_status`: removed all `local_overrides` / `has_local` / `(local)` logic from both
  repos table and packages table
- `framework_package_management.yaml`: removed `local_overrides` comment block
- `README.md`: removed Local override section

## Files modified

- `infra/default-pkg/_framework/_pkg-mgr/run`
- `infra/default-pkg/_config/framework_package_management.yaml`
- `infra/default-pkg/_framework/_pkg-mgr/README.md`
- `infra/default-pkg/_config/default-pkg.yaml` — bumped to 1.2.2
