# Plan: maas-snafu-31 — maas-capture-lldpd Fails Because lldpd Not Installed in Phase 3

## Root Cause

MaaS full commissioning (triggered by `maas machine commission`) is multi-phase:
- Phase 1: 20-* scripts (DISABLED/serial) — installs lldpd among other things
- Phase 2: 30-*, 40-*, 50-* scripts (DISABLED/serial)
- Phase 3: maas-capture-lldpd (ANY/parallel) — in a FRESH ephemeral environment

Each phase starts with a physical PXE reboot (confirmed by MaaS events showing multiple
PXE boots ~44s and ~66s apart). Phase 3 boots into a fresh ephemeral environment
where lldpd is NOT installed. `maas-capture-lldpd` calls
`getmtime("/var/run/lldpd.socket")` — socket doesn't exist → FileNotFoundError →
"Script maas-capture-lldpd failed" → "Failed commissioning".

Evidence (system_id pn748a):
```
17:02:16 Performing PXE boot   ← trigger-commission.sh
17:03:57 Commissioning
17:04:41 Performing PXE boot   ← Phase 1 complete (44s), Phase 2 starts
17:05:11 Gathering information
17:06:17 Performing PXE boot   ← Phase 2 complete (66s), Phase 3 starts
17:06:40 Gathering information
17:07:10 Script maas-capture-lldpd failed
17:07:10 Failed commissioning
```

Note: auto-enlistment (Group 181) ran in ONE phase because enlistment is a different
code path. Explicit full commissioning (`maas machine commission`) always uses the
multi-phase architecture.

Note: snafu-28 added `21-fix-lldpctl` to wrap lldpctl — unnecessary, lldpctl exits 0
when lldpd is running even with no LLDP neighbors. The real problem was always that
lldpd itself is not installed in Phase 3.

## Fix

Create custom commissioning script `maas-00-install-lldpd`:
- Name: `maas-00-install-lldpd` — alphabetically before `maas-capture-lldpd`, ensuring
  it's in Phase 3's tar (MaaS groups `maas-*` scripts in the same phase tar)
- `parallel: none` (DISABLED) — runs in Phase 3's serial phase, BEFORE
  `maas-capture-lldpd` (parallel: any)
- Installs lldpd and starts the service
- Waits for socket to appear

After `maas-00-install-lldpd` runs:
- `/var/run/lldpd.socket` exists
- `maas-capture-lldpd` finds the socket, waits up to 60s for LLDP discovery
- `lldpctl` runs, finds no LLDP neighbors (home lab), exits 0
- `check_call` succeeds, commissioning passes

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/configure-commissioning-scripts.yaml` — modified

- Keep the `21-fix-lldpctl` delete step (cleanup from snafu-30)
- Add: copy `maas-00-install-lldpd.py` to `/tmp` on MaaS server
- Add: upload script to MaaS via REST API (same pattern as original snafu-28 code)
- Update report task

## Open Questions

None — ready to implement.

## Verification

- configure-region log should show "Created maas-00-install-lldpd script"
- MaaS commissioning events should show Phase 3 taking longer (~70s for lldpd install + lldpd wait)
- Script maas-00-install-lldpd should show in node-script-results as PASS
- maas-capture-lldpd should show as PASS
- ms01-02 should reach Ready state
