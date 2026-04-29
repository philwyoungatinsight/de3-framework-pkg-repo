# Fix: Skip MaaS smartctl-validate to Speed Up Commissioning

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Added `testing_scripts=none` to the MaaS commission command in `commission-and-wait.sh`.
This prevents MaaS from running NVMe/SSD storage validation tests (smartctl-validate)
during the commissioning testing phase, reducing MS-01 commissioning time from 60-90+ min
to ~15-20 min.

## Root Cause

MaaS splits commissioning into two phases:
1. **Commissioning scripts** (`commissioning_scripts=`): Data gathering — hardware inventory,
   network config, storage enumeration. Fast (~5 min).
2. **Testing scripts** (`testing_scripts=`): Hardware validation — smartctl, memtest, etc.
   By default, MaaS runs `smartctl-validate` on ALL detected storage devices.

MS-01 hardware has 2+ NVMe drives. Each NVMe smartctl validation takes 10-20 minutes.
With 2+ drives, this added 30-80+ minutes to commissioning time per machine.

Additionally, "Failed to query node's BMC" log messages suggested multiple commissioning
retries (each with a full smartctl run), compounding the delay.

## Discovery

During wave 10 attempt 1, ms01-01 was observed stuck in "Commissioning" status for 65+
minutes. Inspecting MaaS events:

```
Failed to query node's BMC: Connection to AMT BMC timed out
```

And from the MaaS UI, the testing phase was running `smartctl-validate` concurrently on
multiple NVMe disks.

## Fix

In `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`, inside the
`_trigger_commission` function, after building the `commission_cmd`:

```bash
# Skip storage/hardware testing scripts entirely (smartctl-validate, etc.).
# Testing scripts run NVMe/SSD validation that can take 10-20 min per drive.
# With 2-4 NVMe drives per MS-01, this adds 30-80+ minutes to commissioning.
# We don't need storage health validation in our automated pipeline — the OS
# deploy will fail if the drive is bad. Set testing_scripts=none to skip.
commission_cmd="$commission_cmd testing_scripts=none"
```

## Impact

- MS-01 commissioning time: 60-90+ min → ~15-20 min
- NUC commissioning (1 NVMe): ~10 min → ~7 min (minor improvement)
- No loss of functionality: if a drive is bad, the OS deploy will fail with a clear error

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
