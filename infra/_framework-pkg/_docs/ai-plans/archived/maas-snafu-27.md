# Plan: maas-snafu-27 — Commission-State Verification Timeout Too Short

## Root Cause

`trigger-commission.sh` polls for 30 seconds after calling `maas machine commission`
to verify the machine entered "Commissioning" state. AMT machines require 2–3 minutes
to transition from commission API call → Commissioning status:

1. MaaS sends wsman boot override to AMT
2. AMT accepts command and powers on (or cycles)
3. Machine completes POST/BIOS (~15–30s)
4. PXE network boot downloads and boots ephemeral kernel (~30–60s)
5. Ephemeral environment contacts MaaS → status changes to "Commissioning"

Total: 90–180+ seconds. The 30s window expired while the machine was mid-PXE-boot,
so the script concluded the commission request was "rejected" and exited 1.

Evidence from wave log at 10:12–10:13:
```
[10:12:28] Polling for Commissioning state (up to 30s)...
[10:12:34]   [5s] status: New
...
[10:13:04]   [30s] status: New
[10:13:04] ERROR: Machine is in 'New' after 30s — commission API call failed.
```

But MaaS events showed "Performing PXE boot" at 14:12:30 — the commission was accepted
and the machine DID start PXE booting, just not within 30s.

Note: this snafu was NOT triggered by the "first ever" commissioning cycle. The
auto-import hook (maas.lifecycle.new wave) triggered an enlistment cycle that ran
commissioning scripts to gather hardware info, then returned the machine to "New".
The commissioning wave then ran `trigger-commission.sh` to do the full commission, but
the 30s timeout fired before the machine entered "Commissioning" state.

## Fix

Increase the commission-state verification timeout from 30s to 180s (3 minutes),
configurable via `_MAAS_COMMISSION_STATE_WAIT_TIMEOUT` env var. Poll every 10s
(instead of 5s) — no benefit in checking more often.

## Files Modified

### `infra/maas-pkg/_modules/maas_lifecycle_commission/scripts/trigger-commission.sh` — modified

Changed lines 593–612 (original):
```bash
_log "Polling for Commissioning state (up to 30s)..."
_COMM_WAIT=0
while [ "${_COMM_WAIT}" -lt 30 ]; do
    sleep 5
    ...
done
```

To use `_MAAS_COMMISSION_STATE_WAIT_TIMEOUT` (default 180s), poll every 10s.

## Open Questions

None — fix applied.

## Verification

- ms01-02 should reach "Commissioning" state within ~3 minutes of commission API call
- Log should show `[Xs] status: Commissioning` at 90–150s (not fail at 30s)
- Machine should proceed to Ready then deploy
