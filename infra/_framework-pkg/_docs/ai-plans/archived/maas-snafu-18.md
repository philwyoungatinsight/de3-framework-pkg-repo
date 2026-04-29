---
# MaaS Snafu 18: commissioning aborts to New — 30-maas-01-bmc-config queries AMT mid-commissioning

## What Broke

`maas.lifecycle.commissioning` wave — ms01-02 enters Commissioning, runs for ~9 minutes, then MaaS aborts it back to New with:

```
Thu, 16 Apr. 2026 15:50:20 | Failed to query node's BMC | (admin) - Aborting COMMISSIONING and reverting to NEW. Unable to power control the node. Please check power credentials.
```

## Root Cause (Revised)

The `30-maas-01-bmc-config` commissioning script queries/configures AMT (Intel ME) mid-commissioning. On MS-01 hardware, AMT's TLS stack can hang or fail during this query, causing MaaS to mark the commissioning as failed with "Unable to power control the node."

The initial hypothesis (region controller polling AMT post-shutdown) was incorrect — when tested with `power_type=manual`, commissioning ran for 25+ minutes without the ~9-minute abort, confirming the abort was caused by the mid-commissioning script, not post-shutdown AMT polling.

Secondary: `maas-capture-lldpd` calls `lldpctl` which exits 1 when no LLDP neighbors are present (home lab switches don't send LLDP).

## Fix

**`trigger-commission.sh`** (AMT branch):
1. Exclude `30-maas-01-bmc-config` and `maas-capture-lldpd` from commissioning scripts
2. Let MaaS drive commissioning via AMT normally (power_type=amt remains set)

No changes to power_type — changing power_type via `maas machine update` violates CLAUDE.md rule "Never use `maas machine update` to change `power_type`".

## Files Changed

- `infra/maas-pkg/_modules/maas_lifecycle_commission/scripts/trigger-commission.sh`
- `infra/maas-pkg/_modules/maas_lifecycle_ready/scripts/wait-for-ready.sh` (reverted power_type restore logic)

## Verification

1. Re-run `maas.lifecycle.commissioning` wave
2. trigger-commission.sh should show: "Commissioning scripts (excluding maas-capture-lldpd, 30-maas-01-bmc-config): ..."
3. Machine should PXE boot, run commissioning, reach Ready without aborting
4. Downstream: commission/ready/allocated/deploying/deployed waves succeed

## Open Questions

None — ready to execute.
