# Fix: wave row id — pre-compute in state vars, not via Var string concat

## Summary

The previous commit added `id="wave-row-" + item["name"]` to wave table rows, but
`item["name"]` inside `rx.foreach` is a Reflex `ObjectItemOperation` (not a Python
string). Python's `+` operator on `str + Var` raises a TypeError at Reflex compile
time, preventing the GUI from starting. Fixed by pre-computing `row_id` as a plain
Python string in `waves_with_visibility` and `waves_folder_rows`, then referencing
`item["row_id"]` in the component (Var subscript, not string concat).

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**:
  - `waves_with_visibility`: all three `result.append({...})` sites now include
    `"row_id": f"wave-row-{name}"` / `"wave-row-{val}"` / `"wave-row-_none"`.
  - `waves_folder_rows`: `result.append({...})` now includes `"name": node_path` and
    `"row_id": f"wave-row-{node_path}"`.
  - `_wave_toggle_item` and `_wave_folder_item`: changed `id="wave-row-" + item["name"]`
    to `id=item["row_id"]`.

## Root Cause

CLAUDE.md for de3-gui-pkg explicitly documents this: `"literal" + node["field"]`
fails because `node["field"]` is an `ObjectItemOperation`, not a `str`. The fix is
always to pre-compute string values into the dict and read them back via subscript.
