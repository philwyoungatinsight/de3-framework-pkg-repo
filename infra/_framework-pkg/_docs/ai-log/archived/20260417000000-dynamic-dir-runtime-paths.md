# AI Log — 2026-04-17 — dynamic-dir-runtime-paths

## What changed

Consolidated all runtime file paths under `_DYNAMIC_DIR` so two GUI instances
from different repo checkouts no longer conflict.

### `set_env.sh`
- Added `_WAVE_LOGS_DIR=$_DYNAMIC_DIR/run-wave-logs` and `_GUI_DIR=$_DYNAMIC_DIR/gui`
- Both dirs created alongside existing `mkdir -p` call

### `run` (wave runner)
- `setup_logging()` and `_scan_wave_statuses()` now read `_WAVE_LOGS_DIR` from
  environment, falling back to `~/.run-waves-logs` when unset
- Updated module docstring references

### `homelab_gui.py`
- Added `_wave_logs_dir()` helper (reads `_WAVE_LOGS_DIR` env var)
- `_TEST_APPLIED_MARKER` moved from `~/.homelab-gui-test-applied` to `$_GUI_DIR/test-applied`
- `_unit_state_path()` rewritten to use `$_DYNAMIC_DIR/unit-state/unit-state.yaml`
- Three `wave_logs_dir` config-lookup sites replaced with `_wave_logs_dir()`
- `MARKER` (state-check rate-limit file) moved from `/tmp/...` to `$_GUI_DIR/...`
- Exit-code signal files moved from `/tmp/homelab_gui_apply_*.exit` to `$_GUI_DIR/...`

### `infra/de3-gui-pkg/_application/de3-gui/run`
- `_stop()` removes both old `~/.homelab-gui-test-applied` and new `$_GUI_DIR/test-applied`
- Reflex startup log moved from `/tmp/reflex-homelab-gui.log` to `$_GUI_DIR/...`

### `infra/de3-gui-pkg/_config/de3-gui-pkg.yaml`
- Removed `wave_logs_dir` config key (path now driven by env var, not YAML)
- `wave_tail_cmd` updated to use `$_WAVE_LOGS_DIR`

### `framework/clean-all/run` + `config/framework.yaml`
- Removed `stage_move_wave_logs()` and `_read_move_wave_logs()` entirely (logs are
  already in `_DYNAMIC_DIR` — nothing to move)
- Removed `move_wave_logs: true` from `config/framework.yaml`
