# Fix: configure_interfaces Exit Propagation, STATIC Fallback, power_state='off' Post-Commission

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed three bugs in `commission-and-wait.sh` that caused eawest (ms01-01) to fail deployment
even after commissioning succeeded:

1. **`_configure_interfaces` `exit 1` swallowed in pipeline subshell** — function returned 0
   even when STATIC link-subnet failed; `null_resource.commission` was marked created despite
   a broken interface config, causing the subsequent `maas_instance.this` deploy to fail.

2. **Stale link IDs from Python snapshot caused unlink to fail** — pre-computed `existing_link_ids`
   from the initial interface read were stale by the time the bash loop ran (commissioning
   re-configures interfaces between the two); unlink of old IDs silently failed, leaving the
   old DHCP link in place, making the subsequent STATIC link-subnet reject with 400.

3. **STATIC link-subnet fails with "IP already in use"** — when commissioning assigns an IP via
   DHCP, MaaS records it as a DHCP-discovered address. Attempting `mode=STATIC` with that same
   IP returns "IP address is already in use". Must fall back to `mode=AUTO` (which uses DHCP
   and assigns the same IP by MAC).

4. **"Error determining BMC task queue" on deploy** — after commissioning, MaaS DB has
   `power_state='unknown'`. When `maas_instance.this` tries to deploy via AMT, MaaS refuses to
   queue the power-on task without a known power state. Fixed by setting `power_state='off'` in
   the DB immediately after restoring power_type=amt (the machine IS off after commissioning).

## Root Causes

### Bug 1: Pipeline subshell swallows `exit 1`

```bash
# BEFORE: while runs in pipeline subshell; exit 1 exits subshell, not function
echo "$link_cmds" | grep -v '^#' | while IFS=' ' read -r ...; do
    ...
    || { echo "ERROR"; exit 1; }  # ← exits subshell only!
done
# function always returned 0
```

The `exit 1` inside a pipeline subshell (`cmd | while ...`) exits only the subshell. The bash
`while` loop terminates with its own exit code, but the function's return code comes from the
overall pipeline, which ignored the subshell exit.

### Bug 2: Stale link IDs

Python computed `existing_link_ids = ':'.join(str(l['id']) for l in links)` from the initial
`interfaces read` call. But between that read and the bash unlink loop, commissioning or a
previous `_configure_interfaces` run may have changed the link IDs. Unlinking a stale ID returns
an error, leaving the interface with its existing DHCP link intact.

### Bug 3: "IP already in use"

MaaS tracks DHCP-discovered IPs separately from static allocations. When `mode=STATIC` is
attempted with an IP that MaaS knows is a current DHCP lease, it rejects with rc=2 "IP address
is already in use" — even if the requesting machine IS the DHCP leaseholder.

### Bug 4: `power_state='unknown'` blocks deploy queue

After commissioning completes, the MaaS AMT driver cannot confirm the actual power state (AMT
TLS hang returns timeout → `power_state='unknown'`). MaaS's deploy endpoint checks cached
`power_state` before queuing power-on tasks; 'unknown' is treated as "cannot queue" → HTTP 500
"Error determining BMC task queue".

## Fixes

### Fix 1: Process substitution instead of pipeline

```bash
# AFTER: while runs in current shell; exit 1 propagates correctly
while IFS=' ' read -r iface_id subnet_id iface_name; do
    ...
    || { echo "ERROR"; exit 1; }  # ← exits the script
done < <(echo "$link_cmds" | grep -v '^#')
```

Also removed the 4th Python column (`existing_link_ids`) since links are now fetched fresh per-
interface inside the loop.

### Fix 2: Fresh link fetch per-interface inside the loop

```bash
_current_link_ids=$(ssh ${_SSH_OPTS} ubuntu@"$MAAS_HOST" \
    "sudo maas maas-admin interface read $SYSTEM_ID $iface_id 2>/dev/null" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(" ".join(str(l["id"]) for l in d.get("links",[])))')
for _lid in $_current_link_ids; do
    # unlink ...
done
```

One extra SSH call per interface, but guarantees we unlink current IDs (not stale ones).

### Fix 3: STATIC → AUTO fallback

```bash
_static_out=$(ssh ... "sudo maas ... link-subnet ... mode=STATIC ip_address=... 2>&1")
_static_rc=$?
if [ "$_static_rc" = "0" ]; then
    echo "STATIC ok"
else
    echo "WARNING: STATIC rejected (${_static_out}); falling back to AUTO"
    ssh ... "sudo maas ... link-subnet ... mode=AUTO ..." \
        || { echo "ERROR: AUTO also failed"; exit 1; }
fi
```

The machine's DHCP server (MaaS) will assign the same IP by MAC, so AUTO is functionally
equivalent to STATIC for machines with a fixed provisioning IP.

### Fix 4: Set `power_state='off'` after AMT restore in Ready case

```bash
Ready)
    _amt_restore_power_type
    if [ "$POWER_TYPE" = "amt" ]; then
        ssh ... "sudo -u postgres psql maasdb -c \
            \"UPDATE maasserver_node SET power_state = 'off' WHERE system_id = '$SYSTEM_ID'\""
    fi
    _configure_interfaces || exit 1
    exit 0
```

The machine IS powered off after commissioning (commissioning OS shuts down). Setting 'off'
in the DB allows MaaS to queue AMT power-on for deploy without a live AMT query.

## Impact

- `_configure_interfaces` failures now correctly propagate as `exit 1` from commission-and-wait.sh
- Stale link ID unlink failures no longer silently leave broken interface configs
- STATIC IP "already in use" is gracefully handled with AUTO fallback
- AMT machines with TLS hang can proceed to deploy after commissioning (BMC task queue error resolved)
- eawest (ms01-01) will deploy successfully on next `make` run

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
