# AI Log — MaaS Lifecycle Sanity Check

**Date**: 2026-04-14  
**Session**: doit/maas-lifecycle-sanity

## What was done

Implemented the MaaS lifecycle sanity check (`maas-lifecycle-sanity`), a pre-wave Ansible playbook that runs before each MaaS lifecycle wave (commissioning → ready → allocated → deploying → deployed) to verify physical reality matches MaaS state.

### Files created

**`infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/amt-query.py`**  
Python helper that runs on the MaaS server (via `ansible.builtin.script`). Does a fast TCP check of AMT port 16993 first, then queries `CIM_AssociatedPowerManagementService` via wsman with a 20s timeout to get the live hardware power state. Returns JSON: `{"reachable": bool, "power_state": "on"|"off"|"unknown", "error": str}`. Exit code is always 0 — errors are in the JSON.

**`infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml`**  
Two-play Ansible playbook:
- Play 1 (localhost): Loads `config_base` + `capture-config-fact.yaml` + `framework.yaml` to build the full physical machine list (same Jinja2 logic as `maas-machines-precheck`). Sets `_tf_bucket` from `framework.yaml` and `_annihilate_confirm` from `_MAAS_ANNIHILATE_CONFIRM` env var.
- Play 2 (maas_region): Reads MaaS state, then for each machine in Commissioning/Testing/Deploying state checks the BMC via `amt-query.py` (AMT) or webhook proxy (smart_plug). Proxmox VMs are skipped (power_type != amt/smart_plug). Builds an annihilation list of machines where BMC is off/unknown. Optionally prompts (confirm mode). Then: `maas admin machine delete`, then wipes all GCS Terraform state paths for the machine unit and all lifecycle descendants.

**`infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/run`**  
Runner script — same pattern as `maas-machines-precheck/run`. Uses the shared `test-ansible-playbooks/.venv`.

### Files modified

**`infra/maas-pkg/_config/maas-pkg.yaml`**  
Added `pre_ansible_playbook: maas/maas-lifecycle-sanity` to all five lifecycle waves:
`maas.lifecycle.commissioning`, `maas.lifecycle.ready`, `maas.lifecycle.allocated`, `maas.lifecycle.deploying`, `maas.lifecycle.deployed`.

## Key design decisions

- **No `_SANITY_WAVE` env var needed**: The runner doesn't pass the wave name to pre-playbooks. Instead, the playbook checks ALL `maas.lifecycle.new` machines (same list as `maas-machines-precheck`) regardless of which wave triggered it. This is simpler and catches any stuck machine, not just machines in the current wave.
- **`_MAAS_ANNIHILATE_CONFIRM` env var, not config**: Skipped adding `maas_annihilate_confirm` to `pwy-home-lab-pkg.yaml` since `maas_config` is ancestor-merged from the configure-region unit (null provider stack), not the maas provider root. Using env var is simpler and sufficient.
- **Proxmox VMs skipped**: `power_type: proxmox` machines (pxe-test-vm-1) are not checked. BMC check for Proxmox requires the Proxmox REST API — deferred to a follow-up.
- **20s wsman timeout**: Prevents AMT firmware hangs from blocking the sanity check indefinitely.
- **GCS state wipe paths**: Hardcoded tree of descendant paths (parent + commission + ready + allocated + deploying + deployed) using Python heredoc in the Ansible task. Each path is checked with `gsutil stat` before removing to distinguish "removed" from "not found".
- **annihilate_confirm mode requires TTY**: Documented in playbook header. Default is silent (false).

## Annihilation decision table

| MaaS status | BMC state | Action |
|---|---|---|
| NOT IN MAAS | — | Skip |
| New | — | Skip |
| Commissioning | off/unknown | **Annihilate** |
| Commissioning | on | Skip (actively commissioning) |
| Testing | off/unknown | **Annihilate** |
| Ready/Allocated/Deployed | — | Skip |
| Deploying | off/unknown | **Annihilate** |
| Deploying | on | Skip (actively deploying) |
| Broken | — | Skip (needs operator) |
