# Plan: Fix Sanity Check Gaps

## Objective

Close four gaps in the `maas-lifecycle-sanity` playbook and its README. The most critical
is Gap 4: power_type mismatch detection — machines enrolled in MaaS with the wrong power
driver are stuck forever (MaaS cannot power-cycle them). This is confirmed as a root cause
of the current Commissioning failures: all four machines show `power_type: manual` in MaaS
when config requires `amt` or `smart_plug`.

## Context

The `maas-lifecycle-sanity` playbook was implemented in the prior session. After writing
the README and a live state scan, four issues were found:

### Gap 1 — Bug: proxmox/manual power_type machines can be incorrectly annihilated

**Location**: `playbook.yaml` lines 308–326 (the `Determine which machines to annihilate` task)

**Problem**: The `_to_annihilate` Jinja2 block checks `_bmc_state.get(m.hostname, {}).get('power_state', 'unknown')`. For machines with `power_type: proxmox` or `power_type: manual`, no BMC query ever runs (the AMT loop filters to `power_type == 'amt'`, the smart-plug loop filters to `power_type == 'smart_plug'`), so `_bmc_state` has no entry for them. The fallback returns `'unknown'`, which meets the annihilation condition (`ps in ['off', 'unknown']`). Result: any Proxmox VM (`pxe-test-vm-1`) or manual-power machine that is Commissioning/Testing/Deploying would be incorrectly annihilated.

The code comment on lines 306–307 even says "Machines not in MaaS, in New/Ready/Allocated/Deployed states, or with proxmox power_type are left untouched" — but the code does NOT implement the proxmox/manual exclusion.

The README also explicitly states (BMC Check by Power Type table):
- `proxmox`: "Not checked — Skipped in initial implementation"
- `manual`: "Not checked — No BMC available; manual machines are never annihilated"

**Fix**: Add `and m.power_type not in ['proxmox', 'manual']` to the Jinja2 filter in `_to_annihilate`.

### Gap 2 — Missing: No warning log for Broken-state machines

**Location**: `playbook.yaml` — no task for Broken state

**Problem**: The README Annihilation Decision Table says:

> Broken | — | **Skip** (needs operator; do not auto-destroy)

And the Limitations section says:

> Broken state: Machines in `Broken` state are logged as a warning but not annihilated.
> They require manual operator intervention (`maas machine mark-fixed` or physical fix).

There is no debug/warning task in the playbook that logs machines found in `Broken` state.
Without this, an operator running the sanity check gets no indication that a machine needs
manual intervention.

**Fix**: Add a debug task after `=== Current MaaS States ===` that loops over `_machines`
and emits a `WARNING` message for any machine in `Broken` state.

### Gap 3 — README inaccuracy: bounce shown after queries in execution flow

**Location**: `infra/maas-pkg/_docs/maas-lifecycle-sanity.md` — the Execution Flow section

**Problem**: The ASCII flow diagram shows:

```
├─ For each machine in transitional state:
│     ├─ AMT machines:
│     │     1. nc -z -w5 <amt_addr> 16993   (fast TCP check)
│     │     2. wsman enumerate CIM_AssociatedPowerManagementService
│     └─ Smart-plug machines:
│           curl http://127.0.0.1:7050/power/status?host=...
│
├─ (optional) Bounce smart plug to restore AMT standby
```

In the actual code, the plug bounce (`Restore AMT standby via smart plug before BMC check`)
runs **before** the AMT query task (`Query BMC power state for AMT machines`), not after.
The README flow is backwards.

**Fix**: Reorder the README diagram to show bounce before queries.

### Gap 4 — Critical: power_type mismatch not detected or annihilated

**Location**: `playbook.yaml` — `_maas_state` task + `_to_annihilate` task

**Problem**: If a machine is enrolled in MaaS with the wrong `power_type` (e.g., `manual`
instead of `amt`), MaaS cannot power-cycle the machine. Commissioning never completes
because MaaS cannot issue the reboot that returns the machine to a netboot. The machine
sits in `Commissioning` forever with no indication of what went wrong.

Confirmed from live scan (2026-04-14): all four machines show `power_type: manual` in
MaaS. Config requires `amt` (ms01-01, ms01-02, ms01-03) and `smart_plug` (nuc-1). This
is the root cause of the current Commissioning failures.

`maas machine delete` is sufficient MaaS cleanup — it cascades to DHCP reservations, IP
allocations, DNS records, interface records, and power config. No additional MaaS state
needs to be purged. The existing GCS wipe covers the Terraform side.

**Fix requires three changes to `playbook.yaml`**:

1. **`_maas_state` task** — also capture `power_type` from MaaS:

Current:
```jinja2
{%- set _ = result.update({
    m.hostname: {
      'system_id':   m.system_id,
      'status_name': m.status_name
    }
}) -%}
```

Change to:
```jinja2
{%- set _ = result.update({
    m.hostname: {
      'system_id':   m.system_id,
      'status_name': m.status_name,
      'power_type':  m.power_type
    }
}) -%}
```

2. **`_to_annihilate` task** — add power_type mismatch as a second annihilation condition,
checked before the BMC state check. A mismatch triggers annihilation regardless of MaaS
status (even New or Ready — wrong power type means MaaS can never operate the machine).

Replace the existing Jinja2 block with:
```jinja2
{%- set result = [] -%}
{%- for m in _machines -%}
  {%- set status = _maas_state.get(m.hostname, {}).get('status_name', 'NOT IN MAAS') -%}
  {%- if status == 'NOT IN MAAS' -%}
    {# Not yet enrolled — maas.lifecycle.new handles this #}
  {%- else -%}
    {%- set maas_power_type = _maas_state.get(m.hostname, {}).get('power_type', '') -%}
    {%- if maas_power_type != m.power_type -%}
      {# Wrong power driver — MaaS cannot operate this machine at all #}
      {%- set _ = result.append({
          'hostname':     m.hostname,
          'system_id':    _maas_state[m.hostname].system_id,
          'machine_path': m.machine_path,
          'maas_status':  status,
          'bmc_state':    'n/a',
          'reason':       'power_type mismatch: MaaS=' ~ maas_power_type ~ ' config=' ~ m.power_type
      }) -%}
    {%- elif status in ['Commissioning', 'Testing', 'Deploying']
             and m.power_type not in ['proxmox', 'manual'] -%}
      {%- set bmc = _bmc_state.get(m.hostname, {}) -%}
      {%- set ps = bmc.get('power_state', 'unknown') -%}
      {%- if ps in ['off', 'unknown'] -%}
        {%- set _ = result.append({
            'hostname':     m.hostname,
            'system_id':    _maas_state[m.hostname].system_id,
            'machine_path': m.machine_path,
            'maas_status':  status,
            'bmc_state':    ps,
            'reason':       'stuck: ' ~ status ~ ' but BMC=' ~ ps
        }) -%}
      {%- endif -%}
    {%- endif -%}
  {%- endif -%}
{%- endfor -%}
{{ result }}
```

3. **Annihilation log task** — update to show `item.reason` instead of hardcoded text:

```yaml
- name: "=== Annihilation list ==="
  ansible.builtin.debug:
    msg: >-
      {{ item.hostname }}:
      MaaS={{ item.maas_status }}, BMC={{ item.bmc_state }}
      → ANNIHILATE ({{ item.reason }})
  loop: "{{ _to_annihilate }}"
```

**Fix also requires updating `infra/maas-pkg/_docs/maas-lifecycle-sanity.md`**:

- Add `power_type mismatch` row to the Annihilation Decision Table:
  `| Any status | — | power_type in MaaS ≠ config | ANNIHILATE | Wrong power driver; MaaS cannot operate machine |`
- Update the Known Bugs section to remove the power_type mismatch from the bug list for
  proxmox/manual (that bug is about the BMC check path; the new power_type check is a
  separate and more general fix)
- Note in the Execution Flow that power_type is checked before BMC queries

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml` — modify

**Change 1**: Fix the `_to_annihilate` Jinja2 block (task "Determine which machines to annihilate", ~line 308).

Current inner condition:
```jinja2
{%- if status in ['Commissioning', 'Testing', 'Deploying'] -%}
  {%- set bmc = _bmc_state.get(m.hostname, {}) -%}
  {%- set ps = bmc.get('power_state', 'unknown') -%}
  {%- if ps in ['off', 'unknown'] -%}
```

Change to (add power_type guard):
```jinja2
{%- if status in ['Commissioning', 'Testing', 'Deploying']
    and m.power_type not in ['proxmox', 'manual'] -%}
  {%- set bmc = _bmc_state.get(m.hostname, {}) -%}
  {%- set ps = bmc.get('power_state', 'unknown') -%}
  {%- if ps in ['off', 'unknown'] -%}
```

Also update the task comment (lines 306–307) to note that proxmox and manual are excluded,
matching the code's actual behavior.

**Change 2**: Add a Broken-state warning task immediately after the `=== Current MaaS States ===` debug task (after line 152). Insert:

```yaml
    - name: Warn about machines in Broken state (needs operator intervention)
      ansible.builtin.debug:
        msg: >-
          WARNING: {{ item.hostname }} is in Broken state in MaaS.
          This machine will NOT be annihilated automatically.
          Manual intervention required: maas {{ _maas_user }} machine mark-fixed <system_id>
          or fix the physical hardware, then re-run from maas.lifecycle.new.
      loop: "{{ _machines }}"
      loop_control:
        label: "{{ item.hostname }}"
      when:
        - item.hostname in _maas_state
        - _maas_state[item.hostname].status_name == 'Broken'
```

### `infra/maas-pkg/_docs/maas-lifecycle-sanity.md` — modify

Two changes:

**Change 1 — Add Known Bugs section** (already done): A "Known Bugs" section has been
added above the Limitations section, documenting both the proxmox/manual annihilation bug
and the missing Broken state warning. The Limitations section has been updated to cross-
reference the bugs. This change is complete — do not redo it.

**Change 2 — Fix Execution Flow diagram order**: Change the block that shows bounce AFTER
queries to show bounce BEFORE queries.

Current (wrong order):
```
          └── Play 2 (maas_region / MaaS server)
                ├─ Login to MaaS CLI
                ├─ Read all machines → build hostname→status map
                ├─ For each machine in transitional state:
                │     ├─ AMT machines:
                │     │     1. nc -z -w5 <amt_addr> 16993   (fast TCP check)
                │     │     2. wsman enumerate CIM_AssociatedPowerManagementService
                │     │        (20s timeout; returns PowerState integer)
                │     └─ Smart-plug machines:
                │           curl http://127.0.0.1:7050/power/status?host=...
                │
                ├─ (optional) Bounce smart plug to restore AMT standby
                │
                ├─ Determine annihilation list
```

Replace with (correct order — bounce before queries):
```
          └── Play 2 (maas_region / MaaS server)
                ├─ Login to MaaS CLI
                ├─ Read all machines → build hostname→status map
                ├─ (optional) Bounce smart plug to restore AMT standby
                │     For mgmt_wake_via_plug machines: if AMT port 16993 unreachable,
                │     bounce plug (off → 10s → on), poll up to 120s for AMT to respond
                │
                ├─ For each machine in transitional state:
                │     ├─ AMT machines (power_type=amt):
                │     │     1. nc -z -w5 <amt_addr> 16993   (fast TCP check)
                │     │     2. wsman enumerate CIM_AssociatedPowerManagementService
                │     │        (20s timeout; returns PowerState integer)
                │     ├─ Smart-plug machines (power_type=smart_plug):
                │     │     curl http://127.0.0.1:7050/power/status?host=...
                │     └─ Proxmox/manual machines: skipped (no BMC check)
                │
                ├─ Determine annihilation list
```

---

## Execution Order

1. Modify `playbook.yaml`:
   - `_maas_state` task: add `power_type` capture (Gap 4)
   - `_to_annihilate` task: replace Jinja2 block with new logic (Gaps 1 + 4 together)
   - Annihilation log task: add `item.reason` to message (Gap 4)
   - Add Broken-state warning task after `=== Current MaaS States ===` (Gap 2)
2. Modify `maas-lifecycle-sanity.md`:
   - Fix execution flow diagram order (Gap 3)
   - Update Annihilation Decision Table (add power_type mismatch row) (Gap 4)
   - Update Known Bugs section to reflect power_type mismatch is now fixed (Gap 4)

## Verification

After applying changes, mental trace against current live state (all machines in Commissioning with power_type=manual):

- ms01-01: in MaaS, `maas_power_type=manual` ≠ `config=amt` → **ANNIHILATE** (reason: power_type mismatch)
- ms01-02: in MaaS, `maas_power_type=manual` ≠ `config=amt` → **ANNIHILATE** (reason: power_type mismatch)
- ms01-03: in MaaS, `maas_power_type=manual` ≠ `config=amt` → **ANNIHILATE** (reason: power_type mismatch)
- nuc-1: in MaaS, `maas_power_type=manual` ≠ `config=smart_plug` → **ANNIHILATE** (reason: power_type mismatch)

All four deleted from MaaS + GCS state wiped. Next wave re-enrolls from scratch with correct power types.
