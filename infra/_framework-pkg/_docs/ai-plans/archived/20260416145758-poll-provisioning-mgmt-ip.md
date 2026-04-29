---
# Plan: Poll Provisioning IP + Management IP to Detect Genuine Commissioning

## Objective

Replace the age-based check in `trigger-commission.sh` with a direct liveness check:
poll the machine's provisioning VLAN IP (proves commissioning environment is running) and
management IP (AMT, proves machine has power) to decide whether to let commissioning
continue or abort+re-trigger with script exclusions.

The current age-based check (abort if commissioning script results < 180s old) is fragile
and was introduced as a short-term fix. The correct signal is: does the machine have a
reachable provisioning IP? If yes → genuinely commissioning. If no → not in the
commissioning environment → abort and re-trigger.

## Context

Root cause: MaaS auto-commissions on enrollment without our script exclusions. When
`trigger-commission.sh` runs and sees the machine in "Commissioning" state, it should
detect whether the machine is ACTUALLY running the commissioning environment. The
signals are:

1. **Provisioning IP** (`10.0.12.x`): assigned by MaaS DHCP when the machine PXE-boots
   into the commissioning environment. If the machine has a reachable provisioning IP →
   it's in the commissioning env. If not → it hasn't booted the commissioning env yet.

2. **Management IP** (AMT on `10.0.11.x`, port `16993`): reachable if the machine has
   AC power and AMT ME firmware is up. Used to confirm the machine is powered and to
   guide the decision (if AMT up but no provisioning IP → machine booted to disk or is
   in early POST → abort + re-trigger).

Current bad path: machine auto-commissions, trigger-commission.sh sees "Commissioning +
power on", exits 0. Machine runs 30-maas-01-bmc-config for 40+ minutes until timeout.

Key observation from snafu-18: when trigger-commission.sh ran (14:01 local), the machine
was in "Commissioning + power on" (it had just enrolled) but had `ip_addresses: []` and
the provisioning IP was unreachable via ping from MaaS server. This would have correctly
detected "not in commissioning environment" if the IP check was in place.

## Files to Create / Modify

### `infra/maas-pkg/_modules/maas_lifecycle_commission/scripts/trigger-commission.sh` — modify

In the **"already Commissioning"** block (starting at line 143), replace the age-based
check with a provisioning IP + management IP poll. The block currently:
1. Checks power state (via AMT wsman or MaaS API)
2. If power=off → abort (stuck)
3. If power=on → checks age of commissioning script results
   - If < 180s → abort + re-trigger with exclusions
   - If ≥ 180s → exit 0

**New logic** (keep the power=off abort as-is; replace the age check for power=on):

```
When power=on:
  1. Get machine's current ip_addresses from MaaS API
  2. Filter for provisioning VLAN IPs (10.0.12.0/24)
  3. If provisioning IP found:
       Ping it from MaaS server (ssh ubuntu@10.0.10.11 "ping -c2 -W3 <ip>")
       - ping succeeds → machine IS in commissioning environment → exit 0
       - ping fails → commissioning env lost network → fall through to abort+re-trigger
  4. If no provisioning IP (or ping failed):
       Poll up to 90s at 15s intervals for a provisioning IP to appear + respond
       (machine may be in early PXE/DHCP phase when trigger-commission.sh runs)
       While polling:
         - Check MaaS API for ip_addresses each interval
         - Also check if AMT management IP is reachable (log but don't gate on it)
       If provisioning IP appears and responds during poll window → exit 0
       If no provisioning IP after 90s:
         Log: "No provisioning IP after 90s — machine not in commissioning environment"
         Log AMT status (reachable or not) for diagnostics
         Abort + re-trigger with exclusions (fall through to the re-trigger block)
```

**Code snippet for the new logic block** (replaces the age-check `elif` branch):

```bash
else
    # power=on: check if machine is genuinely in the commissioning environment
    _log ""
    _log "STATE CONFIRMED: Commissioning + power on (${PSTATE})"
    _log "ACTION: Check for active provisioning VLAN IP (proves commissioning env is running)..."

    # Helper: get provisioning IP (10.0.12.x) from MaaS API
    _get_provisioning_ip() {
        ssh ${_SSH_OPTS} ubuntu@"${MAAS_HOST}" \
            "${_MAAS} maas-admin machine read ${SYSTEM_ID} 2>/dev/null \
             | python3 -c '
import sys, json
d = json.load(sys.stdin)
for ip in d.get(\"ip_addresses\", []):
    if ip.startswith(\"10.0.12.\"):
        print(ip)
        break
'" 2>/dev/null || true
    }

    # Helper: ping provisioning IP from MaaS server (provisioning VLAN not routable from dev)
    _ping_from_maas() {
        local ip="$1"
        ssh ${_SSH_OPTS} ubuntu@"${MAAS_HOST}" \
            "ping -c2 -W3 '${ip}' 2>/dev/null" 2>/dev/null
    }

    # Helper: check AMT management IP
    _check_amt_mgmt() {
        if [ -n "${AMT_ADDR_S2:-}" ]; then
            ssh ${_SSH_OPTS} ubuntu@"${MAAS_HOST}" \
                "nc -z -w3 '${AMT_ADDR_S2}' '${AMT_PORT_S2:-16993}' 2>/dev/null" 2>/dev/null && echo "up" || echo "down"
        else
            echo "unknown"
        fi
    }

    _PROV_POLL_TIMEOUT="${_PROV_POLL_TIMEOUT:-90}"
    _PROV_POLL_INTERVAL=15
    _prov_elapsed=0
    _prov_ip=""
    _found_prov=false

    while [ "${_prov_elapsed}" -le "${_PROV_POLL_TIMEOUT}" ]; do
        _prov_ip=$(_get_provisioning_ip)
        if [ -n "${_prov_ip}" ]; then
            _log "  Provisioning IP found: ${_prov_ip} (elapsed: ${_prov_elapsed}s)"
            if _ping_from_maas "${_prov_ip}"; then
                _log "  Ping to ${_prov_ip} succeeded — machine IS in commissioning environment."
                _found_prov=true
                break
            else
                _log "  Ping to ${_prov_ip} FAILED — IP assigned but unreachable."
                # Could be transient; keep polling briefly
            fi
        else
            _log "  No provisioning IP yet (elapsed: ${_prov_elapsed}s / ${_PROV_POLL_TIMEOUT}s) ..."
        fi
        if [ "${_prov_elapsed}" -ge "${_PROV_POLL_TIMEOUT}" ]; then break; fi
        sleep "${_PROV_POLL_INTERVAL}"
        _prov_elapsed=$((_prov_elapsed + _PROV_POLL_INTERVAL))
    done

    if [ "${_found_prov}" = "true" ]; then
        _log ""
        _log "STATE CONFIRMED: Commissioning + active provisioning IP (${_prov_ip})"
        _log "ACTION: Machine is genuinely in the commissioning environment. Exit 0."
        exit 0
    fi

    # No provisioning IP after poll window — machine is not in commissioning env
    _amt_status=$(_check_amt_mgmt)
    _log ""
    _log "STATE CONFIRMED: Commissioning + power on BUT no reachable provisioning IP"
    _log "  AMT management: ${_amt_status}"
    _log "  Machine is NOT in the commissioning environment (booted to disk or early POST)."
    _log "ACTION: Abort auto-commissioning and re-trigger with script exclusions."
    _log "  (30-maas-01-bmc-config hangs the commissioning env for 40+ min on this hardware.)"
    _ssh_run "maas machine abort ${SYSTEM_ID}" \
        "${_MAAS} maas-admin machine abort ${SYSTEM_ID} 2>&1 || true"
    _log "Abort sent. Waiting 5s for MaaS to process..."
    sleep 5
    STATUS=$(_status)
    _log "Status after abort: ${STATUS}"
    _log ""
    # Fall through to re-trigger below
fi
```

**Note on `AMT_ADDR_S2` and `AMT_PORT_S2`**: these are already set earlier in the
Commissioning block (lines 154-164 in the current code), so `_check_amt_mgmt` can use
them. The provisioning IP helper and ping helper are new.

**Remove the age-based check**: delete the `_COMM_AGE` / `_FRESH_COMMISSION_THRESHOLD`
logic introduced in the previous commit (efa71594). It is replaced by this IP check.

## Execution Order

1. Read current trigger-commission.sh (already known)
2. Locate the "elif [ \"${_COMM_AGE}\" ..." block (the age check)
3. Replace the entire age-check `elif` branch with the new provisioning IP polling block
4. Keep everything else unchanged (power=off abort, fall-through to re-trigger, etc.)

## Verification

After the next build run:
- Check commissioning apply log: should show "No provisioning IP" + "Abort" + "re-trigger"
  when machine auto-commissions on enrollment
- OR show "Ping succeeded" + "exit 0" if machine actually has a provisioning IP
- After re-trigger: machine should commission successfully (no 30-maas-01-bmc-config)

## Open Questions

None — ready to proceed.
