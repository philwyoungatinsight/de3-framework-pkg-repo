# Fix MaaS Automation: Stale Locks, AMT Hard Reset, SSH known_hosts, _clean_all Script

**Date:** 2026-04-10  
**Session:** Continuation of commissioning/deployment debugging

## Problem

MaaS automation had been unreliable for weeks, causing machines to not commission or
deploy without manual intervention. Root-cause analysis identified four distinct failures:

## Root Cause 1: Stale GCS State Locks

Crashed Terragrunt runs left `.tflock` files in GCS, causing `tofu state show` to fail
with a lock error instead of returning state contents. This caused `check_and_clean_state`
in `auto-import/run` to incorrectly return `False`, so the hook tried to re-import a
machine that was already in state.

**Fix:** Removed stale locks manually. Added code in `_find_and_import` to handle the
`"Resource already managed"` error by returning `True` (state exists, skip re-import)
instead of silently returning `False` and timing out the 300s poll loop.

**File:** `infra/maas-pkg/_tg_scripts/maas/auto-import/run`

## Root Cause 2: Silent `tofu import` Errors

`_find_and_import` used `capture_output=True` but never printed stderr when import failed.
The "Resource already managed" error was invisible, making debugging impossible.

**Fix:** Modified `_find_and_import` to print both stdout and stderr when import returns
non-zero, so errors are visible in the Terragrunt hook output.

## Root Cause 3: SSH known_hosts Blocking API Queries

`_ssh()` and `_ssh_ok()` used `StrictHostKeyChecking=no` but lacked `UserKnownHostsFile=/dev/null`.
When the MaaS server is rebuilt with a new SSH host key, `StrictHostKeyChecking=no` accepts
NEW hosts but still blocks on CHANGED keys in `~/.ssh/known_hosts`. This caused the MaaS
API calls (`sudo maas maas-admin machines read`) to silently return `None`, making
`_find_and_import` return `False` and the hook poll until timeout.

**Fix:** Added `-o UserKnownHostsFile=/dev/null` to all three SSH call sites in `auto-import/run`
(`_ssh`, `_ssh_ok`, `power_cycle_amt`). Also added CLAUDE.md rule and memory entry:
> ALWAYS use both `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null` together.
> `StrictHostKeyChecking=no` alone is NOT enough.

**Files:**
- `infra/maas-pkg/_tg_scripts/maas/auto-import/run`
- `CLAUDE.md` (Conventions section)

## Root Cause 4: AMT PowerState=2 Fails on Running Machines

`power-on-machine.yaml` sent `PowerState=2` (power on from off) unconditionally. When a
machine is already running a deployed OS, PowerState=2 is invalid (no-op or error) — it
doesn't trigger a reboot. The wsman call returned non-zero, causing the Ansible task to fail.

**Fix:** Changed to try `PowerState=10` (hard reset, works when machine is ON) first, then
fall back to `PowerState=2` (works when machine is OFF). Confirmed via direct wsman test on
ms01-01 at 10.0.11.10 that PowerState=10 succeeds (ReturnValue=0).

**File:** `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/power-on-machine.yaml`

## New Feature: maas-pkg _clean_all Script

Added `infra/maas-pkg/_clean_all/run` — a pre-Terraform-destroy purge script that deletes
all MaaS machine records via SSH to the MaaS server before Terraform destroy runs.

**Why needed:** After each `make clean-all`, machines that completed deployment remain in
MaaS with their old system_ids. On the next `make`, the auto-import hook finds the machine
in MaaS but the system_id doesn't match what's in Terraform state (which was wiped), causing
confusing failures. Deleting machines from MaaS first ensures a clean slate.

The script:
1. Extracts the MaaS server IP from `_provider_maas_api_url` in config_params
2. SSHs to the MaaS server and lists all machines
3. Releases any Deployed machines (required before delete)
4. Deletes all machines

Added `maas-pkg` to `pre_destroy_order` in `config/framework.yaml` so the script runs
before Terraform destroy in `make clean-all`.

**Files:**
- `infra/maas-pkg/_clean_all/run` (new)
- `config/framework.yaml` (added maas-pkg to pre_destroy_order)

## AMT Status for ms01 Machines

Confirmed: Intel AMT now works for ms01-01 (10.0.11.10). Previously, only smart plugs were
used because AMT power-on was attempted with PowerState=2 which fails on running machines.
With the PowerState=10 fallback, AMT hard reset works correctly.

ms01-02 and ms01-03 still use smart_plug as primary power type (no change needed there,
they have working Tapo plugs).

## Result

All 4 physical machines (ms01-01, ms01-02, ms01-03, nuc-1) were in Commissioning state
at end of session. ms01-01 (system_id 4py7ff) was in "New" state (recently enlisted via
AMT hard reset, not yet commissioned).
