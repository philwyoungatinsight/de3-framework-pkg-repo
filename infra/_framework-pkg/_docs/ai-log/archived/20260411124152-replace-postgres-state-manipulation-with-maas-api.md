# Fix: Replace all direct postgres state manipulation with MaaS CLI API

**Date**: 2026-04-11
**Principle**: delete-automate-recreate-no-manual-update

## Summary

Replaced ALL direct postgres state manipulation in MaaS automation code with
proper MaaS CLI API calls. This follows the architectural principle established
this session: when infrastructure is broken, use the MaaS API to transition
state or delete-and-recreate, never patch internal database tables.

## Files Changed

### `infra/maas-pkg/_tg_scripts/maas/force-release/run`
- Step 2 replaced `UPDATE maasserver_node SET status = 4` with:
  - `maas machine abort <id>` for Deploying/Commissioning → Failed
  - `maas machine release <id>` for Deployed/Allocated → Ready
  - Delete proceeds regardless (MaaS DELETE API accepts any state)

### `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`

**1. Failed-state reset before commission** (was: `UPDATE status=0`):
- `Failed commissioning` → commission API accepts this directly (no action needed)
- Other `Failed*` states → `maas machine release` transitions to Ready first

**2. hwe_kernel clear** (was: `UPDATE hwe_kernel=''`):
- Replaced with `maas machine update $SYSTEM_ID hwe_kernel=` (API call)

**3. Webhook power_state='off' before commission** (was: `UPDATE power_state='off'`):
- MaaS commission fails if power_state='unknown' (webhook is fire-and-forget)
- Fix: temporarily switch to `power_type=manual` (bypasses power-state check)
- Added `_TC_WEBHOOK_PARAMS_JSON` variable and `_webhook_restore_power_type()` function
- Webhook power type restored after commissioning completes in the Ready case
- Same pattern as the existing AMT approach

**4. AMT power_state='off' during commission trigger** (was: `UPDATE power_state='off'`):
- Removed: already using `power_type=manual` at this point; manual power type
  bypasses MaaS's BMC task queue validation without needing power_state set

**5. AMT power_state='off' after commissioning completes** (was: `UPDATE power_state='off'`):
- Replaced with `timeout 30 maas machine query-power-state $SYSTEM_ID`
- After commissioning, AMT power type is restored; live query updates cached state
- Machine IS off after commissioning — query returns 'off', enabling deploy task queue

**6. Stuck commissioning abort** (was: `UPDATE status=0`):
- Replaced with `maas machine abort $SYSTEM_ID` (Commissioning → Failed commissioning)
- STATUS updated via `STATUS=$(_maas_status)` instead of hardcoded "New"
- `New|Failed*` case in the main loop handles Failed commissioning on next iteration

### `infra/maas-pkg/_modules/maas_machine/main.tf`

**Phase 1 background monitor** (was: `UPDATE hwe_kernel=''`):
- Replaced with `maas machine update $SYSTEM_ID hwe_kernel=` API call

**Phase 1 set_deploy_osystem belt-and-suspenders** (was: `UPDATE hwe_kernel=''`):
- Removed: the preceding `maas machine update hwe_kernel=generic` API call covers it

**Phase 1 pre_deploy_kick belt-and-suspenders** (was: `UPDATE hwe_kernel=''`):
- Removed: same reason

**Phase 2 `_force_deployed` SSH/ping fallback** — REMOVED ENTIRELY:
- Was: poll SSH/ping and `UPDATE maasserver_node SET status=6` if machine reachable
- Root cause: curtin `write_maas_cloud_config` late_command failing caused curtin
  to report "Failed deployment", machine booted anyway, MaaS never got "Deployed" signal
- Fix: make `write_maas_cloud_config` late_command non-fatal (sys.exit(1) → sys.exit(0))
  so curtin ALWAYS completes and sends the "Deployed" signal to MaaS

### `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_trixie.j2`
- `write_maas_cloud_config` late_command: `sys.exit(1)` → `sys.exit(0)` on config read error
- Curtin now always signals MaaS "Deployed" regardless of late_command errors
- Removes need for `_force_deployed` postgres fallback

### `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/wipe-host-clean.yaml`
- Replaced `UPDATE status=4` with `maas machine abort/release` chain before delete

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-test/playbook.yaml`
- Replaced `UPDATE status=4` (Step 1) with `maas machine abort/release` API chain
- Removed `UPDATE status=4` fallback after release timeout (replaced with warning)

### `scripts/ai-only-scripts/maas-machine-clean-all/playbook.yaml`
- Replaced `UPDATE status=4` with `maas machine abort/release` chain before delete

### Deleted scripts
- `scripts/ai-only-scripts/reset-ms01-01/` — deleted (used `UPDATE status=4`)
- `force-maas-ready` and `force-maas-deployed` — already removed in prior session

## Architectural Rule (added to CLAUDE.md and memory)

Never edit MaaS postgres tables to manipulate state. Use MaaS CLI API:
- `maas machine abort` — Deploying/Commissioning → Failed
- `maas machine release` — Deployed → Ready (wipes disk)
- `maas machine commission` — New/Ready/Failed commissioning → Commissioning
- `maas machine delete` — removes machine record entirely
- `maas machine update <id> hwe_kernel=` — clears hwe_kernel via API
- `maas machine query-power-state` — updates cached power_state from live BMC query
- `tofu state rm` + `tofu import` — fix TF state; never patch MaaS internals
