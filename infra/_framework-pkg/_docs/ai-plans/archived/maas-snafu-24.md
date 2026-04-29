# Plan: maas-snafu-24 — maas-capture-lldpd Fails Commissioning When No LLDP Neighbors

## Objective

Fix commissioning failures caused by `maas-capture-lldpd` exiting 1 when no LLDP neighbors
are present. This is normal behavior in home labs without LLDP-capable switches, but MaaS
treats any non-zero exit as a commissioning failure.

## Context

**Root cause**: The built-in MaaS script `maas-capture-lldpd` calls
`check_call(("lldpctl", "-f", "xml"))` (Python subprocess). `lldpctl` exits 1 when no LLDP
neighbors are found. `check_call` raises `CalledProcessError` on non-zero exit, causing the
commissioning script to fail.

**Why the old approach failed**: The previous fix attempt used the `commissioning_scripts`
parameter on `maas machine commission` to pass a whitelist excluding `maas-capture-lldpd` and
`30-maas-01-bmc-config`. This doesn't work: MaaS always runs ALL default built-in commissioning
scripts regardless of the `commissioning_scripts` parameter. Built-in scripts (default=True)
cannot be excluded this way.

**API limitations**: 
- `may_fail`: Not supported in this MaaS version (field exists but has no effect)
- `default_disabled`: Not supported (field recognized but has no effect)
- Script content replacement: Blocked with "Not allowed to change on default scripts."

**Evidence**: Run 164 (previous session) showed `maas-capture-lldpd` exit=0 (lucky timing,
lldpd had accumulated LLDP frames). Run 165 (this session) showed exit=1 (no neighbors found
in the 60s collection window). Inconsistent — the fix must make it always pass.

**Fix**: Create a custom commissioning script `21-fix-lldpctl` that runs between the built-in
`20-maas-01-install-lldpd` (installs lldpd) and `maas-capture-lldpd` (alphabetical ordering:
"21-" sorts before "maas-"). This script wraps `/usr/sbin/lldpctl` with a bash wrapper that
always exits 0, regardless of LLDP neighbor count.

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/configure-commissioning-scripts.yaml` — modified

Replaced the previous approach (per-commission exclusion that didn't work) with:
1. Check if `21-fix-lldpctl` already exists in MaaS
2. If not, copy the script to `/tmp/21-fix-lldpctl.py` and upload via MaaS REST API
   (OAuth1 PLAINTEXT authentication; CLI `script@=` file upload does not work via snap+SSH)

### `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh` — modified

Updated the commissioning script list logic to:
1. Only list custom (non-default) commissioning scripts — built-in scripts always run regardless
2. Pass `commissioning_scripts=<custom-scripts>` to ensure `21-fix-lldpctl` is requested
3. Updated the log message to be accurate (removed misleading "excluding" comment)

## Applied Fix

Script `21-fix-lldpctl` (id=32) was created directly on the MaaS server via REST API
during this session. The Ansible playbook update ensures future `configure-region` runs
create it idempotently on fresh MaaS installations.

## Verification

- Re-run `maas.lifecycle.commissioning` wave
- Log should show: "Custom commissioning scripts: 21-fix-lldpctl"
- During commissioning of ms01-02: script `21-fix-lldpctl` should run and print
  "Installed lldpctl wrapper at /usr/sbin/lldpctl (original at /usr/sbin/lldpctl.orig)"
- `maas-capture-lldpd` should then pass (exit=0) because the wrapper exits 0
- ms01-02 should reach Ready state

## Open Questions

None — root cause confirmed, fix applied and committed.
