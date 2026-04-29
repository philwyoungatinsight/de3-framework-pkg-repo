# Plan: MaaS Lifecycle Sanity Check — Physical Reality Verification

**Date**: 2026-04-15  
**Status**: READY TO EXECUTE

---

## Problem

MaaS machine state routinely diverges from physical reality. Machines appear as
"Commissioning" or "New" in MaaS while they are actually powered off. The lifecycle
automation then spends 5–30 minutes polling for state transitions that will never
happen, or worse, silently succeeds at Terraform level while nothing real occurred.

Root cause: the precheck and lifecycle scripts only read MaaS database state. They
never verify physical reality (can we reach the BMC? is the machine actually on?).

## Solution

A reusable Ansible playbook — `maas-lifecycle-sanity.yaml` — that is called as a
**`pre_ansible_playbook`** on every lifecycle wave. For each machine in the wave it:

1. Reads MaaS state
2. Verifies physical reality via the BMC (AMT wsman power query, or webhook power
   status endpoint)
3. If the BMC is unreachable, bounces the smart plug (if configured) and re-checks
4. Compares MaaS state vs physical reality; if divergence is detected, **annihilates**
   the machine: deletes it from MaaS and removes all descendant Terraform state so the
   wave starts clean from scratch
5. A config option (`maas_annihilate_confirm`, default `false`) controls whether the
   playbook annihilates silently (false) or pauses and prompts the operator first (true)

---

## Scope

### What "annihilate" means
- `maas admin machine delete <system_id>` on the MaaS server
- `gsutil rm` of the GCS state files for the machine unit and all its descendants
  (commission, commission/ready, commission/ready/allocated, .../deploying, .../deployed)
- After deletion the machine is gone from both MaaS and TF state; the `maas.lifecycle.new`
  precheck will re-enroll it on the next run

### When to annihilate
| MaaS status | Physical BMC state | Action |
|---|---|---|
| NOT IN MAAS | — | No action (precheck handles enrollment) |
| New | — | No action (never touched; precheck will power-cycle it) |
| Commissioning | off / unknown | **Annihilate** — stuck, will never complete |
| Commissioning | on | OK — actively commissioning; log and exit 0 |
| Testing | off / unknown | **Annihilate** — stuck |
| Ready | — | OK — skip (short-circuit for later waves) |
| Allocated | — | OK — skip |
| Deploying | off / unknown | **Annihilate** — stuck |
| Deploying | on | OK — actively deploying; log and exit 0 |
| Deployed | — | OK — skip |
| Broken | — | Log warning; do NOT annihilate (needs operator) |
| Failed commissioning | — | No action — wave retry handles this |
| Failed deployment | — | No action — wave retry handles this |

### What "physical BMC state" means
For AMT machines:
1. `nc -z -w5 <amt_address> 16993` — TCP reachability test (fast; if this fails → unreachable)
2. If reachable: run `wsman` with `timeout 20` to query `CIM_AssociatedPowerManagementService`
   and get the actual power state (`PowerState=2` = on, `PowerState=8` = off, etc.)
3. If wsman hangs or TCP is unreachable: AMT firmware is not responding → try smart plug

For smart-plug machines (`power_type: webhook`):
1. `curl -sf http://localhost:7050/power/status?host=<plug_host>&type=<plug_type>` (from MaaS server)

For `mgmt_wake_via_plug: true` machines when AMT is unreachable:
1. Bounce the plug: off → 10s → on
2. Wait up to 120s for AMT port 16993 to respond
3. Re-check power state
4. If still unreachable: mark as "AMT unreachable after bounce" and annihilate (clean slate)

---

## Files to Create / Modify

### `infra/maas-pkg/_wave_scripts/common/maas-lifecycle-sanity/playbook.yaml` — create

New playbook. Two plays:
- **Play 1 (localhost)**: load config_base + capture MaaS facts; build machine list for the
  target wave (same Jinja logic as maas-machines-precheck but parametrised by wave name via env var
  `_SANITY_WAVE`); read `maas_annihilate_confirm` config flag
- **Play 2 (maas_region)**: for each machine in the list, run the sanity loop:
  - Read MaaS state
  - Check BMC (AMT nc + wsman or webhook curl)
  - If BMC unreachable: try smart plug bounce (if `mgmt_wake_via_plug: true`)
  - Compare state vs reality; build `_to_annihilate` list
  - If `maas_annihilate_confirm: true` and list is non-empty: `pause` and ask operator
  - For each machine in `_to_annihilate`:
    - `maas admin machine delete <system_id>`
    - Run `gsutil rm` to wipe GCS state for the machine unit and all descendants

The playbook must be **idempotent**: if the machine is already in a clean state, it logs
"ok" and exits 0 without touching anything.

Key env vars the playbook reads:
- `_SANITY_WAVE` — which wave's machines to check (e.g. `maas.lifecycle.commissioning`)
- `_MAAS_ANNIHILATE_CONFIRM` — overrides config flag if set

Implementation sketch:

```yaml
- name: MaaS lifecycle sanity check
  hosts: maas_region
  gather_facts: false
  tasks:
    - name: Build sanity check results for each machine
      ansible.builtin.shell: |
        python3 << 'PYEOF'
        # For each machine: check MaaS state, check BMC, decide action
        # Returns JSON: {"hostname": ..., "maas_status": ..., "bmc_state": ..., "action": "ok"|"annihilate"}
        PYEOF
      loop: "{{ _machines }}"

    - name: Prompt operator before annihilating (if confirm mode)
      ansible.builtin.pause:
        prompt: "About to annihilate: {{ _annihilate_list }}. Press ENTER to continue, Ctrl-C to abort"
      when:
        - _annihilate_confirm | bool
        - _annihilate_list | length > 0

    - name: Delete machine from MaaS
      ansible.builtin.command: maas admin machine delete {{ item.system_id }}
      loop: "{{ _annihilate_list }}"
      become: true

    - name: Wipe GCS Terraform state for annihilated machines
      ansible.builtin.shell: |
        # gsutil rm for machine unit + all descendants
        for path in {{ item.tf_state_paths | join(' ') }}; do
          gsutil rm "gs://{{ _tf_bucket }}/${path}/default.tfstate" 2>/dev/null || true
        done
      loop: "{{ _annihilate_list }}"
      delegate_to: localhost
```

### `infra/maas-pkg/_wave_scripts/common/maas-lifecycle-sanity/amt-query.py` — create

Python helper script that runs on the MaaS server to query AMT power state via wsman
with a hard timeout (20s). Accepts `AMT_ADDR`, `AMT_PASS`, `OPENSSL_CONF` env vars.
Returns JSON: `{"reachable": bool, "power_state": "on"|"off"|"unknown", "error": str}`.

The script is copied to the MaaS server by `ansible.builtin.script` (same pattern as
`amt-power-cycle`).

### `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` — modify

Add `maas_annihilate_confirm: false` under the MaaS provider root config
(`cat-hmc/maas/pwy-homelab`). This makes the default "silent annihilate" (no prompt).
Operators who want a prompt set it to `true` in their environment's config.

### `config/waves_ordering.yaml` — modify (inspect first)

Add `pre_ansible_playbook` pointing to `maas-lifecycle-sanity/playbook.yaml` on these waves:
- `maas.lifecycle.commissioning`
- `maas.lifecycle.ready`
- `maas.lifecycle.allocated`
- `maas.lifecycle.deploying`
- `maas.lifecycle.deployed`

The sanity check is NOT needed on `maas.lifecycle.new` (precheck already handles enrollment
from a clean state). It IS needed on all subsequent waves because those are where divergence
causes silent infinite polls.

The `_SANITY_WAVE` env var passed to the playbook matches the wave name so the playbook
knows which machines to check.

### `infra/maas-pkg/_tg_scripts/maas/amt-power-cycle/run` — inspect (may not need changes)

The existing `amt-power-cycle/run` script handles PXE boot override + power cycle. The new
`amt-query.py` is a separate read-only query tool; they coexist.

---

## Execution Order

1. Create `amt-query.py` helper (needed by the playbook)
2. Create `maas-lifecycle-sanity/playbook.yaml`
3. Add `maas_annihilate_confirm: false` to `pwy-home-lab-pkg.yaml`
4. Add `pre_ansible_playbook` to waves in `waves_ordering.yaml`
5. Test: run `maas.lifecycle.commissioning` with machines in a bad state; verify
   the sanity check detects divergence, annihilates cleanly, and the wave retries

---

## Verification

After implementation, the following scenario must work:

1. Put ms01-02 in "Commissioning" state in MaaS (manually or via previous wave run)
2. Power off ms01-02 physically (or via AMT)
3. Run `./run --wave maas.lifecycle.commissioning`
4. The sanity pre-check should detect: ms01-02 is Commissioning but power is off → annihilate
5. The wave should then re-run the commission trigger, which sees "NOT IN MAAS" → precheck re-enrolls → commission succeeds

---

## Open Questions

None — ready to proceed.

---

## Risks and Gotchas

### GCS state path derivation
The TF state path for a unit is derived from its terragrunt path relative to the repo root.
Must use the correct bucket name from config, and must enumerate all descendant paths
(commission, commission/ready, etc.) correctly. Use a helper that walks the known tree:
`machines/<name>`, `machines/<name>/commission`, `.../ready`, `.../allocated`,
`.../deploying`, `.../deployed`.

### `ansible.builtin.pause` requires a TTY
If `maas_annihilate_confirm: true` and the playbook runs non-interactively (CI/CD),
`ansible.builtin.pause` will fail. This is intentional — confirm mode is for interactive
operator use only. Document this in the playbook header.

### wsman timeout
The existing `amt-power-cycle/run` script can hang during TLS if AMT firmware is in a bad
state (confirmed in this session). The new `amt-query.py` MUST use `subprocess.run(...,
timeout=20)` and treat timeout as "BMC unreachable".

### Smart plug bounce order
Bounce the plug (off → 10s → on) BEFORE waiting for AMT. Don't bounce if AMT is already
reachable (unnecessary disruption). Only bounce if `mgmt_wake_via_plug: true` AND AMT nc
check fails.

### pxe-test-vm-1 and other Proxmox VMs
These have `power_type: proxmox`. BMC check for Proxmox VMs: query the Proxmox API
(`pvesh get /nodes/<node>/qemu/<vmid>/status/current`) to get the VM power state.
The wave sanity check should handle `power_type: proxmox` by calling the Proxmox REST API.
For the initial implementation, skip the power check for Proxmox VMs and only check
reachability (can we SSH to the VM after deployment?). Add Proxmox power query in a
follow-up.
