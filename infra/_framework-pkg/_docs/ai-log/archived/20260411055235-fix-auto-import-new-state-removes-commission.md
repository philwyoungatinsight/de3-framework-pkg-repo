# Fix: Auto-import Hook Removes null_resource.commission When Machine is "New"

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed a bug in `infra/maas-pkg/_tg_scripts/maas/auto-import/run` where a machine at
"New" status (post-disk-erase) would have `maas_instance.this` removed from TF state but
`null_resource.commission` left in state. TF would then skip re-commissioning (triggers
unchanged) and attempt to deploy a machine still at "New" — causing the deploy to fail.

## Root Cause

When a MaaS machine is released with disk erase enabled (default), it transitions:
`Deployed → Releasing → Erasing → New`

The auto-import hook's non-deployed handler correctly removes `maas_instance.this` from
state so TF redeploys. However, `null_resource.commission` has triggers:
```hcl
triggers = {
  system_id  = maas_machine.this.id
  power_type = maas_machine.this.power_type
}
```

Neither `system_id` nor `power_type` changes after a disk erase, so TF treats
`null_resource.commission` as already "created" and skips running `commission-and-wait.sh`.
TF then proceeds directly to creating `maas_instance.this` — but the machine is at "New"
(not "Ready"), so the MaaS deploy fails.

## Observed Failure Chain

1. ms01-01 (eawest) was "Deployed" when the auto-import hook ran → hook skipped
2. TF destroyed `maas_instance.this` → MaaS released eawest → disk erase → "New"
3. TF's destroy failed: "unexpected state 'New', wanted target 'Ready'"
4. In the next retry, hook sees eawest at "New" → removes `maas_instance.this`
5. TF plans: create `maas_instance.this` (no re-commission because triggers unchanged)
6. Deploy would fail (machine at "New", not "Ready")

## Fix

Added logic to remove `null_resource.commission` from state when `live_status == "New"`:

```python
# When a machine is at "New" it has been erased and needs full re-commissioning
# from scratch. null_resource.commission has triggers {system_id, power_type}
# which don't change after erase, so TF would NOT recreate it — causing
# maas_instance.this creation to fail (machine at "New", not "Ready").
# Remove null_resource.commission from state so TF recreates it → re-runs
# commission-and-wait.sh → machine commissions from "New" to "Ready".
if live_status == "New":
    rc_comm, _ = _tofu_out("state", "show", "null_resource.commission")
    if rc_comm == 0:
        print(
            f"{LOG} machine {stored_id} is 'New' (post-erase) — removing "
            "null_resource.commission to force re-commissioning."
        )
        _tofu("state", "rm", "null_resource.commission")
```

## Impact

- Machines that end up at "New" after disk erase (release) will be fully re-commissioned
  before deploy on the next wave retry
- `null_resource.commission` is recreated → `commission-and-wait.sh` runs from scratch
- Machine commissions from "New" → "Ready" → `maas_instance.this` deploy succeeds

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/auto-import/run`
