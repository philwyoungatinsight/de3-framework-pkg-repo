# Fix: AMT Power Params Restore Using TF-Provided Values

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed two bugs in the AMT commissioning path that caused MS-01 machines to lose their
`power_type=amt` configuration in MaaS after commissioning:

1. **`KeyError: 'power_address'`** in `_amt_power_on()` — crashed when MaaS returned `{}`
   for power parameters (happens when `power_type=manual` is already set).
2. **Empty AMT params after restore** — `_trigger_commission()` fetched AMT params from
   MaaS API before temporarily setting `power_type=manual`. If MaaS already had
   `power_type=manual` (from a prior failed attempt), the fetch returned `{}` and the
   restore was skipped, leaving MaaS with `power_type=manual` permanently.

## Root Cause

### Bug 1: KeyError

In `commission-and-wait.sh` `_amt_power_on()`:
```python
# BEFORE (crashed when params empty):
addr = p['power_address']

# AFTER (handles empty gracefully):
addr = p.get('power_address', '')
if not addr:
    print('WARNING: power_address not found in AMT power params — MaaS power_type may be manual; skipping wsman power-on', file=sys.stderr)
    sys.exit(0)
```

### Bug 2: Params Lost After Retry

The sequence:
1. First commission attempt: sets `power_type=manual`, saves params. But if KeyError or
   other failure prevented `_amt_power_on()` from running, machine stays off.
2. Machine commissions but returns to "New" (retry logic in `_check_commissioning_done`).
3. Second commission attempt: tries to fetch AMT params but MaaS has `power_type=manual`
   → returns `{}`. Saves empty params. Sets to manual (already manual). After
   commissioning, skips restore (empty params). MaaS left with `power_type=manual`.
4. `pre_deploy_kick` sees `power_type=manual`, can't power on machine for deploy.

## Fix

**Pass AMT power params from TF config (YAML source of truth) as env var:**

In `main.tf` `null_resource.commission` environment:
```hcl
environment = {
  MAAS_STATIC_IP        = var.provisioning_ip
  MAAS_POWER_PARAMS_B64 = base64encode(jsonencode(local._power_params))
}
```

In `commission-and-wait.sh` `_trigger_commission()`, after fetching params from MaaS API:
```bash
# Fallback to TF-provided params if MaaS returns empty (power_type=manual)
if { [ -z "$_amt_params_json" ] || [ "$_amt_params_json" = "{}" ]; } && [ -n "${MAAS_POWER_PARAMS_B64:-}" ]; then
    _amt_params_json=$(printf '%s' "${MAAS_POWER_PARAMS_B64}" | base64 -d 2>/dev/null \
        | python3 -c 'import sys,json; p=json.load(sys.stdin); print(json.dumps({k:v for k,v in p.items() if v}))' \
        2>/dev/null || echo "{}")
fi
```

This ensures AMT params are always available from YAML config (the source of truth) even
when MaaS has already been switched to `power_type=manual` by a previous attempt.

## Impact

- AMT power_type is now correctly restored after every commissioning attempt
- No more machines left in `power_type=manual` state after commissioning retries
- Deploy phase can power on machines via wsman correctly

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
- `infra/maas-pkg/_modules/maas_machine/main.tf`
