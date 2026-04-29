# Waves panel auto-scrolls active wave into view

## Summary

When the active wave changes (a new wave starts running or the most-recently-updated
wave changes), the waves panel now automatically scrolls that row to the top of the
visible table area. Implemented by adding DOM `id` attributes to wave rows and yielding
a `scrollIntoView` call script from `refresh_wave_log_statuses` when `recent_wave_name`
changes.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**:
  - `_wave_toggle_item` (list view): added `id="wave-row-" + item["name"]` to
    `rx.table.row()` so the row can be targeted by `getElementById`.
  - `_wave_folder_item` (folder view): same id added.
  - `refresh_wave_log_statuses`: captures `old_recent = self.recent_wave_name` at
    entry; after updating `recent_wave_name`, if it changed and is non-empty, yields
    `rx.call_script` to call `scrollIntoView({block:'start', behavior:'smooth'})` on
    the corresponding row element.
  - Converted `return AppState.refresh_unit_build_statuses` to `yield` (with an `else`
    branch for `had_running_wave`) so the function can be a generator that yields both
    the scroll script and the unit-refresh event.

## Notes

- Only one of list/folder tables is in the DOM at a time (`rx.cond`), so `getElementById`
  silently returns `null` if the other view is active — no error, no scroll.
- `block: 'start'` places the row at the top of the scroll container viewport, matching
  the user's request that the active wave be "the first wave shown".
- `behavior: 'smooth'` gives a visible animation so the scroll doesn't feel jarring.
- The scroll fires only when `recent_wave_name` changes, not on every poll, so it doesn't
  fight the user if they've manually scrolled elsewhere.
