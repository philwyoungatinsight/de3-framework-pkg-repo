# GUI: Waves Folder View — Collapsible Folders + Folder-Level Actions

## Summary

Added collapsible folder nodes to the waves folder view, a toolbar button to
expand/collapse the entire tree, and apply/destroy action buttons on each folder
node that run all waves under that folder prefix.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**

  **Collapsible folders (Plan B — collapsed-set model):**
  - `wave_folder_collapsed: list[str]` state var — empty by default, not persisted,
    resets each session so stale state can never hide a wave
  - `waves_folder_rows` computed var updated: filters out rows whose ancestor is in
    `wave_folder_collapsed`; adds `folder_path`, `has_children`, `is_expanded` fields
    to every row dict; also fixes missing `log_update_age` in `wave_attrs`
  - `toggle_wave_folder(folder_path)` — collapse adds path (stripping already-collapsed
    descendants); expand removes path
  - `_wave_folder_item` folder row now renders clickable `▶`/`▼` chevron + 📁 + label

  **Expand / Collapse all button:**
  - `wave_folders_collapsed: bool` computed var (True when anything is collapsed)
  - `toggle_wave_folder_all()` — expand all: clears list; collapse: computes all
    top-level folder paths from `wave_filters` and collapses them
  - `⊟ Collapse` / `⊞ Expand` button in waves toolbar, visible only in folder view

  **Folder-level apply / destroy:**
  - State vars: `wave_folder_run_dialog_open`, `wave_folder_run_pending_path`,
    `wave_folder_run_pending_mode`
  - `begin_wave_folder_run(folder_path, mode)` — apply goes direct to terminal;
    destroy opens confirmation dialog
  - `_open_wave_folder_terminal(folder_path, mode)` — builds `-w '<folder>.*'` command
    (fnmatch glob already supported by the `./run` script)
  - `folder_action_cell` in `_wave_folder_item` — `▶` apply and `🗑` destroy buttons
    on every folder row, same layout as wave rows
  - Confirmation dialog for folder destroy showing the exact command that will run

## Notes

Using `-w 'network.*'` leverages the existing `fnmatch.fnmatch` filter in `./run`
(line 922) — no changes to the run script needed. The collapsed-set model was chosen
over an expanded-list model to avoid any risk of accidentally hiding waves when wave
names change between sessions.
