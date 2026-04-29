# Fix Wave 10: AMT S5 Commission/Deploy Automation

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed multiple automation issues preventing wave 10 from fully commissioning and deploying
all physical machines (ms01-01, ms01-02, ms01-03, nuc-1) without manual intervention.
Key issues: AMT S5 state on MS-01 hardware, SSH `known_hosts` blocking, Terraform heredoc
interpolation escaping, commission timeout too short, and stale GCS state locks.

## Bugs Fixed

### 1. All SSH calls in main.tf missing `UserKnownHostsFile=/dev/null`

**Root cause**: CLAUDE.md requires BOTH `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`.
The original code only had `StrictHostKeyChecking=no`, which still blocks on CHANGED keys
(happens after every MaaS server rebuild).

**Fix**: Batch-replaced all SSH calls in `infra/maas-pkg/_modules/maas_machine/main.tf` to
include `-o UserKnownHostsFile=/dev/null`.

### 2. commission-and-wait.sh timeout too short for physical machines

**Root cause**: `_COMMISSION_WAIT_TIMEOUT` defaulted to 900s (15 min). Physical MS-01 machines
need 15-30+ minutes to commission. At 900s, a machine still actively commissioning triggered
the timeout → spurious retry → wasted commissioning cycle.

**Fix**: Changed default from 900s to 2400s (40 min) in
`infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`.

```bash
# Default 40 min per attempt. Physical machines with real disks need 15-30+ min
_COMMISSION_WAIT_TIMEOUT="${_COMMISSION_WAIT_TIMEOUT:-2400}"
```

Also updated the `wait_for_condition` call from `_COMMISSION_WAIT_TIMEOUT 900 10` to
`_COMMISSION_WAIT_TIMEOUT 2400 10`.

### 3. Terraform heredoc interpolation escaping in pre_deploy_kick

**Root cause**: Inside a TF `<<-EOT...EOT` heredoc, ALL `${...}` are processed as Terraform
expressions. Bash variable references `${SYSTEM_ID}` and `${AMT_PARAMS_B64}` in a nested
`<<SSHEOF...SSHEOF` heredoc were being interpreted as Terraform resource references, causing
`Error: A reference to a resource type must be followed by at least one attribute access`.

**Fix**: Changed `${SYSTEM_ID}` → `${SYSTEM_ID}` and `${AMT_PARAMS_B64}` → `${AMT_PARAMS_B64}`
in the nested SSHEOF block. Terraform outputs the `${VAR}` literal which the local bash
`<<SSHEOF` then expands at runtime.

**Verification**: `grep -n '\${SYSTEM_ID}\|\${AMT_PARAMS_B64}' main.tf | grep -v '\$\${'` returns empty.

### 4. AMT S5 state: pre_deploy_kick hangs when MS-01 powers off

**Root cause**: MS-01 hardware AMT Management Engine enters S5 (ME firmware offline) when
the machine powers off. Unlike most AMT hardware, MS-01 does NOT maintain AMT in S5.
`maas machine power-on` via AMT wsman hangs indefinitely when AMT ME is offline.

**Fix**: Rewrote `pre_deploy_kick` in `main.tf` to:
1. Read the machine's `power_type` from TF triggers
2. If `power_type = "amt"`: probe AMT port 16993
   - If reachable: use direct wsman power-on (ChangeBootOrder + SetBootConfigRole + RequestPowerStateChange)
   - If unreachable: fall back to `timeout 90 maas machine power-on` (will fail gracefully)
3. If `power_type != "amt"`: use `timeout 90 maas machine power-on`

Also added `power_type` to the `pre_deploy_kick` triggers so TF recreates the resource
if the power type changes.

### 5. AMT S5 fast-fail in commission-and-wait.sh

**Root cause**: When an AMT machine (MS-01) is fully off with no AC power, commissioning
would wait the full `_COMMISSION_WAIT_TIMEOUT` (2400s) × 3 retries = 7200s before failing
with a clear error. No indication to the user that physical power-on was needed.

**Fix**: Added fast-fail check at the start of the AMT commissioning branch in
`commission-and-wait.sh`. Before `_amt_power_cycle`, the script now:
1. Fetches the machine's AMT address from MaaS
2. Probes port 16993 with `nc -z -w3`
3. If unreachable: exits immediately with clear error:
   ```
   ERROR: <system_id> AMT port <addr>:16993 is unreachable.
     MS-01 AMT Management Engine is offline (machine is fully powered off / in S5).
     ACTION REQUIRED: Physically power on the machine, then retry the wave.
   ```

This reduces failure detection from 7200s to ~15s (2 SSH calls + nc timeout).

## Known Hardware Behavior

**MS-01 AMT ME in S5**: Intel AMT Management Engine goes offline when the machine
powers off completely. Unlike most AMT hardware, AMT port 16993 becomes unreachable.
After a power cycle (physical or smart-plug), AMT ME comes back online.

**Symptom**: `nc -z -w3 10.0.11.{10,11,12} 16993` from MaaS server returns closed/timeout.

**Workaround in automation**: The new pre_deploy_kick detects unreachable AMT and falls
back to `timeout 90 maas machine power-on` which uses MaaS's AMT driver (which will
also fail if AMT is down, but at least fails in 90s instead of hanging indefinitely).

## Stale Lock Recovery

Killing a wave mid-apply leaves stale GCS state locks. Two locks needed manual removal
after the previous apply was killed:

```bash
gsutil rm gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01/default.tflock
gsutil rm gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-03/default.tflock
```

**Fix needed**: The wave runner or `auto_import` hook should check for stale locks and
clear them before retrying. A lock is stale if the lock holder process no longer exists.

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/main.tf` — SSH opts, pre_deploy_kick AMT wsman, triggers
- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh` — timeout 2400s, AMT fast-fail
