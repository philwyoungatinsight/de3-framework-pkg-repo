# Plan: maas-snafu-29 — `21-fix-lldpctl` Causes Two-Phase Commissioning Split

## Root Cause

Snafu-28 changed `21-fix-lldpctl` from `parallel: any` to `parallel: none`
(`SCRIPT_PARALLEL.DISABLED = 0`). This caused MaaS to split commissioning into
**two separate PXE boot phases** with a physical machine reboot between them:

**Phase 1** (serial scripts only): `20-maas-01-install-lldpd`, `20-maas-02-dhcp`,
`20-maas-03-machine-resources`, `21-fix-lldpctl` — all PASS.

**[Machine physically reboots — 44-second HTTP log gap, new DHCP 30s lease, new kernel
download at 14:49:37]**

**Phase 2** (fresh ephemeral environment, filtered scripts tar): `30-maas-01-bmc-config`,
`40-maas-01-machine-config-hints`, `50-maas-01-commissioning`, `maas-capture-lldpd`.

In Phase 2, lldpd is NOT installed (fresh environment). `/var/run/lldpd.socket` does not
exist. `maas-capture-lldpd` calls `getmtime("/var/run/lldpd.socket")` → immediate
`FileNotFoundError`. Script fails in ~100ms.

Additionally, `40-maas-01-machine-config-hints` and `50-maas-01-commissioning` fail
because they depend on machine-resources output files written in Phase 1, which don't
exist in the fresh Phase 2 environment.

Evidence (Group 182, system_id c6gyx3):
```
Phase 1 (14:48:47-14:48:53): 20-maas-01-install-lldpd [PASS], 20-maas-02-dhcp [PASS],
  20-maas-03-machine-resources [PASS], 21-fix-lldpctl [PASS]
[44-second gap — physical reboot]
Phase 2 (14:50:20-14:50:21): 30-maas-01-bmc-config [PASS],
  40-maas-01-machine-config-hints [FAIL], 50-maas-01-commissioning [FAIL],
  maas-capture-lldpd [FAIL]
```

Contrast with Group 181 (auto-enlistment, no `21-fix-lldpctl`): ALL 12 scripts ran in
ONE phase. `20-maas-01-install-lldpd` installed lldpd in the serial phase. Then
`maas-capture-lldpd` (parallel) ran, found lldpd running, waited 60s for LLDP discovery,
and PASSED.

## Why the Two-Phase Split Happens

`maas_run_remote_scripts.py` fetches the scripts tar, runs all serial (disabled)
scripts, then instance, then parallel. After ALL three groups complete successfully,
it recursively re-downloads the scripts tar (for hardware-detected scripts). If the
re-downloaded tar differs, a NEW phase begins. When `21-fix-lldpctl` is serial and
the 20-* scripts are also serial, Phase 1 has only serial scripts. After they pass,
the machine re-downloads a filtered tar and reboots into Phase 2.

The fix is simple: **remove `21-fix-lldpctl` entirely**. Group 181 proves that
commissioning succeeds without it. `maas-capture-lldpd` has `parallel: any` in its
metadata; `20-maas-01-install-lldpd` has `parallel: none` (default DISABLED). In a
single-phase run, lldpd is installed in the serial phase before `maas-capture-lldpd`
(parallel) starts — exactly what we wanted `21-fix-lldpctl` to ensure.

## Fix

Remove all `21-fix-lldpctl` tasks from `configure-commissioning-scripts.yaml`. The
snafu-28 fix (the script itself) solved a problem that doesn't exist: the `lldpctl`
wrapper is unnecessary because MaaS commissioning already exits 0 even when
`maas-capture-lldpd` fails. Furthermore, the presence of `21-fix-lldpctl` causes
the two-phase split that breaks multiple other scripts.

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/configure-commissioning-scripts.yaml` — modified

Remove all tasks related to `21-fix-lldpctl`:
- "Get MaaS admin API key (commissioning-scripts)"
- "Login to MaaS CLI (commissioning-scripts)"
- "Check if 21-fix-lldpctl commissioning script already exists in MaaS"
- "Delete existing 21-fix-lldpctl from MaaS (force re-upload to pick up content changes)"
- "Copy 21-fix-lldpctl script to MaaS server (needed for API upload)"
- "Create 21-fix-lldpctl commissioning script in MaaS via REST API"
- "Report commissioning script configuration"

The file will be empty (or contain only the header comment) after removal.

## Open Questions

None — fix is clear.

## Verification

- configure-region task log should show no 21-fix-lldpctl steps
- `maas node-scripts read` should return only built-in scripts (no `21-fix-lldpctl`)
- Syslog should show all commissioning scripts running in ONE phase (no reboot between them)
- `maas-capture-lldpd` should pass (lldpd installed in serial phase before it runs)
- ms01-02 should reach Ready state after commissioning
