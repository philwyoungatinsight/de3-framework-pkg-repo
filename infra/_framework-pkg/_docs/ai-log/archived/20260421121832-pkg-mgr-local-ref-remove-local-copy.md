# pkg-mgr: local_git_ref override + remove local_copy

## What changed

Plan: `pkg-mgr-source-local-ref.md`

### local_git_ref (local_overrides)

Added `local_overrides:` block support in `framework_package_management.yaml`.
Per-developer `git_ref` override for any package — affects clone directory path and
checkout without touching committed config.

- New `_read_local_git_ref <pkg>` helper reads `local_overrides.<pkg>.git_ref` from mgmt YAML
- `_cmd_sync`: computes `effective_ref = local_override or git_ref`; passes it to
  `_ensure_cloned` and `_create_symlink`
- `_cmd_clean` orphan detection: resolves local overrides so locally-overridden clones are
  not pruned as orphans
- `_cmd_status`: repos table and packages table both show `(local)` suffix on ref when an
  override is active; local overrides highlighted in yellow

### Remove local_copy

- Deleted `_repo_inclusion_method` helper (~20 lines)
- Deleted `_is_commit_sha` helper (only used in shallow-clone path)
- `_ensure_cloned` rewritten: only linked_copy logic remains; errors immediately if
  `external_package_dir` is unset; both migration blocks removed (~60 lines deleted)
- `repo_method()` in status simplified to always return `linked_copy`
- `default_inclusion_method` ignored; config header no longer shows it
- Config header now warns in red if `external_package_dir` is not set

## Files modified

- `infra/default-pkg/_framework/_pkg-mgr/run`
- `infra/default-pkg/_config/framework_package_management.yaml`
- `infra/default-pkg/_framework/_pkg-mgr/README.md`
- `infra/default-pkg/_config/default-pkg.yaml` — bumped to 1.2.0
