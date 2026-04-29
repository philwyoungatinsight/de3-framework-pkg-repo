# Proxmox Bridge Configuration Refactor: pve_bridges List Schema

## Summary

Refactored Proxmox bridge configuration from flat per-host variables
(`pve_bridge_technology`, `pve_vlan_bridge`, `pve_cloud_public_ip`, `pve_gateway`)
to a declarative `pve_bridges` list schema. Each bridge entry is a dict describing
its name, NIC, technology, host IP, VLAN subinterface, gateway, and comment.
This enables multi-bridge hosts and cleanly separates concerns across task files.

## Changes

- **`framework/generate-ansible-inventory/generate_ansible_inventory.py`** — emits
  `pve_bridges` list instead of flat vars. If config has a `bridges:` key, passes
  it through directly. Otherwise synthesizes a single-entry backward-compat list
  from the legacy flat fields.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/playbook.configure-pve-networking.yaml`** —
  replaced four flat task includes (configure-linux-bridge, configure-vlan-aware-bridge,
  configure-cloud-public-vlan, configure-ovs-bridge) with a single `configure-bridges.yaml` call.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/playbook.configure-pve.yaml`** — same.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/configure-vlan-aware-bridge.yaml`** —
  removed gateway configuration (was mixing concerns). Gateway now handled exclusively
  by `_configure-bridge-host-ip.yaml`. Task now purely enables VLAN filtering.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/verify-bridge-config.yaml`** —
  updated to iterate `pve_bridges` list and verify each bridge by technology.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/configure-bridges.yaml`** — new
  dispatcher. Processes `pve_bridges` in 5 ordered steps: auto-NIC bridges, explicit-NIC
  bridges, VLAN-aware enablement, OVS bridges, host IP assignment.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/_configure-bridge-host-ip.yaml`** —
  new task. Assigns host IP to bridge or VLAN subinterface; handles gateway.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/_configure-explicit-bridge.yaml`** —
  new task. Creates Linux bridge with explicitly named NIC (no networkd masking needed).
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/_configure-ovs-bridge.yaml`** —
  new task. Creates OVS bridge + NIC attachment + optional OVSIntPort with IP.
- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/README.md`** — updated to describe
  new `pve_bridges` schema, bridge sub-tasks, and backward-compat behavior.
