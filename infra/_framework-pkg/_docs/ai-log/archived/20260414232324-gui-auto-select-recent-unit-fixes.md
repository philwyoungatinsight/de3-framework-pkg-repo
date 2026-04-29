# GUI: Auto-select Recent Unit — Button Move and Selection Fixes

## Summary

Moved the "Auto-select recent unit" control from the Appearance dropdown menu to a compact
toggle button ("Auto") in the infra panel toolbar, next to Merge/Unmerge. Fixed several
bugs where enabling the toggle did not actually select or scroll to the node in the tree.

## Changes

- **`homelab_gui.py`** — removed "Folder view behaviour" section from `appearance_menu()`
- **`homelab_gui.py`** — added `_panel_auto_select_btn()`: compact "Auto" button with
  solid/outline variant to show active state; placed after `_panel_merge_btn()` in control bar
- **`homelab_gui.py`** — `flip_auto_select_recent_unit`: on enable, immediately reads
  `unit-state.yaml`, finds most-recently-applied unit, expands its ancestors in
  `expanded_paths`/`merged_expanded_paths`, sets `left_view="tree"`, then returns
  `AppState.click_node(best)` as an event spec followed by a `requestAnimationFrame` scroll
- **`homelab_gui.py`** — added `id=rx.cond(is_selected, "tree-selected-node", "")` to
  each tree row so JS can target the selected element for `scrollIntoView`
- **`homelab_gui.py`** — `_apply_auto_select` (watcher path): added `_gui_log` line so
  every auto-selection logs the relative unit path to the terminal

## Root Cause

Three bugs, fixed in sequence:

1. **Button not selecting anything**: `flip_auto_select_recent_unit` called
   `self.select_node(best)` as a plain Python method. `click_node` is a Reflex generator
   event that uses `yield` to flush `selected_node_path` to the frontend before loading
   HCL. Calling `select_node` directly skipped that flush — state was set but React never
   re-rendered the tree row highlight. Fix: return `AppState.click_node(best)` as an
   event spec so Reflex dispatches it as a real event after the expansion delta is sent.

2. **Node selected in file viewer but not in tree**: `click_node` was never being
   dispatched as a proper event — confirmed via the path-mismatch debug log showing
   `best` didn't appear in the first 5 tree node paths (they were from a different package).
   The tree only highlights when `selected_node_path` matches a rendered `visible_nodes`
   entry, and the node must be in `visible_nodes` (ancestors expanded).

3. **Node not scrolled into view**: added `id="tree-selected-node"` to the selected row
   and emitted `scrollIntoView({block:'center'})` via `requestAnimationFrame` (fires
   immediately after browser paint, no artificial delay).

## Notes

- `click_node` being a generator (`yield`) is the key invariant: always dispatch it as an
  event spec, never call it as a Python method from another handler.
- The `requestAnimationFrame` approach is faster than `setTimeout(..., N)` — it fires at
  the next browser paint cycle which is the earliest the element can exist in the DOM.
