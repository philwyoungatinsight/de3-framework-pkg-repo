# Add _purpose reserved unit param

## What

Added `_purpose` as an optional reserved unit parameter — a human-readable string
that describes what a unit does and why it exists. Purely informational; no effect
on apply/destroy behaviour. Consistent with existing reserved-key naming convention
(`_wave`, `_region`, `_env`, etc.).

## Where it is documented

`docs/framework/unit_params.md` — new `_purpose` section covering:
- Type / inheritance / framework-effect
- When to set it (aggregating units, ancestor path entries, utility VMs, leaf units)
- Suggested rollout order (phases 1–4)

## Units populated (phase 1 — aggregating/orchestration units)

All in `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`:

| Unit | Purpose |
|------|---------|
| `configure-physical-machines` | Aggregating unit for full machine fleet; downstream deps point here |
| `install-proxmox` | Install Proxmox VE on MaaS-deployed Debian hosts |
| `wait-for-proxmox` | Poll Proxmox API until reachable; gate before VM provisioning |
| `configure-proxmox` | VLAN bridge, storage, API token, SSH key sync on all nodes |
| `configure-proxmox-post-install` | Same playbook scoped to newly-installed nodes, triggered by run_id |
| `maas/configure-server` | PostgreSQL, snap, DHCP/DNS, images, preseed, API key → SOPS |
| `maas/sync-maas-api-key` | Write API key to SOPS; gates all MaaS provider auth |
| `mesh-central/configure-server` | MeshCentral VM install with Intel AMT ACM patches |
| `mesh-central/update-mesh-central` | Aggregating unit; enroll all managed hosts into MeshCentral |

## Remaining phases (not yet done)

2. Ancestor path entries (subtree `_wave`/`_provider`/`_skip_*` annotations)
3. Utility VMs (maas-server-1, mesh-central, image-maker, pxe-test-vm-1)
4. Leaf VMs and physical machines
