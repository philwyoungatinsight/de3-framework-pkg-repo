# Rocky 9 Deploy: poweroff Late Command + ms01-02 Re-enrollment

## Summary

Fixed a "Failed deployment" race condition that caused Rocky 9 deployments on custom/amd64 machines to fail. The root cause was that MaaS's metadata server injects a `power_state: reboot` cloud-config for all deployments; after curtin signaled completion via `node_disable_pxe_url`, the machine rebooted before MaaS finished the state transition — causing it to PXE-boot back into the deployment environment and hit a 404 for a non-existent deployment kernel. The fix adds `poweroff` as the final curtin `late_command`, ensuring the machine powers off cleanly after signaling completion instead of rebooting.

Additionally resolved a double-boot commissioning race where auto-commission raced with the explicit commission API call on fresh enrollment, requiring machine annihilation and re-enrollment from New state to get a clean commissioning run.

## Changes

- **`infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2`** — Added `poweroff: [sh, -c, 'poweroff']` as the final entry in `late_commands:`, after the `maas: [wget, ..., node_disable_pxe_url]` line. Prevents the reboot race that caused "Failed deployment".

## Root Cause (deploy race)

MaaS injects `power_state: reboot` via its metadata server for all deployments. For Rocky 9 custom images, curtin handles the final power action directly (no cloud-init during deploy). After `node_disable_pxe_url` signals completion, the machine rebooted, triggering PXE while MaaS was still in "Deploying" state (regiond's state transition is async). MaaS tried to serve `custom/amd64/ga-24.04/rocky-9` deployment kernel → 404 → "Failed deployment".

## Root Cause (commission race)

MaaS auto-commissions newly enrolled machines immediately on enrollment. When the explicit `maas machine commission` call from the deploying wave fires while auto-commission is already in progress, two competing PXE boot sequences occur. This corrupts the commissioning run → "Failed commissioning". Re-enrollment to a fresh "New" state (with no competing auto-commission already running) produces a clean single-boot commissioning.

## Notes

- The double-boot commission race is mitigated by re-enrollment but not root-fixed. A follow-up (snafu-16) documents three potential root fixes: disabling MaaS auto-commission, early-exit in trigger-commission.sh when already Commissioning+on, or a wait-for-quiescence pre-check.
- The `poweroff` late_command is belt-and-suspenders: even if MaaS transitions fast enough, the machine being off after deployment is correct behavior for bare metal (AMT will power it on at next deploy/commission).
- ms01-02 system_id changed from eg6nhn → gkhdsy on re-enrollment; GCS state was cleared and TF resources re-created from scratch cleanly.
- AMT blocking pattern confirmed: `maas machine commission` call blocks ~5m32s while AMT completes the wsman PXE boot-override + power-on sequence synchronously.
