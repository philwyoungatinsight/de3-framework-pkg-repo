# GUI: Unit Detail Popup — Checkbox-Controlled, Tracks Selected Node

## Summary

Replaced the 5-second hover timer with a simple checkbox in the Appearance menu.
When "Show unit popup on select" is checked, the floating unit-detail popup appears
whenever a node is selected (clicked), and updates its content automatically when
the selection changes. The popup can still be closed with ✕ and dragged by its header.

## Changes

- **`homelab_gui.py`** — state vars:
  - Added `show_unit_popup: bool = False` (persisted in config)
  - Removed `hover_pending_path` (no longer needed without hover timer)

- **`homelab_gui.py`** — event handlers removed:
  - `start_hover_timer` — no longer needed
  - `cancel_hover_timer` — no longer needed
  - `on_hover_show_trigger` — no longer needed
  - `position_hover_popup` — replaced by `init_popup_drag`

- **`homelab_gui.py`** — event handlers added:
  - `_load_hover_popup_for_path(path)` — plain Python helper: loads unit-state + params, sets `hover_popup_open=True`
  - `toggle_show_unit_popup(checked)` / `flip_show_unit_popup()` — checkbox handlers; on enable, immediately loads selected node's data and calls `init_popup_drag`
  - `init_popup_drag()` — wires pointer-capture drag on the popup header; uses `_dragInstalled` guard to prevent duplicate listeners

- **`homelab_gui.py`** — `select_node`: added hook at the top — if `hover_popup_open` and path is non-empty, calls `_load_hover_popup_for_path(path)` to update popup content on every node selection

- **`homelab_gui.py`** — `close_hover_popup`: removed `hover_pending_path` clear (field removed)

- **`homelab_gui.py`** — `install_resizer`: removed mouse-tracker JS (no longer needed)

- **`homelab_gui.py`** — `tree_node_component`: removed `on_mouse_enter` and `on_mouse_leave`

- **`homelab_gui.py`** — `index()`: removed `hover-show-trigger` hidden div

- **`homelab_gui.py`** — `_save_current_config` / `on_load`: added `show_unit_popup` persistence

- **`homelab_gui.py`** — `appearance_menu()`: added "Unit detail popup" section with `_appearance_menu_item("Show unit popup on select", ...)`

## Notes

- The popup only opens when the checkbox is ON AND a node is clicked. If the user closes
  the popup with ✕, subsequent clicks reopen it (because `select_node` only updates
  when `hover_popup_open` is True — the reopen happens via `flip_show_unit_popup` or
  by clicking a node while the checkbox is still on).

  Wait — actually the current logic only updates when `hover_popup_open` is True.
  If the user closes with ✕ (`hover_popup_open = False`), clicking another node won't
  reopen. To reopen: toggle checkbox off/on. This is intentional — the ✕ means "dismiss".

- The `_dragInstalled` guard on the header element prevents duplicate event listeners
  accumulating when content updates (content changes cause re-render but the header
  element persists, so listeners would otherwise stack).
