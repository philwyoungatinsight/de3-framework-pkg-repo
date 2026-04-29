# Background Jobs — Continuously-Running Processes

All looping, polling, and long-lived background processes in the lab stack.
Use this as the first stop when debugging a stuck build or unresponsive GUI.

---

## Quick reference: what runs during a full MaaS deploy

```
terragrunt apply (maas_machine)
  └─ before_hook → auto-import/run          polls MAC + bounces smart-plug until machine enrolls
  └─ local-exec  → commission-and-wait.sh   powers on + waits for commissioning to finish
  └─ local-exec  → clear-hwe monitor        background subprocess; clears hwe_kernel once Deploying

terragrunt apply (maas_lifecycle_ready)
  └─ local-exec  → wait-for-ready.sh        waits for Ready state; configures interfaces

terragrunt apply (maas_lifecycle_deploy → maas_lifecycle_deployed)
  └─ local-exec  → wait-for-deployed.sh     waits for Deployed; power-on watchdog every 5 min

GUI (open in browser)
  └─ background  → local_state_watcher          reads $_DYNAMIC_DIR/unit-status/ for real-time dot updates
  └─ background  → sync_unit_status_from_gcs    pulls unit status from GCS on page load
  └─ background  → sync_wave_status_from_gcs    pulls wave history from GCS on page load
  └─ background  → config_file_watcher          mtime-polls stack YAML + SOPS secrets
  └─ background  → signal_inventory_ready       signals when inventory cache is populated
```

---

## Full inventory

| Name | Location | Package | Trigger | Poll interval | Timeout | Timeout env var |
|------|----------|---------|---------|---------------|---------|-----------------|
| Auto-import | `infra/maas-pkg/_tg_scripts/maas/auto-import/run` | maas-pkg | Terragrunt `before_hook` on `maas_machine` | 10–30 s (MAC); 90 s (plug bounce) | 300 s | `_MAAS_AUTO_IMPORT_TIMEOUT` |
| Commission & wait | `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh` | maas-pkg | Terraform `local-exec` on `null_resource.commission` | 10 s | 2400 s × 3 retries | `_COMMISSION_WAIT_TIMEOUT`, `_COMMISSION_MAX_RETRIES` |
| HWE kernel monitor | `/tmp/clear-hwe-$SYSTEM_ID.sh` (ephemeral, from `maas_machine/main.tf`) | maas-pkg | Spawned by Terraform `local-exec` as `setsid nohup` background process | 30 s | Exits when `Deploying→Deployed` | — |
| Wait for Ready | `infra/maas-pkg/_modules/maas_lifecycle_ready/scripts/wait-for-ready.sh` | maas-pkg | Terraform `local-exec` on `null_resource.wait_ready` | 15 s | 2400 s | `_COMMISSION_WAIT_TIMEOUT` |
| Wait for Deployed (+ power watchdog) | `infra/maas-pkg/_modules/maas_lifecycle_deployed/scripts/wait-for-deployed.sh` | maas-pkg | Terraform `local-exec` on `null_resource.wait_deployed` | 30 s (status); 300 s (power check) | 10 800 s | `_DEPLOY_WAIT_TIMEOUT` |
| GUI local state watcher | `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — `local_state_watcher` | de3-gui-pkg | Page load (process-level singleton) | 8 s normal; 2 s accelerated | Session lifetime | — |
| GUI unit status GCS sync | `homelab_gui.py` — `sync_unit_status_from_gcs` | de3-gui-pkg | Page load (one-shot) | — | One-shot | — |
| GUI wave status GCS sync | `homelab_gui.py` — `sync_wave_status_from_gcs` | de3-gui-pkg | Page load (one-shot) | — | One-shot | — |
| GUI config file watcher | `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — `config_file_watcher` | de3-gui-pkg | Page load (per client) | 2 s | Session lifetime | — |
| GUI inventory ready signal | `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — `signal_inventory_ready` | de3-gui-pkg | Page load (per client) | 1 s | 120 s max, then exits | — |
| Build watchdog (cron) | `scripts/ai-only-scripts/build-watchdog/check` | scripts | Claude `CronCreate` (1-minute cron) | 1 min | None — active while `./run --build` is running | — |
| Build watchdog (loop) | `scripts/ai-only-scripts/build-watchdog/run` | scripts | Manual or via Claude `Monitor` | 30 s | None — Ctrl-C to stop | — |

---

## What each job does

### MaaS polling scripts

See `infra/maas-pkg/_docs/background-processes.md` for full detail on each script,
including env vars, status file schema, stuck-detection, and recovery steps.

Summary:
- **Auto-import** — waits for machine MAC to appear in MaaS; bounces smart plug every 90 s
- **Commission & wait** — triggers commission, polls for Ready/Failed; retries up to 3×
- **HWE kernel monitor** — clears `hwe_kernel` once machine transitions to Deploying; exits on Deployed
- **Wait for Ready** — polls for Ready after commission; configures network interfaces once Ready
- **Wait for Deployed** — polls for Deployed; power-on watchdog every 5 min if machine powers off mid-deploy

All MaaS polling scripts write `$_DYNAMIC_DIR/unit-status/maas-<unit>.yaml` on each iteration;
the GUI reads these for live phase/message display in the build status hover popup.

### GUI local state watcher (`local_state_watcher`)
Process-level singleton (one per GUI server process). Three-tier status detection:
- **Tier 0**: consumes `$_DYNAMIC_DIR/unit-status/exit-*.yaml` (written by root.hcl
  after_hook on every apply/destroy) — the primary status source; no GCS calls
- **Tier 0b**: reads `$_DYNAMIC_DIR/unit-status/maas-*.yaml` (written by MaaS scripts
  above) — provides live phase/message during long-running commission/deploy
- **Tier 3**: reads `$_GUI_DIR/homelab_gui_apply_*.exit` files written by `apply_unit()`
Accelerates from 8 s → 2 s for 60 s when a GUI-initiated apply fires.

### GUI GCS sync tasks (`sync_unit_status_from_gcs`, `sync_wave_status_from_gcs`)
One-shot tasks fired on each page load. Pull unit build statuses and wave phase history
from GCS (`unit_status/` and `wave_status/` prefixes) written by `write-exit-status/run`
and the wave runner. Recover dots and wave history from before the current GUI session.
Use ISO timestamp cursors (`unit_status_sync_after`, `wave_status_sync_after`) for
incremental fetches after the first load.

### GUI config file watcher (`config_file_watcher`)
One instance per connected browser client. Polls mtime of all stack config YAMLs and
the SOPS secrets file every 2 s. Reloads config and refreshes UI state when any file changes.

### GUI inventory ready signal (`signal_inventory_ready`)
Fired once per page load. Waits up to 120 s for the background inventory refresh to
complete (flag `_INVENTORY_REFRESH_COMPLETE`), then bumps `inventory_refresh_counter`
to trigger a UI re-render. Ensures SSH buttons appear even when the cache was empty at
initial startup. Exits after signalling (not a persistent loop).

### Build watchdog — cron (`build-watchdog/check`)
One-shot script registered via Claude's `CronCreate` tool on a 1-minute cron schedule.
SSHes to the MaaS server, reads machine states, checks wave logs for errors, and appends
one status line to `~/.build-watchdog.log`. Includes a session guard so only one Claude
session acts on a given build at a time (90 s heartbeat via `~/.build-watchdog.session`).

### Build watchdog — loop (`build-watchdog/run`)
Continuous monitoring loop run manually or via Claude's `Monitor` tool. Prints one
status line every 30 s showing: build running/stopped, MaaS machine states (with `!`
flags for unexpected states), and the last meaningful line from the active wave log.

---

## Shared infrastructure

- **`utilities/bash/framework-utils.sh`** — provides `wait_for_condition()` used by all
  four MaaS polling scripts. Signature:
  `wait_for_condition <desc> <check_cmd> <timeout_var> <default_s> <interval_s>`
- **`$_DYNAMIC_DIR/unit-status/`** — shared directory for real-time status files:
  - `exit-<unit>.yaml` — written by `utilities/tg-scripts/write-exit-status/run` on apply/destroy completion
  - `maas-<unit>.yaml` — written by MaaS polling scripts on each iteration; read by GUI
- **`unit_path.env`** — generated into each module cache directory by `root.hcl`; sourced by MaaS scripts to obtain `UNIT_PATH` and `UNIT_REL_FULL`

---

## Per-package detail

- MaaS polling scripts: `infra/maas-pkg/_docs/background-processes.md`
- GUI background tasks: `infra/de3-gui-pkg/_docs/background-tasks.md`
