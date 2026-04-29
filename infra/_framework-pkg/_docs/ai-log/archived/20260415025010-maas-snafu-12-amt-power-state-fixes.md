# maas-snafu-12: AMT Power State Fixes

## Summary

Fixed three bugs in `amt-power-cycle/run` that caused ms01-01 and ms01-03 to stay
powered off after "power-cycle sent": AMT silently accepts PowerState=10 (hard reset)
on S5 machines but does nothing; a 30s timeout was added to prevent wsman from hanging;
and the invoke() ReturnValue check was inverted, causing spurious "ChangeBootOrder failed"
warnings even when the command succeeded. ms01-01 and ms01-03 now enroll in MaaS
correctly. ms01-02 is blocked by a wrong AMT password configured in firmware (user action
required).

## Changes

- **`infra/maas-pkg/_tg_scripts/maas/amt-power-cycle/run`** — Three fixes:
  1. Added `query_power_state()` which calls `wsman get CIM_AssociatedPowerManagementService`
     and parses `PowerState>(\d+)<`. Before issuing a power command, the script now
     queries current state: PowerState=2 (S0/ON) → send hard reset (10); anything else
     (S5=8, S4=5, S3=4, unknown) → send power on (2). Previously, hard reset was always
     tried first, which AMT silently accepts on S5 machines with rc=0 but does nothing.
  2. Added `_WSMAN_TIMEOUT = 30` and `timeout=_WSMAN_TIMEOUT` to all `subprocess.run()`
     calls. Without this, wsman could hang indefinitely (reproduced: hung for 10+ minutes
     on ms01-02 when its AMT returned 401).
  3. Fixed inverted `invoke()` success check: `"ReturnValue>0<" not in r.stdout` →
     `"ReturnValue>0<" in r.stdout`. AMT returns `<ReturnValue>0</ReturnValue>` on
     success; the old check treated success as failure, printing spurious "WARNING:
     ChangeBootOrder failed" for every invocation (even when wsman rc=0 and the PXE
     boot override was correctly set).

- **`docs/ai-plans/maas-snafu-12.md`** — Updated with confirmed diagnosis for ms01-02:
  ms01-02 returns HTTP 401 while ms01-01 and ms01-03 return HTTP 500 (authenticated) —
  each machine has its own independently configured AMT password; ms01-02's SOPS entry
  did not match what was set in firmware. ms01-02 is currently powered ON but not
  PXE-booting (booting from disk without AMT boot override). User action documented.

## Root Cause

1. **PowerState=10 on S5 machines**: AMT spec allows PowerState=10 (hard reset) to be
   sent to any machine regardless of state; AMT accepts it with rc=0 but only resets
   machines that are already running. Machines in S5 silently ignore it and stay off.
   Fix: always query state first.

2. **wsman hang (no timeout)**: `subprocess.run()` without `timeout=` blocks forever
   if wsman hangs (seen when AMT returns 401 — wsman waits for response that never
   comes cleanly due to a wsman binary SIGSEGV bug on 401 responses).

3. **invoke() inverted check**: The string `ReturnValue>0<` IS present in a successful
   AMT response (`<ReturnValue>0</ReturnValue>`). Using `not in` meant success was
   treated as failure. Fix: use `in`.

## Notes

- ms01-02 AMT password mismatch: each ms01 machine has an independently configured AMT
  password. ms01-02's SOPS entry did not match what was set in its firmware.
  Do NOT assume AMT passwords are shared across machines — each must be verified and
  stored independently in SOPS. See `docs/ai-plans/maas-snafu-12.md` for full detail.
- wsman crashes with SIGSEGV (rc=-11) on HTTP 401 responses — this is a bug in the
  wsman binary. The Python script handles it: rc=-11 → exits 1 → precheck plug fallback.
- After testing invoke() fix, ms01-01 and ms01-03 were inadvertently power-cycled.
  They re-enlisted in MaaS harmlessly (already in New state; MaaS recognized by MAC).
