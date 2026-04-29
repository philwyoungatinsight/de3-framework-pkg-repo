# improve-unit-status: Layer C — MaaS intermediate status

## Summary

Implemented Layer C of the `improve-unit-status-1` plan: live progress visibility during the long-running MaaS commissioning (~5 min) and deployment (~10 min) phases.

## Changes

### `root.hcl` — new `generate "unit_path_env"` block

Generates `unit_path.env` into every module cache directory alongside `backend.tf` and `provider.tf`. Content:
```bash
export UNIT_PATH="<rel_path>"
export UNIT_REL_FULL="<rel_path_full>"
```
Scripts source this to get the unit path without any per-machine terragrunt.hcl changes.

### `commission-and-wait.sh` — maas-status YAML writer (Layer C1)

Added at the top of the script:
- Sources `../unit_path.env` from the module cache directory
- Records `_MAAS_STATUS_STARTED_EPOCH` / `_MAAS_STATUS_STARTED_ISO` for elapsed-time tracking
- `_write_maas_status(phase, message)` helper: writes `$_DYNAMIC_DIR/unit-status/maas-<rel_full>.yaml` atomically

Wired into `_check_commissioning_done` (called every ~10s by `wait_for_condition`):
```
phase: commissioning
message: "Waiting for MaaS commissioning (elapsed: 4m12s, timeout: 2400s)"
```

### `wait-for-ready.sh` — same pattern (Layer C1)

Same helper + same wiring into `_check_ready_done` with `phase: ready`.

### `wait-for-deployed.sh` — same pattern (Layer C1)

Same helper + same wiring into `_check_deployed_done` with `phase: deploying`.

### `homelab_gui.py` — maas-status YAML reader (Layer C2)

Added "Tier 0b" immediately after the exit-status YAML scan in `local_state_watcher`. Runs every poll cycle:
- Scans `$_DYNAMIC_DIR/unit-status/maas-*.yaml`
- Files are **NOT consumed** — re-read every cycle until the apply completes
- Writes `maas_phase`, `maas_message`, `last_apply_at` to unit-state.yaml
- Advances `last_apply_at` on every update → Auto-select button tracks the node every 30s
- Skips updating `unit_build_statuses` for units already resolved by Tier 0 (exit-status YAML)
- When apply completes, `write-exit-status/run` deletes the `maas-<unit>.yaml`, stopping updates

## What the GUI now shows

During commissioning/deployment, the hover popup shows:
- `maas_phase: commissioning` (or `ready` / `deploying`)
- `maas_message: Waiting for MaaS commissioning (elapsed: 4m12s, timeout: 2400s)`
- `last_apply_at:` advancing every ~10-30s (keeps Auto-select tracking the node)

On apply completion, the maas-status file is deleted and the hover popup transitions to final `status: ok | fail`.

## Layer C3 (not implemented)

TF module `exit_status`/`exit_details` outputs — lowest priority, adds historical detail to Tier 2 validate. Deferred.
