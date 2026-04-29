# AI Log — GUI floating panels mode + appearance accordion

**Date:** 2026-04-15  
**Session:** gui-floating-panels-and-appearance-submenus  
**Plan:** docs/ai-plans/gui-floating-panels-and-appearance-submenus.md

## Summary

Implemented two GUI improvements in `homelab_gui.py`:

### 1. Floating panels mode

A new layout mode where the infra tree stays fixed in the layout and the three secondary
panels (file viewer, terminal, object viewer) become independent draggable/resizable
floating windows.

**What was added:**
- 16 new state vars: `floating_panels_mode`, `float_{fv,term,ov}_{open,saved_x,saved_y}`
- Event handlers: `toggle/flip_floating_panels_mode`, `init_all_float_panels`
- Per-panel handlers ×3: `toggle/flip/close_float_{file_viewer,terminal,object_viewer}`,
  `save_float_{fv,term,ov}_{x,y}`, `init_float_{file_viewer,terminal,object_viewer}`
- JS drag initialisers follow the `hover_popup_window` pattern (`_positionSet` guard,
  `_dragInstalled` guard, pointer-capture drag)
- Default positions: stacked near viewport centre with 30 px stagger
- Position persistence: saved to `state/current.yaml` on close via `rx.call_script` callbacks
- Three new `rx.Component` functions: `float_file_viewer_panel()`, `float_terminal_panel()`,
  `float_object_viewer_panel()` — each wraps the existing panel function
- "Panels ▾" dropdown: `panels_menu()` in `left_panel()` header, visible only when floating mode is on
- `index()` updated: outer `rx.cond(floating_panels_mode, ...)` renders infra-tree-only sidebar in
  floating mode; the three floating panel components added at page root level (like hover_popup_window)
- `on_load` appends `init_all_float_panels` to the scripts list when floating mode was persisted on

### 2. Appearance menu accordion

Replaced the flat scrollable appearance menu with 10 collapsible accordion sections so it
fits on screen without scrolling.

**What was added:**
- 10 new state vars: `appear_s_{controls,infra,wave,file,popup,terminal,params,networks,layout,theme}`
- 10 flip handlers: `flip_appear_s_*`
- `_appearance_section()` helper: collapsible titled section with ▾/▸ toggle
- `appearance_menu()` body fully rewritten using `_appearance_section()` wrappers
- "Floating panels mode" checkbox added as first item in the Layout section
- "Show in controls bar" and "Infra tree" sections open by default; all others collapsed

All new state persisted to `state/current.yaml` via `_save_current_config` / `on_load`.
