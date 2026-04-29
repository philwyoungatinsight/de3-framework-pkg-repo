# Fix: auto-import hook does not wait for 'Deploying' → 'Deployed' before importing maas_instance

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Wave 10 apply failed with `409 Conflict (No machine with system ID reng4p available.)` when
trying to CREATE `maas_instance.this` for ms01-03. The machine was already in "Deploying" state
from the previous wave run's Terraform allocation (which succeeded but then failed to poll status
due to MaaS still restarting after wave 9).

## Root Cause

The `auto-import/run` `check_and_clean_state` function handles "Deploying" machines in the `else`
branch (since "Deploying" is not in `non_deployed_statuses`). When `maas_instance.this` is NOT
in TF state and the machine is "Deploying", it tries `tofu import maas_instance.this <id>`.

The import fails because the MaaS Terraform provider requires the machine to be in "Deployed"
status to be importable as `maas_instance`:

```
Error: machine 'ms01-03' needs to be already deployed to be imported as maas_instance resource
```

After the import warning, `check_and_clean_state` returns True (no problem), and the
`before_hook` exits with code 0. The main apply then runs and tries to CREATE
`maas_instance.this`, which attempts to allocate the machine again. Since it is already
allocated/deploying, MaaS returns `409 Conflict`.

## Fix

Added a wait loop in `check_and_clean_state` when `live_status == "Deploying"` and
`maas_instance.this` is NOT in state. The loop polls every 30 seconds (up to
`_MAAS_DEPLOY_WAIT_TIMEOUT` seconds, default 1800) until the machine reaches "Deployed".
Only then does it attempt the import.

If the machine reaches "Failed deployment" or the timeout expires, it returns True early
(allows apply to proceed; the apply itself will then detect the failure state and handle it).

## General Rule

When a MaaS machine is in "Deploying" state during the auto-import before_hook:
- The machine CANNOT be imported as `maas_instance` until it is fully "Deployed"
- The main apply will get 409 Conflict if it tries to allocate a deploying machine
- The hook must wait for the deployment to complete before importing and returning

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/auto-import/run`
  (added wait loop for `live_status == "Deploying"` before attempting import)
