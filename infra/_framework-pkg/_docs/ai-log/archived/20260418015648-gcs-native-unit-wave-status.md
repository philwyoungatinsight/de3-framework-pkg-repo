# GCS-native unit and wave status

**Date**: 2026-04-18  
**Plan**: `docs/ai-plans/archived/20260418015643-gui-status-gcs-impl.md`

## What was done

Implemented GCS-native build status persistence as described in the design spec (`docs/ai-plans/gui-status-gcs.md`).

### New files

- **`utilities/bash/gcs-status.sh`** — shared bash helper `gcs_write_unit_status`. Sources after `set_env.sh`; reads bucket from `config/framework.yaml`. All GCS writes are fire-and-forget (`... &`).
- **`utilities/python/gcs_status.py`** — Python equivalent for the wave runner. Provides `write_wave_status(wave, phase, status)`. All GCS writes use daemon threads.
- **`scripts/human-only-scripts/purge-gcs-status/run`** — pruning script. Keeps last `_GCS_STATUS_KEEP_LAST` (default 5) JSON objects per `unit_status/<path>/` and `wave_status/<wave>/` group. Supports `DRY_RUN=1`.

### Modified files

- **`utilities/tg-scripts/write-exit-status/run`** — sources `gcs-status.sh` and calls `gcs_write_unit_status` after writing the local YAML. No change to local write path.
- **`run`** (wave runner) — imports `gcs_status`; wraps `_stream` calls in `run_tg()` and `run_ansible_playbook()` with `write_wave_status` at phase start (running) and end (ok/fail).
- **`infra/de3-gui-pkg/.../homelab_gui.py`**:
  - Removed Tier 1 (`.terragrunt-cache` mtime scan + GCS cat fallback) from `local_state_watcher`. Unit status now arrives exclusively via Tier 0 exit-status YAMLs.
  - Removed GCS bucket setup lines that were only used by Tier 1.
  - Added state vars: `unit_status_sync_after`, `wave_status_sync_after`, `gcs_wave_statuses`.
  - Added `sync_unit_status_from_gcs` background task: incremental sync of `unit_status/` on startup to recover prior-session unit statuses.
  - Added `sync_wave_status_from_gcs` background task: loads newest wave status per wave from `wave_status/` on startup.
  - Both tasks launched from `on_load` alongside `local_state_watcher`.
  - `refresh_wave_log_statuses()` merges `gcs_wave_statuses` for waves not found in the current session's `run.log`.
- **`infra/gcp-pkg/_setup/seed`** — adds 180-day GCS lifecycle Delete rule on `unit_status/` and `wave_status/` prefixes as a long-term backstop.

## Key design decisions

- GCS writes never block apply or wave execution (all fire-and-forget).
- Bucket name read from `config/framework.yaml` at call time (no env var needed).
- Tier 0 (exit-status YAMLs) remains the fast local inter-process signal; GCS is the shared truth store for cross-session recovery.
- `gcs_state_mtimes` state var retained — still used by the validate/GCS scan path (`do_refresh_unit_build_statuses`).
