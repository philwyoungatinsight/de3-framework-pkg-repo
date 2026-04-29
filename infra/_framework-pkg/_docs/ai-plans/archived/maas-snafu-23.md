# Plan: maas-snafu-23 — AMT Hard Reset Ignores PXE Boot Override on MinisForum MS-01

## Objective

Fix `amt-power-cycle/run` so that when the machine is in S0 (running), it does a soft
power-off first (PowerState=8 → S5 standby), then powers on (PowerState=2), instead of
issuing a hard reset (PowerState=10). On MinisForum MS-01 hardware, AMT hard reset from
S0 does NOT honour the PXE boot override — the machine reboots to disk. Only a cold
power-on from S5 honours the override.

## Context

**Root cause**: The MS-01's UEFI firmware ignores the AMT PXE boot override on hard reset
(PowerState=10). It only honours the override on a cold power-on from S5 (PowerState=2).
This was diagnosed over multiple sessions where the machine consistently rebooted to
Rocky 9 instead of PXE booting after AMT hard reset.

**Evidence**: Manually bouncing the smart plug (to cut AC and force the machine fully off),
then sending AMT PowerState=2 from S5, caused the machine to PXE boot correctly. Hard
reset (PowerState=10) from S0 consistently failed to PXE boot.

**Affected script**: `infra/maas-pkg/_tg_scripts/maas/amt-power-cycle/run` — used during
enrollment (maas.lifecycle.new precheck) to PXE boot a machine that is currently running
an OS.

**Not affected**: MaaS's own AMT driver (used for commissioning/deploying) — when MaaS
sends commission/deploy, the machine is already off (S5), so AMT sends PowerState=2
which works correctly.

## Open Questions

None — root cause confirmed, fix is clear.

## Files to Modify

### `infra/maas-pkg/_tg_scripts/maas/amt-power-cycle/run` — modify

**Change lines 186-199** (the S0 power cycle block):

Old:
```python
if current_state == 2:
    # Machine is ON — hard reset sends PXE boot override into effect immediately.
    if power(10):
        sys.exit(0)
    # Hard reset failed; try power cycle as fallback.
    if power(5):
        sys.exit(0)
else:
    # Machine is OFF (S5/S4/S3/unknown) — power on.
    if power(2):
        sys.exit(0)
    # Power-on failed; try hard reset as fallback.
    if power(10):
        sys.exit(0)
```

New:
```python
if current_state == 2:
    # Machine is ON (S0). MinisForum MS-01 UEFI ignores the PXE boot override on
    # hard reset (PowerState=10) — machine reboots to disk. Only a cold power-on
    # from S5 (PowerState=2) honours the override. Sequence: soft-off → wait for
    # S5 → power-on.
    import time
    if not power(8):  # soft power-off (request S5)
        # Soft-off failed — last resort: hard reset (PXE override likely ignored on MS-01)
        print("WARNING: soft-off failed; hard reset fallback (PXE override may be ignored on MS-01)", file=sys.stderr)
        power(10)
        sys.exit(0)
    # Poll AMT until machine exits S0 (max 60s), then power-on.
    for _ in range(12):
        time.sleep(5)
        s = query_power_state()
        print(f"Post-soft-off AMT state: {s}")
        if s != 2:  # no longer S0
            break
    if power(2):  # cold power-on from S5
        sys.exit(0)
    # Power-on from S5 failed — try hard reset as last resort
    if power(10):
        sys.exit(0)
else:
    # Machine is OFF (S5/S4/S3/unknown) — power on.
    if power(2):
        sys.exit(0)
    # Power-on failed; try hard reset as fallback.
    if power(10):
        sys.exit(0)
```

**Also add `import time` at the top of the file** (with the other imports).

## Execution Order

1. Add `import time` to the imports section
2. Replace the S0 power cycle block (lines 186-199)

## Verification

- Next time `maas.lifecycle.new` runs for ms01-02 (after annihilation), the enrollment
  log should show "soft-off" + "Post-soft-off AMT state: ..." + cold power-on from S5
- Machine should PXE boot and enlist as New in MaaS without manual intervention
