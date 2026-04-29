# Plan: maas-snafu-13 — power_type restore failure + gate false-positive

## Objective

Fix two automation bugs that caused every machine to get stuck with `power_type=manual`
after commissioning was triggered, and caused the lifecycle gate to false-alarm on the
correct `smart_plug → webhook` power_type mapping.

---

## What Broke

### Bug 1: MAAS-2 gate false-positive (smart_plug → webhook mapping)

**Symptom**: `maas.lifecycle.new` POST gate fails:
```
nuc-1: MAAS-2 FAIL — power_type MaaS=webhook config=smart_plug (annihilate and re-enroll)
```

**Root Cause**: The gate compared MaaS `power_type` directly against config `power_type`.
But `smart_plug` in config maps to `webhook` in MaaS (defined in `terragrunt.hcl` line 178:
`power_type = local._power_type == "smart_plug" ? "webhook" : local._power_type`).

This comparison fired on every run for nuc-1, causing it to be annihilated and re-enrolled
in an infinite loop.

The same bug existed in the PRE gate's annihilation check (would annihilate nuc-1 on every
pre-gate run even though its power_type was correct).

### Bug 2: `power_type=manual` not restored after commission trigger

**Symptom**: `maas.lifecycle.commission` POST gate fails:
```
ms01-01: MAAS-2 FAIL — power_type MaaS=manual config=amt expected_maas=amt
ms01-02: MAAS-2 FAIL — power_type MaaS=manual config=amt expected_maas=amt
ms01-03: MAAS-2 FAIL — power_type MaaS=manual config=amt expected_maas=amt
nuc-1:   MAAS-2 FAIL — power_type MaaS=manual config=smart_plug expected_maas=webhook
```

**Root Cause**: `trigger-commission.sh` Step 4 sets `power_type=manual` temporarily, then
Step 6 tries to restore it. But the restore command `maas machine update $SYSTEM_ID power_type=amt`
fails with `{"power_parameters": ["This field is required."]}` because MaaS requires
`power_parameters` to accompany `power_type=amt`.

Step 6 used `_ssh_run` (fire-and-forget, never fails) instead of `_ssh_run_strict`, so
the error was silently swallowed. The machine stayed with `power_type=manual`.

`webhook` type (nuc-1) did NOT fail because MaaS doesn't require additional parameters
for `webhook` — the parameters were preserved from before manual was set.

---

## Fixes Applied

### Fix 1: `maas-lifecycle-gate/playbook.yaml` — smart_plug → webhook mapping

**File**: `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml`

Both the PRE annihilation check and the MAAS-2 POST check were updated to compute
`_expected_maas_pt` (= `'webhook'` if config `power_type == 'smart_plug'`, else unchanged)
and compare MaaS power_type against that expected value instead of the raw config value.

PRE check (line ~468):
```jinja2
{%- set _expected_maas_pt = 'webhook' if m.power_type == 'smart_plug' else m.power_type -%}
{%- if maas_power_type != _expected_maas_pt -%}
```

MAAS-2 POST check (line ~675):
```jinja2
{%- set _expected_maas_pt2 = 'webhook' if m.power_type == 'smart_plug' else m.power_type -%}
{%- if ms.get('power_type', '') != _expected_maas_pt2 -%}
```

### Fix 2: `trigger-commission.sh` — pass power_parameters on restore

**File**: `infra/maas-pkg/_modules/maas_lifecycle_commission/scripts/trigger-commission.sh`

Step 6 was rewritten to pass `power_parameters` from `MAAS_POWER_PARAMS_B64` when
restoring power_type. Uses Python on the remote side to avoid shell quoting issues
with JSON. Also changed from `_ssh_run` (silent) to explicit `_RESTORE_RC` error check.

```bash
# Runs Python on MaaS server to call maas machine update with power_parameters
ssh ... ubuntu@MAAS_HOST "python3 -c \"
import subprocess, base64, json, sys
b64 = '${MAAS_POWER_PARAMS_B64:-}'
params = json.loads(base64.b64decode(b64).decode()) if b64 else {}
cmd = ['/usr/bin/snap', 'run', 'maas', 'maas-admin', 'machine', 'update',
       'SYSTEM_ID', 'power_type=POWER_TYPE']
if params:
    cmd.append('power_parameters=' + json.dumps(params))
r = subprocess.run(['sudo'] + cmd, ...)
sys.exit(r.returncode)
\""
```

---

## Recovery Action (manual, one-time)

While machines were commissioning with `power_type=manual`, power_type was manually
restored for all 5 machines using a local Python script that SSH'd to MaaS and called
the API with proper power_parameters. After this:
- ms01-01/02/03: `power_type=amt` restored
- nuc-1: `power_type=webhook` restored
- pxe-test-vm-1: `power_type=proxmox` restored

---

## Status

- Bug 1 (MAAS-2 false positive): **FIXED** — playbook updated
- Bug 2 (power_type restore failure): **FIXED** — trigger-commission.sh updated
- Manual power_type recovery: **DONE** — all machines have correct power_type
- Commissioning: **IN PROGRESS** — machines commissioning; will re-run wave when Ready

---

## Verification

After commissioning completes:
1. Re-run `./run --build --wave 'pxe.maas.*' --wave 'maas.*'`
2. `maas.lifecycle.commission` POST gate should pass (power_type restored correctly)
3. On a subsequent full clean+build, trigger-commission.sh should restore power_type correctly
   without manual intervention

### Fix 3: Gate state table — allow "Failed commissioning" at new:post and commissioning:pre

**File**: `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml`

`new:post` and `commissioning:pre` both rejected machines in "Failed commissioning" state:
- MAAS-4: `'Failed commissioning'` not in `maas4_allowed` list
- MAAS-5: `maas5: true` treated "Failed commissioning" as an error state

But "Failed commissioning" IS an enrolled machine — `trigger-commission.sh` explicitly re-commissions
these machines. Fix: added "Failed commissioning" and "Failed testing" to `maas4_allowed` for both
gate entries, and set `maas5: false` at those stages.

### Fix 4: Commission trigger state reset — force re-run for Failed-commissioning machines

**File**: `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml`

The `null_resource.commission_trigger` uses `system_id + power_type` as triggers. When a machine
is in "Failed commissioning" and re-runs the wave, Terraform says "No changes" (triggers unchanged)
so `trigger-commission.sh` never runs again.

Fix: added a PRE-mode-only section in the commissioning:pre gate that:
1. Identifies machines in "Failed commissioning" or "Failed testing" state
2. Removes their commission unit's GCS state (`{machine_path}/commission/default.tfstate`)
3. This forces Terraform to recreate the null_resource and re-run trigger-commission.sh

This is idempotent state normalization, permitted per CLAUDE.md pre-wave playbook rule.
