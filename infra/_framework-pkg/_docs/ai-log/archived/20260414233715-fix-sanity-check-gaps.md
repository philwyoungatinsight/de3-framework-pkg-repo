# Fix Sanity Check Gaps — maas-lifecycle-sanity

**Date**: 2026-04-14  
**Plan**: `docs/ai-plans/fix-sanity-check-gaps.md`

## What Was Done

Closed four gaps in `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml` and its README.

### Gap 1 — Proxmox/manual machines incorrectly annihilated (FIXED)

The original `_to_annihilate` Jinja2 block had no exclusion for `power_type: proxmox` or
`power_type: manual` machines. Since no BMC query runs for those types, `_bmc_state` has no
entry for them — the fallback returned `power_state=unknown`, meeting the annihilation
condition. Fixed by restructuring the block: power_type mismatch is checked first; the
BMC-state path now has an explicit `and m.power_type not in ['proxmox', 'manual']` guard.

### Gap 2 — No warning log for Broken-state machines (FIXED)

Added a `Warn about machines in Broken state` debug task after the `=== Current MaaS States ===`
summary. Emits a WARNING with instructions (`maas machine mark-fixed`) when any machine has
`status_name == 'Broken'`.

### Gap 3 — README execution flow diagram order (FIXED)

The diagram showed the plug bounce after the BMC queries. In the code, the bounce always
runs before the AMT/smart-plug queries. Fixed the ASCII diagram to show the correct order.

### Gap 4 — power_type mismatch not detected (CRITICAL — FIXED)

Root cause of current Commissioning failures: all four machines (ms01-01, ms01-02, ms01-03,
nuc-1) enrolled in MaaS with `power_type: manual` when config requires `amt` or
`smart_plug`. MaaS cannot issue the reboot needed to complete Commissioning.

Three changes to `playbook.yaml`:
1. `_maas_state` task: now captures `power_type` from MaaS alongside `system_id` and `status_name`.
2. `_to_annihilate` Jinja2 block: completely rewritten. For any enrolled machine where
   `maas_power_type != m.power_type`, appends to annihilation list with
   `reason: 'power_type mismatch: MaaS=<x> config=<y>'`. The BMC-state check only runs
   if power_type matches.
3. Annihilation log task and report task: updated to use `item.reason` instead of hardcoded text.

README (`maas-lifecycle-sanity.md`) updated:
- Annihilation Decision Table: added power_type mismatch row (fires for any enrolled status).
- Known Bugs section: cleared (all bugs fixed).
- Limitations section: updated to reflect proxmox/manual are excluded from BMC path (not buggy).
- Execution Flow diagram: corrected order (bounce before queries).

## Files Changed

- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml`
- `infra/maas-pkg/_docs/maas-lifecycle-sanity.md`

## Verification

Mental trace with live state (all machines Commissioning with power_type=manual in MaaS):
- ms01-01: `maas_power_type=manual` ≠ `config=amt` → **ANNIHILATE** (power_type mismatch)
- ms01-02: `maas_power_type=manual` ≠ `config=amt` → **ANNIHILATE** (power_type mismatch)
- ms01-03: `maas_power_type=manual` ≠ `config=amt` → **ANNIHILATE** (power_type mismatch)
- nuc-1: `maas_power_type=manual` ≠ `config=smart_plug` → **ANNIHILATE** (power_type mismatch)

After annihilation: machines deleted from MaaS, GCS state wiped. Next wave re-enrolls
from scratch via `maas.lifecycle.new` auto-import hook with correct power types.
