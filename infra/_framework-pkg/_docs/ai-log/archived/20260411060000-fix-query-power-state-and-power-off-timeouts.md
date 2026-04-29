# Fix: _query_actual_power_state and _amt_power_cycle power-off Timeouts

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed two additional hang vectors in `commission-and-wait.sh` that caused wsman zombie
processes to accumulate on the MaaS server when AMT TLS at 10.0.11.11:16993 hangs:

1. **`_query_actual_power_state` had no timeout** — `maas machine query-power-state`
   triggers the MaaS AMT driver which calls wsman. When the TLS handshake hangs
   indefinitely, every `_amt_check_off` poll in `wait_for_condition` spawns a new
   zombie wsman process (root-owned, MaaS AMT driver, no timeout).
2. **`_amt_power_cycle` power-off had no timeout** — `maas machine power-off` also
   goes through the MaaS AMT driver → wsman → same TLS hang issue.

## Root Causes

### Bug 1: No timeout on `_query_actual_power_state`

Every call path that checks whether the machine is on/off goes through
`_query_actual_power_state` → `sudo maas maas-admin machine query-power-state $SYSTEM_ID`
→ MaaS AMT driver → `wsman identify --endpoint https://...@10.0.11.11:16993`.

When AMT TLS at 10.0.11.11:16993 accepts TCP but never completes the TLS handshake
(observed on ms01-02), each wsman process hangs indefinitely. Called every 10s by
`_amt_check_off` in the power-off wait loop, this accumulates wsman zombies rapidly.

This affects:
- `_amt_power_on` safety check (before every deploy power-on)
- `_amt_power_cycle` (before every commission attempt)
- `_amt_check_off` via `wait_for_condition` (power-off confirmation wait)
- `_log_power_state` (at start of every `_trigger_commission` call)

### Bug 2: No timeout on `maas machine power-off` in `_amt_power_cycle`

When `_amt_power_cycle` determines the machine is "on" (from `_query_actual_power_state`)
and calls `maas machine power-off`, the MaaS AMT driver again calls wsman → same hang.

## Fixes

### Fix 1: `timeout 90` on `_query_actual_power_state`

```bash
_query_actual_power_state() {
    local result
    # timeout 90: MaaS AMT driver calls wsman which can hang indefinitely when
    # 10.0.11.xx:16993 accepts TCP but TLS handshake never completes (S5 / ME
    # firmware boot issues). 90s is generous; normal queries return in <2s.
    result=$(ssh ${_SSH_OPTS} ubuntu@"$MAAS_HOST" \
        "timeout 90 sudo maas maas-admin machine query-power-state $SYSTEM_ID 2>/dev/null \
         | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"state\",\"unknown\"))'" \
        2>/dev/null) || result="unknown"
    echo "${result:-unknown}"
}
```

When `timeout 90` fires, the SSH command returns non-zero, `result="unknown"` is used.
`_amt_check_off` treats "unknown" as "off" (S5/deep sleep = machine is off). No zombie.

### Fix 2: `timeout 60` on `maas machine power-off` in `_amt_power_cycle`

```bash
ssh ${_SSH_OPTS} ubuntu@"$MAAS_HOST" \
    "timeout 60 sudo maas maas-admin machine power-off $SYSTEM_ID" \
    >/dev/null 2>&1 || true
```

### Fix 3: `timeout 60` on recovery path `maas machine power-off`

Same pattern applied to the stuck-commissioning recovery path.

## Impact

- No more indefinitely-hanging SSH commands from `_query_actual_power_state`
- wsman zombie accumulation on MaaS server prevented
- Commission/deploy scripts can always make forward progress even when AMT TLS hangs
- The `_amt_check_off` wait now reliably resolves (returns "unknown" = off after ≤90s)

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
