# Fix package-system.md — sync doc to actual code

**Date**: 2026-04-21  
**Task**: Update `infra/default-pkg/_docs/framework/package-system.md` to match real code

## What was wrong

Four discrepancies between the doc and the actual implementation:

1. **Missing packages in "Current Packages" table** — `de3-gui-pkg` and `mikrotik-pkg`
   were present in `infra/` as symlinks but not listed in the doc.

2. **External package system undocumented** — All non-local packages come from the
   `de3-runner` external repo, pulled via `_ext_packages/` symlinks. The
   `framework_package_management.yaml` `linked_copy`/`local_copy` mechanism was
   not mentioned anywhere in the doc.

3. **`_setup/run` pattern showed arg-forwarding to `./seed` that doesn't exist** —
   The doc showed `case "${1:-}" in ... *) exec ./seed "$@"` but `default-pkg/run`
   (the only setup script) has no such logic. Removed the fictional case statement
   and noted what default-pkg actually installs.

4. **3-tier fallback described as identical for modules and provider templates** —
   Actually: modules use `.modules-root` sentinel at Tier 1 AND Tier 2;
   provider templates use plain file existence (no sentinel). Doc now documents
   each separately.

## Files changed

- `infra/default-pkg/_docs/framework/package-system.md` — all four fixes above
