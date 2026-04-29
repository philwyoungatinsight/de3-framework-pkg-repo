# Add Framework Repos Cytoscape view to de3-gui

## Summary

Added a new "Framework Repos" explorer root to the de3-gui GUI that reads
`config/tmp/fw-repos-visualizer/known-fw-repos.yaml` and visualises repos as
Cytoscape compound nodes with packages as children. The view has its own menu
bar with Refresh, Layout selector, Collapse, and Appearance controls. Node
positions are persisted to a separate layout file.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**
  - Added `_FW_REPOS_YAML`, `_FW_REPOS_LAYOUT`, `_FW_REPOS_VIZ_BIN` path constants
  - Added `_FwReposCytoscapeGraph` subclass with `cytoscape-dagre` + `dagre` npm deps
  - Added 11 AppState fields (`framework_repos_data`, `fw_repos_positions`, `fw_repos_root_ids`, `fw_repos_collapsed_repos`, `fw_repos_layout`, and 6 appearance bools)
  - Added 4 computed vars: `framework_repos_data_keys`, `fw_repos_layout_label`, `fw_repos_cyto_layout`, `fw_repos_cytoscape_elements`
  - Added 8 event handlers: `save_fw_repos_layout`, `reset_fw_repos_layout`, `toggle_fw_repo_collapsed`, `collapse_all_fw_repos`, `expand_all_fw_repos`, `set_fw_repos_layout_by_label`, `refresh_fw_repos_data`
  - Added fw_repos data loading in `on_load()` (reads YAML + layout file, derives root_ids)
  - Added fw_repos state persistence in `_save_current_config()` and `_load_state()`
  - Added `_FW_REPOS_CYTOSCAPE_STYLESHEET`, `_FW_REPOS_CYTOSCAPE_INIT_JS`, `_FW_REPOS_SAVE_LAYOUT_JS` constants
  - Added `_fw_repos_appearance_menu()`, `_fw_repos_collapse_menu()`, `fw_repos_cytoscape_view()` component functions
  - Updated `render_left_panel_content()` with `("framework_repos", fw_repos_cytoscape_view())`
  - Updated `_explorer_root_selector()` label match and dropdown with "Framework Repos" item
  - Updated `set_explorer_root()` docstring

- **`infra/de3-gui-pkg/_application/de3-gui/state/fw-repos-layout.yaml`** — created empty placeholder for persisted node positions

## Design Decisions

- **No deduplication**: packages appear in every repo that lists them with embedded/external badge — no cross-compound edges
- **Appearance controls** (show/hide lineage, source badge, URL, packages, type badge, exportable, merge-duplicates stub) all live in a single Appearance dropdown rather than bare checkboxes
- **Collapse dropdown** handles both bulk Collapse All/Expand All and per-repo toggles via `rx.foreach`
- **Layout algorithms**: Force (cose), Tree (breadthfirst), Layered (dagre via subclass), Saved (preset from file)
- **Layout persistence**: GUI-owned `state/fw-repos-layout.yaml` — never touched by fw-repos-visualizer
- **Refresh button** shells out to `fw-repos-visualizer --list`; tool has `auto_refresh_on_render: true` so it re-scans stale sources automatically

## Notes

The `dagre` layout requires `cytoscape-dagre` to be registered at runtime. The init JS does `cytoscape.use(window.cytoscapeDagre)` — this fires only when the component mounts. Layout algorithm changes after initial mount may require a page reload for the new algorithm to take effect (v2 concern: add a component key derived from `fw_repos_layout` to force remount on change).
