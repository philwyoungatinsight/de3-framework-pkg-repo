# Fix: Commission Script Deployed-State Terminal and Interface Unlink-Before-Link

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed two bugs in `commission-and-wait.sh` that caused wave 10 failures:

1. **`_check_commissioning_done` didn't recognize "Deployed"** — when a machine completed
   commissioning and transitioned directly to a deploy phase (Deployed/Allocated/Deploying),
   the polling loop kept running for the full 2400s timeout instead of exiting immediately.
2. **`_configure_interfaces` failed silently on STATIC link** — when an interface already
   had a subnet link (e.g. mode=DHCP from a previous commissioning run), MaaS rejected
   `link-subnet mode=STATIC`, the script emitted a WARNING and continued, leaving the
   interface without a usable network config. Deploy then failed with:
   `400 Bad Request: Node has no address family in common with the server`.

## Root Causes

### Bug 1: Non-terminal "Deployed" status caused 40-minute wait

`_check_commissioning_done` only recognized `Ready|Failed*|Broken|New` as terminal.
"Deployed", "Allocated", and "Deploying" returned 1 (keep polling). When a machine
was already deployed from a prior wave attempt, the commission script polled the full
2400s timeout, then fell into the `Commissioning|Testing|unknown` timeout handler which
attempted `_stale_os_wipe` — completely wrong for a successfully deployed machine.

### Bug 2: Interface re-link failure silently skipped

The Python script computed the target subnet from the interface's existing link.
The bash loop then called `interface link-subnet mode=STATIC`, which MaaS rejects
if the interface already has ANY link (the existing DHCP link from commission).
The error was swallowed with `>/dev/null 2>&1 || echo "WARNING"` — deploy proceeded
without a network address and failed.

## Fixes

### Fix 1: Add deploy-phase states to terminal set

```bash
_check_commissioning_done() {
    _ms_status=$(_maas_status)
    echo "  [$(date '+%H:%M:%S')] $SYSTEM_ID: $_ms_status"
    case "$_ms_status" in
        Ready|Deployed|Allocated|Deploying|Failed*|Broken|New) return 0 ;;
        *) return 1 ;;
    esac
}
```

Added matching case in post-wait_for_condition STATUS handler:
```bash
Deployed|Allocated|Deploying)
    echo "$SYSTEM_ID commissioning complete (status: $STATUS) — already in deploy phase, skipping interface config."
    exit 0
    ;;
```

### Fix 2: Unlink existing links before re-linking

Modified Python output to include existing link IDs (colon-separated, `-` if none):
```python
existing_link_ids = ':'.join(str(l['id']) for l in links) if links else '-'
print(iface['id'], sub_id, iface['name'], existing_link_ids)
```

Bash loop now unlinks existing links before setting STATIC/AUTO:
```bash
if [ -n "${existing_link_ids:-}" ] && [ "$existing_link_ids" != "-" ]; then
    IFS=':'
    for _lid in $existing_link_ids; do
        [ -n "$_lid" ] || continue
        ssh ... "sudo maas maas-admin interface unlink-subnet $SYSTEM_ID $iface_id id=$_lid" ...
    done
fi
```

Also changed the STATIC link failure from a WARNING (silent skip) to an ERROR that
causes the commission script to exit 1, so deploy is blocked with a clear error
rather than failing obscurely in MaaS.

## Impact

- Commission polling exits immediately when machine reaches deploy phase (saves 35-40 min)
- Interface STATIC link always succeeds on retry (unlink first, then link)
- STATIC link failure is now fatal (deploy won't proceed with broken network config)

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
