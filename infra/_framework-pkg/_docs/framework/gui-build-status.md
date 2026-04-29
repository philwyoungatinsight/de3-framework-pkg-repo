# GUI Build Status

How the GUI (`infra/de3-gui-pkg/_application/de3-gui/`) tracks and displays per-unit
build status (the coloured dot next to each leaf unit in the explorer tree).

---

## Status values

| Value | Meaning |
|-------|---------|
| `ok` | Apply succeeded (exit 0) or GCS tfstate has `resources[]` count > 0 |
| `destroyed` | GCS tfstate exists but `resources[]` is empty (unit cleanly destroyed) |
| `fail` | Apply exited non-zero, or unit appeared in a wave run.log but has no GCS state |
| `unknown` | Local apply activity detected but GCS was unreachable at the time |
| `none` | No information yet (default before any check) |

---

## Persistent cache — `unit-state.yaml`

All status knowledge is written to a local YAML file co-located with the wave logs:

```
~/.run-waves-logs/unit-state.yaml
```

The path respects `config.wave_logs_dir` in `de3-gui-pkg.yaml` (default: `~/.run-waves-logs`).

### Schema (v2)

```yaml
schema_version: 2
units:
  <unit_path>:               # e.g. maas-pkg/_stack/maas/pwy-homelab/machines/de3-bmc
    status: ok               # ok | fail | destroyed | unknown | none
    resources_count: 3       # resource count from GCS tfstate (set by validate path)
    last_apply_exit_code: 0  # 0 = success, 1 = failure (set by Tier 0 / Tier 3)
    last_apply_at: "2026-04-14T10:15:36Z"     # when apply finished
    last_validated_at: "2026-04-14T10:30:00Z" # when GCS scan last confirmed this
    details: ""              # human-readable reason (from exit-status YAML)
    maas_phase: ""           # commissioning | ready | deploying | deployed (MaaS only)
    maas_message: ""         # live progress text during MaaS phases
    maas_hostname: ""        # MaaS system_id (populated during MaaS lifecycle)
```

### Writers

| Source | Fields written | When |
|--------|---------------|------|
| `write-exit-status/run` (Tier 0) | `status`, `last_apply_at`, `last_apply_exit_code`, `details` | After every terragrunt apply/destroy via `root.hcl` after-hook |
| MaaS lifecycle scripts (Tier 0b) | `maas_phase`, `maas_message`, `maas_hostname` | Each poll cycle during commissioning / deploy |
| `local_state_watcher` (Tier 1) | `status`, `last_apply_at` | When `.terragrunt-cache` mtime changes and GCS cat succeeds |
| `local_state_watcher` (Tier 3) | `status`, `last_apply_at`, `last_apply_exit_code` | When `$_GUI_DIR/homelab_gui_apply_*.exit` file is consumed |
| `do_validate_unit_build_statuses` | `status`, `resources_count`, `last_validated_at` | Full GCS scan via "Validate (GCS)" button |
| `do_refresh_subtree_status` | `status`, `last_validated_at` | Right-click → "Refresh build status (recursive)" |

### Reader

`on_load` reads the YAML on every page load and populates `unit_build_statuses` in Reflex
state immediately — no network calls, no blank dots on restart.

---

## Update pipeline

Tier 0 is the **primary path** for any apply run through the wave runner or terragrunt
directly. Tier 3 is the GUI-specific path for GUI-initiated applies.

```
Tier 0: exit-status YAMLs (root.hcl after-hooks)         ← PRIMARY PATH
  │  root.hcl fires two after_hooks after every apply/destroy:
  │    exit_status_mark_ok  — touches .ok-<unit> marker on success
  │    exit_status_write    — runs utilities/tg-scripts/write-exit-status/run
  │  write-exit-status/run reads the .ok- marker to determine ok vs fail
  │  Writes: $_DYNAMIC_DIR/unit-status/exit-<unit>.yaml (local, consumed by watcher)
  │       AND gs://<bucket>/unit_status/<unit_path>/<ts>.json (GCS, for cross-session recovery)
  │  → local_state_watcher consumes local file on next poll (file deleted)
  │  → writes unit_build_statuses in Reflex state
  │  → writes unit-state.yaml
  │
Tier 0b: MaaS intermediate status                         ← LIVE PROGRESS
  │  MaaS lifecycle scripts (commission-and-wait.sh, wait-for-ready.sh,
  │    wait-for-deployed.sh) write progress every poll iteration:
  │    $_DYNAMIC_DIR/unit-status/maas-<unit>.yaml
  │  Contains: phase, message, machine_id, started_at, updated_at
  │  → local_state_watcher reads (does NOT consume) on each poll
  │  → writes maas_* fields to unit-state.yaml
  │  Cleaned up by write-exit-status/run when apply completes
  │
Tier 3: GUI apply exit-code files                         ← GUI-SPECIFIC
  │  apply_unit() writes exit code to $_GUI_DIR/homelab_gui_apply_<unit>.exit
  │  local_state_watcher consumes file on next poll
  │  exit ≠ 0 → status = "fail"
  │  → writes unit_build_statuses in Reflex state + unit-state.yaml
  │
Validate (on demand): do_validate_unit_build_statuses     ← AUTHORITATIVE
     Full gsutil ls -l -r scan across all _stack/ prefixes
     mtime-cached: only re-downloads state files whose mtime changed
     Parses resources[] count → ok / destroyed
     Parses latest run.log for attempted units with no GCS state → fail
     → writes unit_build_statuses in Reflex state
     → writes unit-state.yaml (with resources_count + last_validated_at)
```

### Exit-status file schema (Tier 0)

Written to `$_DYNAMIC_DIR/unit-status/exit-<rel_path_full>.yaml`:

```yaml
unit_path: maas-pkg/_stack/maas/pwy-homelab/machines/de3-bmc
status: ok                           # ok | fail
finished_at: "2026-04-14T10:15:36Z"
```

### MaaS status file schema (Tier 0b)

Written to `$_DYNAMIC_DIR/unit-status/maas-<rel_path_full>.yaml`:

```yaml
unit_path: maas-pkg/_stack/maas/pwy-homelab/machines/de3-bmc
phase: commissioning                 # commissioning | ready | deploying | deployed
message: "Waiting for MaaS commissioning (elapsed: 134s, timeout: 2400s)"
machine_id: <system_id>
started_at: "2026-04-14T10:00:00Z"
updated_at: "2026-04-14T10:02:14Z"
```

---

## User-facing controls

### ⟳ Refresh button (fast)

Reads `unit-state.yaml` and updates the UI. Completes in milliseconds — no GCS calls.
Use this after the GUI has been running and applying units (the watcher keeps the YAML current).

### Validate (GCS) button (authoritative)

Runs the full GCS scan. Use this to:
- Populate the YAML for the first time on a new machine
- Catch state changes made outside the GUI (manual terragrunt applies, wave runs)
- Resolve `unknown` entries left by Tier 1 when GCS was temporarily unreachable

### Auto-refresh (from unit-state.yaml)

Enable via **Appearance → Show build status → Auto-refresh** checkbox.

When enabled, `local_state_watcher` reads `unit-state.yaml` and pushes updates to the
UI automatically — no button press needed.  Two trigger modes, controlled by the
interval selector that appears next to the checkbox:

| Interval | Behaviour |
|----------|-----------|
| `0 s` | On file-change only — updates within ~8 s of `unit-state.yaml` being written |
| `N s` | Every N seconds, regardless of whether the file changed |

The interval selector offers: 0 (on-change), 10, 15, 30, 60, 120, 300 seconds.
Both settings are persisted in `state/current.yaml`.

### Auto-refresh on wave completion

When the waves view detects a running wave finish (`had_running_wave` → False), it
automatically triggers `refresh_unit_build_statuses` (the fast YAML read).

---

## Per-unit log files

`apply_unit()` tees terragrunt output to:

```
~/.run-waves-logs/unit-logs/<unit-path>/YYYYMMDD-HHMMSS.log
~/.run-waves-logs/unit-logs/<unit-path>/latest.log  ← symlink to most recent
```

`latest.log` always points at the most recent run for that unit. The shell command uses
`${PIPESTATUS[0]}` (not `$?`) to capture terragrunt's exit code correctly through the
`tee` pipe.

---

## Implementation notes

- **Atomic writes**: `_write_unit_state()` writes to `.yaml.tmp` then `os.rename()`;
  protected by `_unit_state_lock` (`threading.Lock`) to prevent concurrent corruption.
- **GCS mtime cache** (`gcs_state_mtimes` Reflex state var): cleared on `on_load` so the
  next Validate does a full diff; updated by each GCS scan so subsequent Validates are
  incremental.
- **Reflex state** (`unit_build_statuses`): in-memory mirror of the YAML for the current
  session. The YAML is the durable store; Reflex state is the live UI cache.
- **`_DYNAMIC_DIR`**: resolves to `config/tmp/dynamic/` in the repo root; cleaned by
  `./run --clean-all`. Tier 0/0b files live under `unit-status/` within this dir.
- **Tier 0 hooks**: defined in `root.hcl` (lines ~404–421) as `after_hook` blocks on
  every apply/destroy. Script: `utilities/tg-scripts/write-exit-status/run`.
