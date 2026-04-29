# Plan: maas-snafu-28 — 21-fix-lldpctl Parallel Race with maas-capture-lldpd

## Root Cause

The `21-fix-lldpctl` commissioning script was uploaded to MaaS with `parallel: any`
metadata. This caused it to start concurrently with `maas-capture-lldpd` (only 3ms
apart per syslog). In some commissioning runs, `maas-capture-lldpd` called lldpctl
before the wrapper was installed (the wrapper takes ~60ms to write), causing a 440ms
fast failure:

```
14:29:51.976 Starting 21-fix-lldpctl      ← installs wrapper in 60ms
14:29:51.979 Starting maas-capture-lldpd  ← starts 3ms later
14:29:52.037 Finished 21-fix-lldpctl (0)  ← wrapper installed
14:29:52.416 Finished maas-capture-lldpd (1) ← failed in 440ms (called lldpctl before wrapper)
```

Previous runs (12:32, 13:22, 14:06) passed because `maas-capture-lldpd` waited ~50 seconds
for LLDP neighbor discovery. The wrapper was in place well before lldpctl was called.
The 14:29 run failed because `maas-capture-lldpd` called lldpctl in the first 440ms
(possibly due to lldpd in a different state after 7 intermediate scripts ran between
the lldpd install and the capture scripts starting).

Secondary issue: configure-commissioning-scripts.yaml only created the script if absent
(no force-update), so the `parallel: any` version persisted across build runs.

## Fix

Two changes to `configure-commissioning-scripts.yaml`:

1. **Change `parallel: any` → `parallel: none`** in the script metadata. With `parallel: none`,
   MaaS runs the script alone (all other scripts wait). Since `21-` < `maas-` alphabetically,
   `21-fix-lldpctl` runs first and completes before `maas-capture-lldpd` starts.

2. **Force re-upload every run**: Added a delete step (`when: _lldpctl_fix_check.rc == 0`)
   before recreation, removed `when: _lldpctl_fix_check.rc != 0` from copy/create steps.
   Ensures MaaS always has the current version of the script.

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/configure-commissioning-scripts.yaml` — modified

- Added delete step before copy/create
- Changed `parallel: any` → `parallel: none` in script metadata
- Removed `when: _lldpctl_fix_check.rc != 0` conditions on copy/create tasks

## Open Questions

None — fix applied.

## Verification

- configure-region task log should show "re-uploaded (force-update)" for 21-fix-lldpctl
- Syslog should show `21-fix-lldpctl` completing (exit 0) before `maas-capture-lldpd` starts
- ms01-02 should reach Ready state after commissioning
