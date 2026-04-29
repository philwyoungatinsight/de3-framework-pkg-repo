# document-background-jobs-1: Document All Continuously-Running Jobs

## Problem Statement

There is no single place to see all continuously-running or looping processes in the
lab stack. They span three packages (maas-pkg, de3-gui-pkg, scripts) and three trigger
mechanisms (Terraform local-exec, Reflex async tasks, Claude CronCreate). Anyone
debugging a stuck build or an unresponsive GUI has to grep across the whole repo to
understand what is supposed to be running.

---

## Inventory (discovered 2026-04-16)

### maas-pkg — Terraform local-exec polling loops

| Script | Phase | Poll interval | Default timeout |
|--------|-------|---------------|-----------------|
| `infra/maas-pkg/_tg_scripts/maas/auto-import/run` | Pre-commission (before_hook) | 10–30 s (MAC poll); 90 s (plug bounce) | 300 s |
| `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh` | Commission | 10 s | 2400 s × 3 retries |
| `infra/maas-pkg/_modules/maas_lifecycle_ready/scripts/wait-for-ready.sh` | Ready | 15 s | 2400 s |
| `infra/maas-pkg/_modules/maas_lifecycle_deployed/scripts/wait-for-deployed.sh` | Deploy | 30 s (status); 300 s (power watchdog) | 10 800 s |

All four scripts also write `$_DYNAMIC_DIR/unit-status/maas-<unit>.yaml` every poll
iteration for the GUI (added in Layer C of improve-unit-status-1).

All timeouts are configurable via env vars (`_<RESOURCE>_WAIT_TIMEOUT`). The scripts
use `wait_for_condition` from `utilities/bash/framework-utils.sh`.

### de3-gui-pkg — Reflex async background tasks (session-lifetime)

| Method | Trigger | Poll interval | Purpose |
|--------|---------|---------------|---------|
| `local_state_watcher` | Page load | 8 s (normal) / 2 s (accelerated) | Reads `$_DYNAMIC_DIR/unit-status/` and `.terragrunt-cache` tfstate mtimes; drives unit_build_statuses |
| `config_file_watcher` | Page load | 2 s | Polls stack config + secrets for mtime changes; reloads on change |
| `signal_inventory_ready` | Page load | 1 s (max 120 s) | Waits for inventory refresh to complete, then bumps UI counter |

On-demand tasks (not looping): `do_validate_unit_build_statuses`, `do_refresh_unit_build_statuses`, `do_refresh_subtree_status`, `clone_pkg_repo`, `run_refactor_preview`, `run_refactor_execute`.

### scripts — Build watchdog (Claude CronCreate)

| Script | Trigger | Poll interval | Purpose |
|--------|---------|---------------|---------|
| `scripts/ai-only-scripts/build-watchdog/check` | Claude CronCreate (cron schedule) | Cron schedule (configured per session) | One-shot entry point; reads wave logs + MaaS state; prints status summary |
| `scripts/ai-only-scripts/build-watchdog/run` | Manual or CronCreate loop | ~30 s | Continuous loop during active build; polls wave progress |

---

## Design: Three-Level Documentation

### Level 1 — Central index: `docs/background-jobs.md`

One authoritative table of all continuously-running jobs across the entire repo.
Readers should be able to answer "what is running right now during a MaaS deploy?"
in under 30 seconds.

Schema per row:
- **Name** — short human name
- **Location** — file path (relative to repo root)
- **Package** — which package owns it
- **Trigger** — how it starts (terraform hook / page load / cron / manual)
- **Poll interval** — how often it wakes up
- **Timeout** — when it gives up (or "session-lifetime" / "none")
- **Timeout env var** — name of the env var that controls the timeout
- **What it does** — one-sentence description

### Level 2 — Per-package docs: add a "Background processes" section

**`infra/maas-pkg/_docs/background-processes.md`** (new file)

Covers the four MaaS polling scripts in detail:
- State machine position each script occupies
- Env vars that tune timeout and retry
- How to tell if a script is stuck (what the log shows)
- Recovery steps (what to do when the timeout fires)
- How the script writes to `$_DYNAMIC_DIR/unit-status/` and what the GUI does with it

**`infra/de3-gui-pkg/_docs/background-tasks.md`** (new file)

Covers the three session-lifetime Reflex tasks:
- What each task polls and why
- How they interact with each other (ordering, state vars they write)
- Accelerated polling: what triggers it, what `_LOCAL_STATE_WATCHER_ACCELERATE_UNTIL` does
- How `unit-state.yaml` is written/read and what fields mean (link to schema in `improve-unit-status-1.md`)
- How the watchdog cron interacts with the GUI (it does not — they are independent)

### Level 3 — Inline header comments in each script

Each polling script should have a header comment block (30–50 lines) that covers:
- Single-sentence purpose
- Trigger (how the script starts)
- Poll interval and timeout env var
- Key env vars the script reads
- Key files the script reads/writes
- Exit codes and their meaning

The three MaaS wait scripts already have reasonable headers. The build-watchdog/run
needs its header updated. The GUI tasks lack docstrings — add them.

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `docs/background-jobs.md` | **New** — central index table |
| `infra/maas-pkg/_docs/background-processes.md` | **New** — MaaS polling scripts detail |
| `infra/de3-gui-pkg/_docs/background-tasks.md` | **New** — GUI background tasks detail |
| `scripts/ai-only-scripts/build-watchdog/run` | Update header comment |
| `homelab_gui.py` — `local_state_watcher` | Add module-level docstring |
| `homelab_gui.py` — `config_file_watcher` | Add module-level docstring |
| `homelab_gui.py` — `signal_inventory_ready` | Add module-level docstring |

---

## Implementation Order

1. Write `docs/background-jobs.md` (central index) — this is the most valuable single deliverable.
2. Write `infra/maas-pkg/_docs/background-processes.md` — MaaS lifecycle detail.
3. Write `infra/de3-gui-pkg/_docs/background-tasks.md` — GUI task detail.
4. Update header comments in `build-watchdog/run` and the three GUI tasks.

---

## Open Questions

1. **Build watchdog cron schedule**: what is the actual cron expression in use? The
   `.claude/scheduled_tasks.lock` file has a session ID but not the schedule itself.
   Check with `/schedule` or `CronList` to see if there's a registered cron job.

2. **Gate scripts**: the MaaS gate playbooks (`maas-machines-precheck`) may also run
   as pre-wave hooks. Are they long-running enough to warrant inclusion?
   Suggested answer: no — they are one-shot Ansible playbooks, not loops.

3. **HWE kernel monitor** (`/tmp/clear-hwe-$SYSTEM_ID.sh`): spawned as a background
   `setsid nohup` subprocess from `maas_machine/main.tf`. Should this be documented?
   Suggested answer: yes — add a row to the central index with "spawned by Terraform,
   runs until Deploying→Deployed transition".
