# GUI: unit-state.yaml persistent cache + auto-refresh

## Summary

Introduced `~/.run-waves-logs/unit-state.yaml` as a persistent per-unit build status
cache for the GUI. The "⟳ Refresh" button is now near-instant (YAML read, no GCS),
and a new "Validate (GCS)" button handles the full authoritative scan. An auto-refresh
option keeps status in sync automatically on file-change or a configurable interval.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**
  - Added `_unit_state_path()`, `_read_unit_state()`, `_write_unit_state()` — atomic YAML
    helpers with a threading lock
  - `on_load`: reads YAML on startup instead of clearing statuses (instant population,
    no GCS call)
  - `local_state_watcher`: writes `unit-state.yaml` after every Tier 1 (GCS cat) and
    Tier 3 (exit-file) status update
  - `refresh_unit_build_statuses` / `do_refresh_unit_build_statuses`: fast path — reads
    YAML only, no network I/O
  - New `validate_unit_build_statuses` / `do_validate_unit_build_statuses`: full GCS scan
    (the old refresh logic), writes `last_validated_at` + `resources_count` to YAML
  - `do_refresh_subtree_status`: also persists subtree scan results to YAML
  - `apply_unit`: tees output to `~/.run-waves-logs/unit-logs/<unit>/YYYYMMDD-HHMMSS.log`
    + `latest.log` symlink; uses `${PIPESTATUS[0]}` for correct exit code through tee
  - Auto-refresh: new state vars `unit_status_auto_refresh` + `unit_status_auto_refresh_secs`;
    `local_state_watcher` checks YAML mtime and/or elapsed interval on every poll; new
    Appearance menu controls (checkbox + interval select); both vars persisted to
    `state/current.yaml`
  - UI: "Validate (GCS)" button added next to "⟳ Refresh"; auto-refresh row below buttons

- **`docs/framework/gui-build-status.md`** — new doc covering status values, YAML schema,
  three-tier update pipeline, Refresh vs Validate, auto-refresh modes, per-unit logs,
  and implementation notes

## Notes

The YAML is co-located with wave logs (`~/.run-waves-logs/`) so both live in the same
inspection directory. `0 s` interval means on-change only (mtime check on every 8 s
poll); any positive interval also triggers a time-based refresh regardless of mtime.
