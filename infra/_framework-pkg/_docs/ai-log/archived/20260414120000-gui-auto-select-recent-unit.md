# AI Log — GUI: Auto-select recent unit

**Date**: 2026-04-14
**File**: `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`

## What changed

Added an "Auto-select recent unit" toggle to the Appearance menu's new "Folder view behaviour"
section. When enabled, the tree auto-selects and highlights the unit whose apply most recently
completed, driven by the existing `local_state_watcher` background loop.

## Changes made

### State variables (line ~3763)
- Added `auto_select_recent_unit: bool = False` — the toggle state
- Added `recent_unit_path: str = ""` — tracks the most recently auto-selected unit path

### `_apply_auto_select` helper (after `select_node`)
- Plain Python method (not a Reflex event) called only from inside `async with self:` blocks
- Expands all ancestor paths so the node is visible in the tree
- Sets `selected_node_path`, loads HCL content (handles both separated and merged tree modes)

### Toggle event handlers
- `toggle_auto_select_recent_unit(checked)` — checkbox `on_change` handler
- `flip_auto_select_recent_unit()` — click-on-label handler (same pattern as wave highlight)

### Persistence
- `_save_current_config`: added `"auto_select_recent_unit"` key
- `on_load`: restores with `bool(saved_menu.get("auto_select_recent_unit", False))`

### `local_state_watcher` hooks (3 places)
- **Tier 1** (GCS tfstate change): auto-selects the first unit in `updates` dict
- **Tier 3** (exit-code files): auto-selects the first unit in `exit_updates` dict
- **Auto-refresh** (unit-state.yaml mtime change): selects the unit with most recent
  `last_apply_at`; only fires on `mtime_changed`, not `interval_elapsed`

### Appearance menu
- New "Folder view behaviour" section inserted between the existing "Folder view" section
  and "Wave panel columns" section
- Uses `_appearance_menu_item` — same pattern as all other toggles in the menu

## Pattern followed
Mirrors the existing `wave_highlight_recent` / `recent_wave_name` feature for wave panel.
