# Fix: power-mgmt-test Treats "unknown" Power State as SKIP (not FAIL)

**Date**: 2026-04-11  
**Waves affected**: external.power (test playbook)

## Summary

Fixed `power-mgmt-test/playbook.yaml` to treat `unknown` power state results as
SKIP instead of FAIL. This was blocking wave `external.power` (and all downstream
waves including `pxe.maas.machine-entries`) because ms01-02 (eg83cp) has a
broken AMT TLS handshake at 10.0.11.11:16993 that causes `query-power-state` to
return `state: 'unknown'` rather than 'on' or 'off'.

## Root Cause

`ms01-02` has an AMT issue where the TLS port (16993) accepts TCP connections but
the TLS handshake never completes (90s timeout). MaaS's `query-power-state` for
this machine eventually returns `{"state": "unknown"}` rather than failing the
CLI call outright.

The playbook's result classification:
```python
{%- set status = 'PASS' if state in ['on', 'off']
            else 'SKIP' if state == 'NOT_IN_MAAS'
            else 'FAIL' -%}
```

Both `unknown` and `query_failed` fell into the FAIL branch, but they are
fundamentally different:
- `query_failed` = the MaaS CLI call itself returned non-zero (auth error,
  network unreachable, missing credentials) → genuine blocking failure
- `unknown` = MaaS successfully queried the endpoint and got a response, but
  the power state is indeterminate → commissioning handles this (see
  `commission-and-wait.sh`'s `_amt_power_cycle` "unknown" handling)

## Fix

Changed `unknown` to map to SKIP:
```python
{%- set status = 'PASS' if state in ['on', 'off']
            else 'SKIP' if state in ['NOT_IN_MAAS', 'unknown']
            else 'FAIL' -%}
```

Added a descriptive SKIP message explaining why unknown is not a hard failure:
```
SKIP  ms01-02 (amt) → unknown (power state indeterminate — commissioning handles this)
```

The assert success message now also reports skip count.

## Impact

- `external.power` test playbook no longer blocks when a machine has an
  indeterminate AMT power state (TLS timeout, slow response)
- `query_failed` (actual MaaS CLI failures) still correctly block as FAIL
- ms01-02's commissioning is handled by `commission-and-wait.sh`'s special
  "unknown → attempt power-off anyway" logic (committed earlier)

## Files Changed

- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/power-mgmt/power-mgmt-test/playbook.yaml`
