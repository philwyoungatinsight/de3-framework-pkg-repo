---
date: 2026-04-18
slug: gui-gcs-sync-loading-steps
---

# GUI: Show GCS Sync Steps in Startup Banner

## What changed

Extended the startup status banner in `homelab_gui.py` to surface `gcs-unit-sync` and
`gcs-wave-sync` as visible loading steps.

**State vars added** (`gcs_unit_sync_running`, `gcs_wave_sync_running`): two `bool` fields
near the existing GCS cursor vars (line ~3914).

**`app_status_message` updated**: now has five states instead of two — inventory pending,
inventory + GCS syncing, unit-only syncing, wave-only syncing, both syncing. Banner stays
visible until all background syncs complete.

**`sync_unit_status_from_gcs` updated**: sets `gcs_unit_sync_running = True` (merged into
existing `async with self` cursor-read block) and wraps the full remaining body in
`try/finally` to guarantee the flag clears on all exit paths (normal, early-return, exception).

**`sync_wave_status_from_gcs` updated**: same pattern — flag set on entry, `try/finally`
clears it unconditionally.

## Why

Previously the banner cleared once inventory refresh completed, even though both GCS syncs
could still be running (gsutil ls + per-object cat over GCS). Users saw stale build status
data with no indication that a sync was in progress.
