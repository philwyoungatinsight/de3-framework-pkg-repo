# Plan: maas-snafu-16 — Rocky 9 Deploy Race + Double-Boot Commission Race

## What Broke

### "Failed deployment" race condition on Rocky 9

After curtin DD'd the Rocky 9 image and ran `node_disable_pxe_url` to signal completion to MaaS, the machine rebooted instead of staying off. This triggered a PXE boot while the machine was still in "Deploying" state (the state transition in regiond is async and hadn't completed). MaaS tried to serve a deployment kernel for `custom/amd64/ga-24.04/rocky-9`, which doesn't exist → 404 → "Failed deployment".

Root cause: MaaS's metadata server injects a `power_state: reboot` cloud-config for ALL deployments. For custom images (no cloud-init running during curtin phase), curtin itself handles the final power action. The reboot caused the machine to PXE-boot back into the deploy environment before MaaS finished transitioning to "Deployed".

Fix: Added `poweroff: [sh, -c, 'poweroff']` as the LAST late_command in `curtin_userdata_rocky9.j2`, after the `maas: [wget, ..., node_disable_pxe_url]` line. This immediately powers the machine off after signaling completion — cloud-init never runs, no reboot, and MaaS transitions to "Deployed" cleanly while the machine is off.

File: `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2`

### Double-boot race condition in trigger-commission.sh (DIAGNOSED, NOT YET FIXED)

When auto-commission runs on a freshly enrolled machine at the same time as the explicit `maas machine commission` call from the deploying wave, two competing PXE boots occur. The second boot while the commissioning scripts are already running corrupts the commissioning run, resulting in "Failed commissioning" state.

Root cause: MaaS auto-commissions newly enrolled machines by default. When the enrollment import hook fires, the machine jumps from New → Commissioning immediately. The `commission_trigger` null_resource then calls `maas machine commission` explicitly, which may interfere with or re-trigger the already-in-progress commissioning.

**Observed symptom**: machine enters "Failed commissioning" state after first deploy attempt, requiring annihilation + re-enrollment.

**Current mitigation**: On re-enrollment (fresh New state with no competing auto-commission), the deployment succeeds. The trigger-commission.sh correctly handles the "Commissioning + power-on" case (exits 0) and "Commissioning + power-off" case (abort + retrigger).

**Root fix needed** (not yet implemented): 
- Option A: Disable MaaS auto-commissioning on enrollment (configure `enable_kernel_crash_dump: false` + disable auto-commission in MaaS settings)
- Option B: In trigger-commission.sh, when machine is already Commissioning with BMC=on, exit 0 immediately (treat as "already in progress, don't interfere")
- Option C: In the commission module, add a pre-check that waits for any in-progress commissioning to complete before calling the explicit commission API

Current state: the fix for the "Failed deployment" race (snafu-16 primary) has been deployed and verified. The double-boot race (secondary) is mitigated by re-enrollment but not root-fixed.

## Files Changed

- **`infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2`**  
  Added `poweroff: [sh, -c, 'poweroff']` as last entry in `late_commands:`, after the `maas:` wget line.  
  This prevents the post-deploy reboot that caused "Failed deployment" race.

## Remaining Gaps

1. **Double-boot commission race**: trigger-commission.sh can cause double-boot when auto-commission races with explicit commission API call on fresh enrollment. See Option A/B/C above. Needs a follow-up snafu fix before this becomes a persistent reliability problem.

2. **wait-for-deployed poweroff tolerance**: The deployed:post gate currently skips SSH checks for machines that are powered off (AMT=unreachable). This is correct behavior post-poweroff, but should be explicitly documented in the gate logic.

## Verification

Deployment of ms01-02 (system_id: gkhdsy) as Rocky 9 succeeded:
- deploy_trigger fired at 22:14:02
- Deploying state confirmed at 22:14:24  
- `poweroff` late_command prevented reboot race
- MaaS transitioned to Deployed state cleanly
- deployed:post gate PASSED
