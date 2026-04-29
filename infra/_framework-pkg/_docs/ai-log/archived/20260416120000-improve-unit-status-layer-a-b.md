# improve-unit-status: Layer A + B implementation

## Summary

Implemented the first two layers of the `improve-unit-status-1` plan:
- **Layer A**: Generic exit-status hook in `root.hcl` — captures ok/fail for every apply/destroy in all contexts
- **Layer B**: GUI Tier 0 consumer — reads exit-status YAMLs instead of calling `gsutil cat`

Also cleaned up the unit-state.yaml schema (v2): removed `resources_count`, added `details`, `maas_phase`, `maas_message`, `maas_hostname` fields.

## Changes

### `root.hcl` — two new `after_hook` entries in a new `terraform {}` block

Two-hook pattern at the end of `root.hcl`:

1. `exit_status_mark_ok` (`run_on_error = false`): touches a hidden marker file in `$_DYNAMIC_DIR/unit-status/` **only** on success
2. `exit_status_write` (`run_on_error = true`): always runs; reads the marker to determine ok vs fail, writes `exit-<rel_path_full>.yaml`, cleans up any stale `maas-<unit>.yaml`

All files land in `$_DYNAMIC_DIR/unit-status/` (`config/tmp/dynamic/unit-status/`) — per-checkout, no `/tmp/` scatter.

### `utilities/tg-scripts/write-exit-status/run` — new script

Bash script called by the `exit_status_write` hook. Reads the `.ok-<unit>` marker to determine ok vs fail, writes an atomic YAML via temp+rename, and cleans up any stale MaaS intermediate status file.

### `homelab_gui.py` — Tier 0 consumer + schema v2

**Tier 0 (new)**: At the start of each `local_state_watcher` poll cycle, scans `$_DYNAMIC_DIR/unit-status/exit-*.yaml`. For each file: reads `unit_path`/`status`/`finished_at`, updates `unit_build_statuses` and `unit-state.yaml`, deletes the file. Tracks resolved unit paths so Tier 1 GCS cat is skipped for them.

**Tier 1 fallback**: GCS `gsutil cat` now only fires for tfstate-mtime changes where no exit-status YAML was found (applies from before the hook was deployed, or race conditions).

**Schema v2**:
- `resources_count` removed from schema comment, `_write_unit_state` (v2 bump), hover popup `_ORDER`, and Tier 2 validate write path
- New fields added to `_ORDER`: `maas_phase`, `maas_message`, `details`

### `docs/ai-plans/improve-unit-status-1.md` — plan document (created in prior session)

Full design doc for all three layers. Decisions recorded: destroy=yes, transitional old exit files=keep, resources_count=removed.

## What's next (Layer C)

Layer C (MaaS intermediate status) still pending:
- C1: commission-and-wait / deploy scripts write `maas-<unit>.yaml` every 30s
- C2: GUI Tier 1 picks up `maas-*.yaml` files each poll cycle
- C3: MaaS TF module `exit_status`/`exit_details` outputs (lowest priority)
