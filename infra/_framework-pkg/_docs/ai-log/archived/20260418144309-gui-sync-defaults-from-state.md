# GUI: sync defaults from current state

## What changed

- **`homelab_gui.py` `_load_state()`**: now falls back to `state/defaults.yaml` when
  `current.yaml` is absent (first boot / fresh clone / wiped container). A corrupt
  `current.yaml` still returns `{}` unchanged.
- **`state/defaults.yaml`** (new): snapshot of the current tuned look — dark theme,
  `pwy-home-lab-pkg` only, all the panel/wave display toggles as preferred — with
  transient fields (`*_search_query`, `selected_node_path`, etc.) zeroed out.
- **`scripts/ai-only-scripts/snapshot-gui-defaults/run`** (new): re-snapshots
  `defaults.yaml` from the live `current.yaml` any time the user wants to freeze the
  current look as the new factory reset.

## Why

The GUI previously fell back to stale Python class defaults on first boot, producing a
visibly wrong initial state (wrong theme, wrong filters, wrong panel sizes). This makes
the defaults match months of real tuning without requiring a full GUI session to configure.
