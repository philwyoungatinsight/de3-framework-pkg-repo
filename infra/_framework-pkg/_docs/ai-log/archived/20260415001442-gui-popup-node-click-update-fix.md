# GUI: Fix Unit Popup Not Updating on Node Click; Close Unchecks Toggle

## Summary

Fixed two bugs in the unit detail popup: clicking different tree nodes did not update
the popup content, and closing the popup with ✕ did not uncheck the "Show unit popup on
select" checkbox in the Appearance menu.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — `click_node`:
  added popup update hook before the `yield` — when `show_unit_popup` is True and a node
  path is provided, `_load_hover_popup_for_path(path)` is called so the popup content
  refreshes on every node click

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — `close_hover_popup`:
  added `self.show_unit_popup = False` and `self._save_current_config()` so that pressing
  ✕ unchecks the Appearance toggle and persists the closed state

## Root Cause

`click_node` is a generator event that does NOT call `select_node` — it sets
`selected_node_path` inline. The previous fix added the popup update hook to
`select_node`, which is never called on node click. The correct location is inside
`click_node` itself, before the `yield`.

## Notes

- `click_node` uses `self.show_unit_popup` (checkbox state) as the guard, not
  `self.hover_popup_open` (visibility state). This is intentional: after closing with ✕,
  both flags are False, so clicking another node doesn't unexpectedly reopen the popup.
- The hook in `select_node` (using `hover_popup_open`) remains for any non-click selection
  paths (e.g., auto-select recent unit).
