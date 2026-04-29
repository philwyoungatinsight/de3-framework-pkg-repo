# Plan: Show GCS Sync Steps in GUI Startup Banner

## Objective

Extend the startup status banner to surface `gcs-unit-sync` and `gcs-wave-sync` as
visible loading steps, so users understand why the GUI shows stale or missing build
status data immediately after opening it. Currently the banner clears once inventory
refresh completes, even though both GCS syncs may still be in progress (fetching unit
statuses and wave run history from GCS).

## Context

Key findings from code exploration:

- **`startup_status_banner()`** (line 16070) renders a fixed bottom bar driven entirely
  by the `app_status_message` computed var. When the var returns `""` the bar vanishes.
- **`app_status_message`** (line 4062) currently has two states:
  1. `is_loading=True` → `"Initializing…"`
  2. `inventory_refresh_counter == 0` → `"Refreshing inventory…"`
  3. otherwise → `""` (banner disappears)
- **`sync_unit_status_from_gcs`** (line 9208) and **`sync_wave_status_from_gcs`**
  (line 9300) are `@rx.event(background=True)` tasks kicked off from `on_load` (lines
  5601–5602). They run concurrently with `signal_inventory_ready` and can each take
  several seconds (gsutil ls + per-object cat over GCS).
- Neither sync function currently touches any state var that the banner watches — they
  run silently after the banner has already cleared.
- State variables related to these syncs live around line 3914–3919: `unit_status_sync_after`,
  `wave_status_sync_after`, `gcs_wave_statuses`.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

**1. Add two boolean state vars** near line 3914 (the GCS sync cursor block):

```python
# GCS status sync cursors — ISO timestamps of last sync (empty = never synced).
unit_status_sync_after: str = ""
wave_status_sync_after: str = ""
# Track whether each GCS sync background task is currently running.
gcs_unit_sync_running: bool = False
gcs_wave_sync_running: bool = False
```

**2. Update `app_status_message`** (line 4062) to extend the banner lifetime through both GCS syncs:

```python
@rx.var
def app_status_message(self) -> str:
    if self.is_loading:
        return "Initializing\u2026"
    inv_pending = self.inventory_refresh_counter == 0
    unit_syncing = self.gcs_unit_sync_running
    wave_syncing = self.gcs_wave_sync_running
    if inv_pending:
        if unit_syncing or wave_syncing:
            return "Refreshing inventory + syncing GCS\u2026"
        return "Refreshing inventory\u2026"
    if unit_syncing and wave_syncing:
        return "Syncing GCS status (unit + wave)\u2026"
    if unit_syncing:
        return "Syncing GCS unit status\u2026"
    if wave_syncing:
        return "Syncing GCS wave status\u2026"
    return ""
```

**3. Update `sync_unit_status_from_gcs`** (line 9208) to set the flag on entry and clear it on all exit paths:

At the top of the function body (after the `gsutil` which-check), add:
```python
async with self:
    self.gcs_unit_sync_running = True
```

Wrap the entire remainder of the function in a `try/finally` so the flag always clears:
```python
try:
    # ... existing body ...
finally:
    async with self:
        self.gcs_unit_sync_running = False
```

**4. Update `sync_wave_status_from_gcs`** (line 9300) identically:

At the top (after the `gsutil` which-check), add:
```python
async with self:
    self.gcs_wave_sync_running = True
```

Wrap remainder in `try/finally`:
```python
try:
    # ... existing body ...
finally:
    async with self:
        self.gcs_wave_sync_running = False
```

> **Note on early returns**: both functions have early-return paths (bucket not configured,
> gsutil not found, empty URI list). The `try/finally` placement must be *after* those
> early returns — those paths mean there's nothing to sync, so showing a loading step
> would be misleading. Set `gcs_*_sync_running = True` only after confirming there is
> real work to do (i.e. after the gsutil `ls` call succeeds and URIs are found).
> Actually, it's cleaner UX to set the flag before the `ls` call so the user sees the
> step immediately — just ensure `finally` always clears it.

## Execution Order

1. Add `gcs_unit_sync_running` and `gcs_wave_sync_running` state vars.
2. Update `app_status_message` computed var.
3. Update `sync_unit_status_from_gcs` — set flag, add try/finally.
4. Update `sync_wave_status_from_gcs` — set flag, add try/finally.

## Verification

After changes, start the GUI with `./run run` and open it in a browser.
On load, the bottom banner should cycle through visible messages:

1. `"Initializing…"` — briefly while `on_load` runs
2. `"Refreshing inventory…"` or `"Refreshing inventory + syncing GCS…"` — while inventory runs
3. `"Syncing GCS status (unit + wave)…"`, `"Syncing GCS unit status…"`, or
   `"Syncing GCS wave status…"` — as syncs complete individually
4. Banner disappears — all syncs done

Check the GUI log (`_gui_log` output) for `[gcs-unit-sync]` and `[gcs-wave-sync]`
lines to confirm the syncs ran and the counts are non-zero on a loaded environment.
