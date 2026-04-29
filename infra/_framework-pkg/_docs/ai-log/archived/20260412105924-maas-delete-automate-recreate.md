# MaaS machines delete-automate-recreate for waves 9-11

**Date:** 2026-04-12
**Context:** MaaS machine entries (ms01-01, ms01-02, ms01-03) in broken state; user updating firmware on ms01-01 and ms01-03

## What was broken

- All recent runs of `pxe.maas.machine-entries` failed with `connection refused` to `10.0.10.11:5240` (timing — MaaS not yet up when partial re-runs start; no wait/readiness check in the wave on its own)
- `ms01-01`, `ms01-03`: TF state had `power_type=manual` permanently (commission script sets it temporarily but only restores on `Ready`; failed commissions left it stuck)
- `ms01-02` (eg83cp): Stuck in `Failed commissioning` — AMT unreachable (`wsman` not at `/usr/bin/wsman` on dev machine; SSL errors from machine)
- `ms01-03` (reng4p): Stuck mid-deployment (`Deploying`)
- All scripts in `maas-pkg/_wave_scripts/`, `maas-pkg/_tg_scripts/`, and `scripts/ai-only-scripts/` were using stale inventory path `ansible/terragrunt_lab_stack/hosts.yml` instead of `ansible/inventory/hosts.yml` (path renamed in commit 12187ad but not all references updated)

## Actions taken

1. **delete-automate-recreate** for ms01-01, ms01-02, ms01-03:
   - Ran `maas-machine-clean-all` with `machines_filter` to skip nuc-1 (working fine)
   - Deleted all 3 machines from MaaS
   - Removed all TF state (including configure-physical-machines null_resource)
   - nuc-1 (kdmsep, Deployed) left intact

2. **Fixed stale inventory path** in 13 `run` scripts across:
   - `scripts/ai-only-scripts/` (4 files)
   - `infra/maas-pkg/_tg_scripts/` (3 files)
   - `infra/maas-pkg/_wave_scripts/` (6 files)
   Changed: `ansible/terragrunt_lab_stack/hosts.yml` → `ansible/inventory/hosts.yml`

3. **Fixed `maas-machine-clean-all` script**:
   - Added `source "$_UTILITIES_DIR/bash/init.sh"` (was missing, caused `_activate_ansible_locally: command not found`)
   - Added `machines_filter` support to playbook (optional list; if set, only processes named machines)

4. **Fixed `power_type=manual` left in state after Failed commissioning** in `commission-and-wait.sh`:
   - Added `_amt_restore_power_type` + `_webhook_restore_power_type` calls in the `Failed*` case before retry/exit
   - Previously these were only called on `Ready`; failed commissions left `power_type=manual` in MaaS permanently

## Current state

- MaaS: only nuc-1 (kdmsep, Deployed) remains
- TF state: ms01-01, ms01-02, ms01-03 fully cleared; configure-physical-machines cleared
- Ready for re-run after firmware updates complete on ms01-01, ms01-03

## Next steps

1. Complete firmware updates on ms01-01 and ms01-03 (and ms01-02 if AMT is also broken there)
2. Power machines off
3. Re-run `./run --apply --start-at <pxe.maas.machine-entries>`
   - auto-import hook will power-cycle via AMT and PXE boot for enlistment
   - commission-and-wait.sh will commission and deploy
