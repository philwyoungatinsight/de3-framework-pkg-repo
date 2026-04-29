# Plan: maas-snafu-30 — snafu-29 Fix Forgot to Delete 21-fix-lldpctl from MaaS

## Root Cause

The snafu-29 fix updated `configure-commissioning-scripts.yaml` to remove the upload
of `21-fix-lldpctl` — but did not add a step to DELETE the existing `21-fix-lldpctl`
script that had already been uploaded to MaaS by a prior build run.

As a result, `21-fix-lldpctl` (with `parallel=0 / DISABLED`) was still present in MaaS
when the next commissioning run started. This caused the same two-phase commissioning
split as documented in snafu-29:

- Phase 1 (serial scripts only): `20-*`, `21-fix-lldpctl` → completed, machine rebooted
- Phase 2 (fresh environment): `30-*`, `40-*`, `50-*`, `maas-*` → ran without lldpd

Evidence from MaaS event log (system_id da4wfc):
```
15:33:03 Performing PXE boot    ← trigger-commission.sh AMT boot
15:33:42 Commissioning          ← entered commissioning
15:34:23 Performing PXE boot    ← Phase 1 complete, machine rebooting for Phase 2
15:35:22 Performing PXE boot    ← Phase 2 starting
16:19:05 Aborted commissioning  ← maas.lifecycle.ready timed out (45 min)
```

Direct verification: `maas node-scripts read type=commissioning` showed
`CUSTOM: 21-fix-lldpctl parallel=0` was still present after the snafu-29 fix ran.

## Fix

Two changes:

1. **Deleted `21-fix-lldpctl` from MaaS immediately** (one-time manual step via SSH)

2. **Added delete step to `configure-commissioning-scripts.yaml`** so future runs
   clean up any leftover script:
   ```yaml
   - name: Delete 21-fix-lldpctl from MaaS if present (snafu-30 cleanup)
     ansible.builtin.shell: |
       export PATH="/snap/bin:$PATH"
       maas maas-admin node-script delete 21-fix-lldpctl 2>/dev/null || true
     become: true
     changed_when: false
   ```

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/configure-commissioning-scripts.yaml` — modified

Added delete step before the debug report task. The login tasks are not needed because
`maas maas-admin` uses the already-logged-in session on the server (done by
configure-region playbook earlier in the same play).

## Open Questions

None.

## Verification

- `maas node-scripts read type=commissioning` should show `Custom scripts: 0`
- Commissioning should run in ONE phase (no extra PXE boot between serial and parallel phases)
- ms01-02 should reach Ready after commissioning
