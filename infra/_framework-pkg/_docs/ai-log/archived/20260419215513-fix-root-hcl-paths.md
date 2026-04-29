# Fix: root.hcl stale paths after consolidation into default-pkg

**Date**: 2026-04-19
**File**: `root.hcl`

## Summary

Fixed two stale path references in `root.hcl` that still pointed to old top-level
`config/` and `utilities/` directories after those trees were consolidated into
`infra/default-pkg/`.

## Changes

1. **Line ~73 — `_fw_sec_path`**:
   - Old: `${local.stack_root}/config/framework_secrets.sops.yaml`
   - New: `${local.stack_root}/infra/default-pkg/_config/framework_secrets.sops.yaml`

2. **Line ~416 — `after_hook "exit_status_write"` execute path**:
   - Old: `${get_repo_root()}/utilities/tg-scripts/write-exit-status/run`
   - New: `${get_repo_root()}/infra/default-pkg/_utilities/tg-scripts/write-exit-status/run`

## Impact

Without these fixes, any terragrunt run would either fail to decrypt framework
secrets (path miss on `_fw_sec_path`) or fail the post-apply hook trying to execute
a non-existent `write-exit-status/run` script.
