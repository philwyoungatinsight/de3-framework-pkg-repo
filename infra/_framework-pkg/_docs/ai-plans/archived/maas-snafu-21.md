# Plan: maas-snafu-21 — Auto-Enrollment Commissioning Runs maas-capture-lldpd

## Objective

ms01-02 commissioning fails with "maas-capture-lldpd has run past it's timeout(0:01:00)".
The `trigger-commission.sh` script already excludes `maas-capture-lldpd` from commissioning,
but the exclusion was not applied because the script exited early when it saw the machine
was already in "Commissioning" state with a reachable provisioning IP.

## Context

**Root cause chain:**
1. After ms01-02 enrolls via `maas.lifecycle.new`, MaaS automatically starts an "auto-enrollment
   commissioning" with ALL scripts — including `maas-capture-lldpd`.
2. `maas-capture-lldpd` times out in 1 minute (no LLDP neighbors on our home lab switch).
   This script runs early (~5 min into commissioning) but MaaS doesn't mark the machine
   failed until ALL scripts complete.
3. When our `maas.lifecycle.commissioning` wave runs, `trigger-commission.sh` sees:
   - Machine status = "Commissioning"
   - Power = on
   - Provisioning IP (10.0.12.x) reachable
   → Script concluded "machine is genuinely in the commissioning environment" and exited 0.
4. The auto-enrollment commissioning completes with lldpd failure → "Failed commissioning".

**Why the early exit was wrong:**
The auto-enrollment commissioning uses ALL scripts (MaaS default). Our commissioning command
excludes `maas-capture-lldpd` and `30-maas-01-bmc-config`. There is no way to tell from
outside whether an in-progress commissioning is using our exclusion list or not. Trusting
that any in-progress commissioning is "correct" is wrong.

**Evidence:**
```
Thu, 16 Apr. 2026 22:00:12 ERROR | maas-capture-lldpd has run past it's timeout(0:01:00)
```

## Open Questions

None — ready to proceed.

## Files Created / Modified

### `infra/maas-pkg/_modules/maas_lifecycle_commission/scripts/trigger-commission.sh` — modified

Removed the early `exit 0` when "Commissioning + reachable provisioning IP". Now both the
"has provisioning IP" and "no provisioning IP" paths fall through to abort + re-commission
with our exclusion list.

**Before:**
```bash
if [ "${_found_prov}" = "true" ]; then
    _log "ACTION: Machine is genuinely in the commissioning environment. Exit 0."
    exit 0
fi
# No provisioning IP...
_log "ACTION: Abort and re-trigger commissioning with script exclusions."
```

**After:**
Both cases (provisioning IP found or not found) now fall through to the abort+re-trigger
block. If the machine is actively commissioning, we abort it and re-commission with our
exclusion list. This costs ~10-15 min if the previous commissioning was already using
the right exclusion list, but guarantees correctness.

## Execution Order

1. Apply `trigger-commission.sh` fix (done)
2. Annihilate ms01-02 (system_id ggepx4): delete from MaaS + wipe GCS TF state
3. Kill any running build
4. Re-run `./run -b -w "*maas*"`

## Verification

- commissioning-apply log shows: "Aborting in-progress commissioning and re-triggering with script exclusions"
- `maas-capture-lldpd` does NOT appear in the commissioning run
- Machine reaches "Ready" state after commissioning
- ms01-02 successfully deployed (Rocky 9)
