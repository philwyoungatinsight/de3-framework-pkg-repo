# Fix Wave 10: MaaS Machine Automation Issues

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10), pxe.maas.test-vms (wave 11)

## Summary

Fixed two automation bugs that caused wave 10 (pxe.maas.machine-entries) to fail on retries, and improved the pre-check playbook to fail fast with clear error messages.

## Bugs Fixed

### 1. auto-import: maas_instance.this not imported when machine already Deployed (409 Conflict)

**Root cause**: When the MaaS Terraform provider loses its connection mid-deployment (e.g. MaaS snap restarts under heavy I/O), `maas_instance.this` fails to be persisted in Terraform state even though the machine finishes deploying in MaaS. On the next retry, `check_and_clean_state()` sees the machine is "Deployed" and returns True, but `maas_instance.this` is not in state. Terraform then tries to create it → MaaS returns `409 Conflict: No machine with system ID <id> available.`

**Fix**: In `infra/maas-pkg/_tg_scripts/maas/auto-import/run`, added logic in the `else` branch of `check_and_clean_state()` (when `live_status == "Deployed"`) to import `maas_instance.this` if it is not already in state. This prevents the 409 error on subsequent retries.

```python
# When machine is Deployed but maas_instance.this is NOT in state:
rc_inst, _ = _tofu_out("state", "show", "maas_instance.this")
if rc_inst != 0:
    _tofu("import", "maas_instance.this", stored_id)
```

Also manually ran `terragrunt import maas_instance.this brfpky` for the current nuc-1 state to unblock the in-flight retry.

### 2. maas-managed-vms-test: wrong wave name reference

**Root cause**: The test playbook was looking for machines in wave `on_prem.maas.managed.vms` which doesn't exist. The actual wave is `pxe.maas.test-vms`.

**Fix**: Rewrote `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-managed-vms-test/playbook.yaml` to check the correct `pxe.maas.test-vms` wave. Also added proper ancestor `_skip_on_build` inheritance check, port 22 reachability check, and cleaner Deployed status assertion.

### 3. Pre-check: no AMT reachability check (slow failures, burnt retries)

**Root cause**: When ms01 physical machines (ms01-01/02/03) are physically off (no AC power), Intel AMT port 16993 is unreachable. `configure-physical-machines` tries to power them on via AMT and fails. Without a pre-check, this wastes all 3 retries of the wave (and each retry burns 22+ seconds before failing).

**Fix**: Added an AMT reachability check to `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-precheck/playbook.yaml`. The new `Check AMT reachability for unenrolled physical machines` play:
1. Reads the list of AMT machines in the wave from YAML config
2. Reads which machines are already in MaaS (enrolled machines don't need AMT reachability)
3. Runs `nc -z -w3 <amt_address> 16993` from the MaaS server for each unenrolled AMT machine
4. Fails fast with a clear message if any AMT port is unreachable

Result: The wave now fails in ~10 seconds (3 nc checks × 3s timeout) instead of burning 3 retries × 22s each.

## Known Hardware Pre-condition

**ms01-01/02/03 require physical AC power before automation can manage them.**

- AMT (Intel Active Management Technology) requires standby power to operate
- AMT is only active when the machine has AC power connected (even when powered off)
- Without AC power: AMT port 16993 is completely unreachable
- Symptom: `nc -z -w3 10.0.11.10 16993` returns closed from MaaS server
- Verified at: 10.0.11.10 (ms01-01), 10.0.11.11 (ms01-02), 10.0.11.12 (ms01-03)

This is documented as a one-time physical prerequisite in `docs/idempotence-and-tech-debt.md`.

## Wave Status After Fixes

- Wave 9 (pxe.maas.seed-server): ✅ PASSED
- Wave 10 (pxe.maas.machine-entries): ❌ FAILS at precheck — "AMT port 16993 unreachable for ms01-01/02/03"
  - nuc-1 is Deployed (brfpky) with maas_instance.this imported to TF state
  - Wave will pass once ms01 machines have AC power
- Wave 11 (pxe.maas.test-vms): Not yet attempted
