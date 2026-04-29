# GUI Log Output: Add Timestamps

## Summary

All `print()` log calls in `homelab_gui.py` now emit a `[HH:MM:SS]` timestamp
prefix, making it easy to correlate log lines with actions in the running app.
Previously all log lines lacked timestamps and were hard to sequence when
debugging startup or background task timing.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** —
  added `from datetime import datetime as _datetime` import and a `_gui_log(msg)`
  helper that calls `print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)`.
  Replaced all ~34 `print(f"[tag] ...")` calls (across `[homelab_gui]`,
  `[inventory_refresh]`, `[on_load]`, `[local-state-watcher]`, `[file-watcher]`,
  `[remove_pkg_repo]`, `[keyboard-layout]` tags) with `_gui_log(...)`.

## Notes

- The `_gui_log` helper is intentionally minimal — no logging levels, no file
  output, no module path. Just a wall-clock timestamp for terminal correlation.
- `flush=True` is preserved in the helper so log lines appear immediately even
  when stdout is line-buffered.
