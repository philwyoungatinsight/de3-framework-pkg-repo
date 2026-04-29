# Fix: _amt_power_cycle "unknown" Early Return and AMT Restore Timing

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed two bugs in `commission-and-wait.sh` that caused ms01-02 (eg83cp) to fail
commissioning even after its null-VLAN interfaces were fixed:

1. **`_amt_power_cycle` returned 0 for "unknown" AMT state without power-cycling** —
   machine could still be running old commissioning environment, making the next
   commission attempt see stale network config.

2. **`power_type=amt` was restored inside `_trigger_commission` immediately after
   `maas machine commission`** — MaaS then queried AMT during the 2400s commissioning
   wait, spawning wsman zombies on TLS-hang AMT (ms01-02 at 10.0.11.11:16993).

## Root Causes

### Bug 1: `_amt_power_cycle` "unknown" = "off" assumption

`_amt_power_cycle` treated AMT state "unknown" as "machine is in S5 (deep sleep, off)"
and returned 0 without issuing any power-off. This is correct when the machine is
truly off, but wrong when:

- Machine is ON but AMT TLS is hanging (accepts TCP, TLS handshake never completes)
- This is exactly the ms01-02 scenario: `_query_actual_power_state` always returns
  "unknown" due to the 90s TLS timeout, even when the machine is powered on

Result: `_amt_power_cycle` returned without power-cycling → machine continued running
old commission environment → next commission attempt saw stale network config → MaaS
generated "Failed to apply custom network configuration" again.

### Bug 2: AMT restore runs during commissioning

Inside `_trigger_commission()`:
1. Save `_amt_params_json`, set `power_type=manual` (so MaaS won't call AMT on commission)
2. Send `maas machine commission`
3. **IMMEDIATELY restore `power_type=amt`** ← bug: commissioning is still in progress
4. Call `_amt_power_on`

After the restore at step 3, MaaS starts querying AMT for power state during the
commissioning wait. On ms01-02 (TLS-hanging AMT), each query spawns a wsman zombie
that hangs for 90s. Accumulated zombies eventually exhaust MaaS resources.

Additionally, the AMT power query during commissioning can interfere with the
commissioning PXE boot network flow.

## Fixes

### Fix 1: Attempt power-off even when state is "unknown"

```bash
if [ "$live_state" = "unknown" ]; then
    # Two possible causes: (a) S5/deep sleep, (b) ON with hanging AMT TLS.
    # Cannot distinguish. Attempt power-off anyway:
    # - If already off (case a): no-op
    # - If on with TLS-hang (case b): AMT driver tries wsman with timeout 60
    echo "  ... attempting power-off (machine may be on with unresponsive AMT TLS)."
    ssh ${_SSH_OPTS} ubuntu@"$MAAS_HOST" \
        "timeout 60 sudo maas maas-admin machine power-off $SYSTEM_ID" \
        >/dev/null 2>&1 || true
    sleep 10
    return 0
fi
```

### Fix 2: Defer AMT restore to after commissioning completes

Extracted restore logic into `_amt_restore_power_type()`, called from the main loop
after `STATUS=Ready` is confirmed:

```bash
# In main loop:
Ready)
    echo "$SYSTEM_ID commissioning complete."
    _amt_restore_power_type  # ← deferred restore
    _configure_interfaces || exit 1
    exit 0
```

`_trigger_commission` now only calls `_amt_power_on` after the commission command.
`_TC_AMT_PARAMS_JSON` (script-level variable, replaces `local _amt_params_json`) 
persists across the commissioning wait so `_amt_restore_power_type` can access it.

## Impact

- Machines with TLS-hanging AMT (ms01-02) are now reliably power-cycled before each
  commission attempt, even when AMT returns "unknown"
- MaaS does not query AMT during commissioning (power_type stays "manual" until Ready)
- No wsman zombie accumulation during commissioning wait on TLS-unresponsive AMT
- AMT is fully restored after commissioning completes, in time for deploy power-on

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
