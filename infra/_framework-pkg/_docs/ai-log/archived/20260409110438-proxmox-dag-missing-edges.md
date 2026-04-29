# Fix missing Proxmox DAG edges (install-proxmox, wait-for-proxmox)

## Problem

`install-proxmox` and `wait-for-proxmox` had no explicit Terraform dependency edges.
Ordering was enforced entirely by wave sequencing:

- wave 9: `pxe.maas.machine-entries` — physical machines deployed
- wave 11: `hypervisor.proxmox.install` — Proxmox installed on machines
- wave 12: `hypervisor.proxmox.configure` — Proxmox configured

Without the wave runner (`terragrunt run --all`), Terraform had no information
that `install-proxmox` requires machines to exist, or that `wait-for-proxmox`
requires Proxmox to be installed.

## Fix

Added two missing DAG edges (in both `pwy-home-lab-pkg` and `proxmox-pkg/examples`):

**`install-proxmox`** — soft `dependencies` on `configure-physical-machines`:
- MaaS-deployed machines must exist before Proxmox can be installed on them.
- Uses the aggregating unit (single dep, fleet-size-independent).

**`wait-for-proxmox`** — hard `dependency` on `install-proxmox`:
- Proxmox API does not exist until Proxmox is installed.
- Wires `install_proxmox.outputs.run_id` into the trigger so the API poll
  re-runs automatically whenever Proxmox is reinstalled.

## Resulting DAG

```
configure-physical-machines (wave 9)
  → install-proxmox (wave 11)         [new edge]
    → wait-for-proxmox (wave 11)      [new edge]
      → configure-proxmox (wave 12)   [pre-existing]
        → all Proxmox VMs             [pre-existing via _proxmox_deps.hcl]
```
