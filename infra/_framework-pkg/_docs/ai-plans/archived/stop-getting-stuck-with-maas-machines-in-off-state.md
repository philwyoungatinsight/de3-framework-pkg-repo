# Plan: stop-getting-stuck-with-maas-machines-in-off-state

## Root Cause

`trigger-commission.sh` Step 4 sets `power_type=manual` for **ALL** machines before
triggering commissioning. This is catastrophic for `webhook`/`smart_plug` machines:

- **AMT machines**: setting `manual` prevents MaaS from racing on BMC power during
  commissioning (correct and necessary).
- **webhook/smart_plug machines**: the webhook IS the power mechanism. MaaS uses
  `power_on_uri` to turn the machine on when commissioning starts. If `power_type=manual`
  is set first, MaaS sees "manual" and just waits for a human to flip the switch.
  The machine never powers on. Commissioning times out after 90 minutes → "Failed commissioning".

This has caused nuc-1 (`power_type: smart_plug`) to get stuck every single time
commissioning is triggered — the machine sits OFF in "Commissioning" state indefinitely.

## What Breaks

1. `trigger-commission.sh` Step 4: `maas machine update $SYSTEM_ID power_type=manual` (unconditional)
2. Step 5: `maas machine commission $SYSTEM_ID` → MaaS powers on via manual (does nothing)
3. Step 6: Restores webhook — but MaaS already issued (no-op) power-on. Machine stays OFF.
4. Result: nuc-1 stuck in Commissioning + power=off/unknown for 90 minutes → Failed commissioning
5. The "Failed commissioning" retry loop then re-runs from the same broken script → infinite loop

## Fix: Make Step 4 conditional on power_type

Only set `power_type=manual` for machine types where BMC racing is a real concern
(AMT, IPMI, Redfish — types with active BMC controllers that MaaS can call during commissioning).

For `webhook`, `smart_plug`, `manual`, `proxmox`: skip the manual override entirely.
The machine either powers itself on (webhook), doesn't need BMC management (manual/proxmox),
or has no BMC at all.

## Files to Modify

### `infra/maas-pkg/_modules/maas_lifecycle_commission/scripts/trigger-commission.sh` — modify

**Step 4**: Make conditional. Only set `power_type=manual` if `POWER_TYPE` is an active
BMC type (`amt`, `ipmi`, `redfish`).

```bash
# ---------------------------------------------------------------------------
# Set power_type=manual temporarily (BMC-managed machines only)
# ---------------------------------------------------------------------------
_log ""
_log "--- Step 4: Set power_type=manual temporarily ---"
_BMC_TYPES="amt ipmi redfish"
if echo "${_BMC_TYPES}" | grep -qw "${POWER_TYPE:-}"; then
    _log "power_type=${POWER_TYPE} (BMC-managed) — setting manual to prevent BMC racing during commissioning."
    _ssh_run "maas machine update power_type=manual for ${SYSTEM_ID}" \
        "${_MAAS} maas-admin machine update ${SYSTEM_ID} power_type=manual 2>&1"
    _MANUAL_OVERRIDE=true
else
    _log "power_type=${POWER_TYPE} — skipping manual override (not a BMC-managed type; webhook/smart_plug/proxmox power on normally)."
    _MANUAL_OVERRIDE=false
fi
```

**Step 6**: Only restore if `_MANUAL_OVERRIDE=true`.

```bash
_log ""
_log "--- Step 6: Restore original power configuration ---"
if [ "${_MANUAL_OVERRIDE}" = "true" ] && [ -n "${POWER_TYPE:-}" ] && [ "${POWER_TYPE}" != "manual" ]; then
    # ... existing Python subprocess restore logic ...
else
    _log "No manual override was applied — power_type unchanged, nothing to restore."
fi
```

## Recovery for Current Stuck State

nuc-1 is currently stuck: Commissioning + power=unknown (OFF).
power_type is `webhook` (correctly set). MaaS can power it on.

One-time recovery (after fixing trigger-commission.sh):
```bash
# Power on nuc-1 via MaaS (uses webhook/smart_plug)
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "sudo /usr/bin/snap run maas maas-admin machine power-on qh6dq6"
```

nuc-1 will PXE boot and complete commissioning. Then restart the build.

## Verification

After fix, on a fresh commissioning run:
1. nuc-1 should NOT be set to `power_type=manual` at any point
2. `commissioning:post` gate: nuc-1 should be Commissioning with BMC=on
3. `ready:post` gate: nuc-1 should reach Ready without timing out
4. No more "Failed commissioning" loops caused by machine never powering on

## Execution Order

1. Modify `trigger-commission.sh` (Steps 4 and 6)
2. Power on nuc-1 manually via MaaS API (one-time recovery)
3. Restart build — nuc-1 should commission successfully without manual intervention
