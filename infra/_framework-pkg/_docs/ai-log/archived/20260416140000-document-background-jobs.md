# document-background-jobs: Central index + per-package docs

## Summary

Implemented the `document-background-jobs-1` plan: created a central cross-package
index of all continuously-running processes, two per-package detail docs, and updated
script headers to match actual behavior.

## Changes

### `docs/background-jobs.md` (new)

Central index covering all 9 looping/background processes across 3 packages:
- Quick-reference diagram of what runs during a full MaaS deploy
- Full inventory table (name, location, package, trigger, poll interval, timeout, env var)
- Detailed prose description of each job
- Shared infrastructure section (`framework-utils.sh`, `$_DYNAMIC_DIR/unit-status/`, `unit_path.env`)
- Links to per-package detail docs

### `infra/maas-pkg/_docs/background-processes.md` (new)

MaaS polling scripts in detail:
- State machine position each script occupies (enrolled → commissioned → ready → deployed)
- Env vars that tune timeout and retry for each script
- Stuck detection: what the log shows when a script is hanging
- Recovery steps (always: delete machine, clear GCS state, re-run wave)
- How `unit_path.env` is sourced and what it provides
- `$_DYNAMIC_DIR/unit-status/` file types and lifecycle
- HWE kernel monitor section (ephemeral `/tmp/clear-hwe-$SYSTEM_ID.sh`)

### `infra/de3-gui-pkg/_docs/background-tasks.md` (new)

GUI background tasks in detail:
- `local_state_watcher`: Tier 0/0b/1/3 detection strategy, `unit-state.yaml` v2 schema,
  accelerated polling, `_LOCAL_STATE_WATCHER_ACCELERATE_UNTIL`
- `config_file_watcher`: what it polls, YAML vs SOPS change handling, why per-client
- `signal_inventory_ready`: one-shot, `_INVENTORY_REFRESH_COMPLETE` flag, ordering
- Shared infrastructure: `_DYNAMIC_DIR` paths, global singletons and their purpose

### `scripts/ai-only-scripts/build-watchdog/run` (modified)

Updated header comment from 4 lines to a full block documenting:
- Trigger (manual / Monitor tool)
- Poll interval and env vars
- Files read (`~/.run-waves-logs/latest/`)
- Output format with example
- MaaS state flags (`!` suffix meaning)
- Cross-reference to `build-watchdog/check`

### `homelab_gui.py` — `local_state_watcher` docstring (modified)

Replaced the outdated GCS-centric docstring with the current four-tier architecture:
Tier 0 (exit-status YAMLs), Tier 0b (MaaS intermediate YAMLs), Tier 1 (tfstate mtime + GCS cat fallback), Tier 3 (legacy GUI exit files).
