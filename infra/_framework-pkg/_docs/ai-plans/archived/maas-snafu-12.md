# Plan: maas-snafu-12 — AMT power-cycle sends wrong PowerState for S5 machines

## Objective

Fix `amt-power-cycle/run` so it issues the correct AMT power command based on the
machine's current power state. Without this fix, machines in S5 (soft-off) silently
receive a hard-reset command that AMT accepts with rc=0 but ignores, leaving the
machine off and causing the MaaS enrollment wait to time out.

---

## What Broke

### Symptom

`maas-machines-precheck` reports "power-cycle sent" for ms01-01 and ms01-03 but they
never PXE boot and never appear in MaaS. The enrollment poll times out after 300s.

### Root Cause

`amt-power-cycle/run` Step 3 tries `PowerState=10` (hard reset) first:

```python
if power(10):   # hard reset (machine ON)
    sys.exit(0)
print("Hard reset failed; trying power-on...", file=sys.stderr)
if power(2):    # power on (machine OFF)
    sys.exit(0)
```

`power()` returns True when `wsman` exits rc=0. When the machine is in S5 (soft-off),
AMT **accepts** `PowerState=10` with rc=0 but does not actually boot the machine.
The script exits 0, reporting success. The fallback `PowerState=2` (power on) is
never reached. The machine stays off.

### Confirmed via AMT query

```
ms01-01 (10.0.11.10): PowerState>8<  ← S5, still off after "power-cycle sent"
ms01-03 (10.0.11.12): PowerState>8<  ← S5, still off after "power-cycle sent"
```

### Secondary issues

1. **`invoke()` ReturnValue check appears inverted** — `"ReturnValue>0<" not in r.stdout`
   matches the success case (ReturnValue=0 IS "ReturnValue>0<" in XML). This means
   ChangeBootOrder and SetBootConfigRole always show as failed, but the script
   continues anyway. Needs investigation — may be masking boot-override failures.

2. **ms01-02: wrong AMT password in SOPS + wsman crashes on 401**
   - Confirmed via curl (from MaaS server with `OPENSSL_CONF` legacy config):
     ms01-02 AMT returns HTTP 401 (authentication failure). ms01-01 and ms01-03
     return HTTP 500 (authenticated, empty SOAP body = correct auth).
   - Each ms01 machine has its own AMT password configured in firmware independently.
     ms01-02 had been physically configured with a password that did not match its
     SOPS entry. ms01-01 and ms01-03 were unaffected.
   - wsman crashes (SIGSEGV, rc=-11) when it gets a 401 response — a bug in the
     wsman binary. The Python script catches rc=-11 → exits 1 → precheck falls
     through to the raw plug fallback.
   - Raw plug fallback was run (plug cycle confirmed), but ms01-02 did NOT enroll
     in MaaS within 300s. Likely cause: BIOS boot order has disk first and disk
     has a previous OS install — no AMT boot override means no PXE boot.
   - **RESOLVED**: User updated `ms01-02.power_pass` in SOPS to match the
     password actually configured in ms01-02's AMT firmware. All three ms01
     machines now authenticate independently; passwords are NOT assumed to be equal.

---

## Fix: Query power state before issuing power command

In `amt-power-cycle/run`, query the current AMT power state before Step 3 and choose:
- Current state = 2 (ON) → `PowerState=10` (hard reset)
- Current state = anything else (S5=8, S4=5, S3=4, unknown) → `PowerState=2` (power on)

Leave `invoke()` ReturnValue check alone for now — without seeing actual wsman XML
output the inversion might be intentional. Document for investigation after power-state
fix is confirmed working.

---

## Files to Modify

### `infra/maas-pkg/_tg_scripts/maas/amt-power-cycle/run` — modify

1. Add `query_power_state()` function that calls
   `wsman get CIM_AssociatedPowerManagementService` and parses `PowerState>(\d+)<`.

2. Fix `invoke()` ReturnValue check: change `not in` → `in`.

3. Add `query_power_state()` function and replace Step 3 hard-coded `power(10)` sequence.

4. `invoke()` ReturnValue check left unchanged — investigate separately after power-state fix is confirmed.

---

## Verification

After fix, re-run precheck. Expected:
- ms01-01, ms01-03: script queries state (8=S5), sends PowerState=2, machine boots
- Log shows "Current AMT power state: 8" then "PowerState=2 sent"
- Machines appear in MaaS within 300s

---

## Status

### Primary fix: PowerState=10 on S5 machines — RESOLVED
Applied in commit `7f7cb3e3`. `amt-power-cycle/run` now queries power state first,
uses `PowerState=2` for OFF machines. ms01-01 and ms01-03 now enroll successfully.
30s wsman timeouts added in `648bc255`.

### ms01-02: BLOCKING — wrong AMT password
As of 2026-04-15 ~06:30 UTC:
- ms01-01, ms01-03, nuc-1 enrolled in MaaS (names: better-turtle, well-hawk, fine-worm)
- ms01-02 not enrolled; smart plug ON (machine powered on but not PXE booting)
- Automation is blocked; precheck fails with "ms01-02 did not enlist in MaaS"

User must take one of the three actions listed under "User action required" above.

## Open Questions

What is the correct AMT password for ms01-02? Was it set to something different
from ms01-01/ms01-03 during initial lab setup?
