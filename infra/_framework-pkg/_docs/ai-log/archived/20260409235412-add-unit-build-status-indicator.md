# Add per-unit build status indicator to unit tree

## What changed

Added a new appearance option "Show build status" to the unit explorer tree in `homelab_gui.py`. When enabled, a coloured dot appears before each leaf unit's name indicating its build state:

- **Green** — `default.tfstate` exists in the GCS state bucket (unit was successfully applied)
- **Red** — unit appeared in the latest run's "Unit queue" but has no GCS state (likely failed)
- **Grey** — not yet attempted or fully cleaned up (no log evidence, no GCS state)
- **Amber** — "unknown" (reserved for future use; not yet populated)

## Files modified

- `infra/de3-gui-pkg/_applications/de3-gui/homelab_gui/homelab_gui.py`

## Implementation details

1. **New `AppState` fields**: `unit_build_statuses: dict[str, str]`, `show_unit_build_status: bool`, `unit_build_status_loading: bool`

2. **`visible_nodes` computed var**: injects `build_status` field into every node dict by looking up `unit_build_statuses[node_path]` (defaults to `"none"`)

3. **`refresh_unit_build_statuses` background task** (`@rx.event(background=True)`):
   - Reads the GCS bucket name from `infra/pwy-home-lab-pkg/_config/gcp_seed.yaml`
   - Runs `gsutil ls -r gs://<bucket>/` and maps `*/default.tfstate` paths to `"ok"` status
   - Parses `~/.run-waves-logs/latest/run.log` for `- Unit <path>` lines to find attempted units; marks attempted-but-no-state as `"fail"`

4. **`tree_node_component`**: coloured 7px dot inserted before the node name inside the name hstack, visible only for terragrunt leaf units when `show_unit_build_status` is on

5. **Appearance menu**: "Show build status" toggle added under the "Folder view" section, with a conditional "⟳ Refresh status" button that fires the background task

6. **Persistence**: setting saved to/loaded from `state/current.yaml` via `_save_current_config` / `on_load`; toggling on auto-triggers an initial refresh

## Why

User requested a quick visual indicator of which units have been deployed vs. not, without having to read wave logs or check GCS manually.
