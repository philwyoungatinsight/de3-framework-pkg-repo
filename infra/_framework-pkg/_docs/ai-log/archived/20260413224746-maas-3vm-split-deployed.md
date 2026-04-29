# MaaS 3-VM Split Architecture — Successfully Deployed

**Date**: 2026-04-13  
**Session**: maas-3vm-split-deployed

## Summary

The 3-VM MaaS split architecture (`maas-db-1`, `maas-region-1`, `maas-rack-1`) is now fully
deployed and passing the `pxe.maas.seed-server` wave test. This completes the migration from
the old single-VM `maas-server-1` (combined region+rack+DB).

## Bugs Fixed This Session

### 1. Stale `configure-server` unit on disk
The old `configure-server/terragrunt.hcl` was still present on disk without a YAML config
entry. Without the entry, `modules_dir` fell back to `default-pkg/_modules` where
`null_resource__configure-server` doesn't exist, causing wave clean to fail.

**Fix**: Stopped and deleted orphan Proxmox VMs (100, 101, 102) via Proxmox API, removed
GCS state for `configure-server` and `maas-server-1` units, then deleted both directories.

### 2. IP conflicts from orphan VMs
Three VMs simultaneously held `10.0.10.11` — two old `maas-server-1` stale VMs (IDs 100,
101) and the new `maas-region-1` (ID 105). Ansible was connecting to the old VMs and failing
with `[Errno 2] No such file or directory: b'maas'`.

**Fix**: Stopped and deleted VMs 100 and 101 via Proxmox REST API. Only fresh VMs
(maas-db-1=102, maas-rack-1=104, maas-region-1=105) remain.

### 3. `configure-maas-networking.yaml` called before rack existed
In the 3-VM split, `configure-region` runs before any rack controller is registered.
`configure-maas-networking.yaml` calls `maas rack-controllers read` which returns `[]`,
then `[0].system_id` fails with `AnsibleLazyTemplateList has no element 0`.

**Root cause**: Old single-VM arch ran `maas init region+rack` creating both simultaneously,
so rack always existed when networking was configured. Split arch separates these steps.

**Fix**: Removed `configure-maas-networking.yaml` include from `configure-region` playbook.
`configure-rack` play 3 (which runs on `maas_region` *after* rack joins) already calls
the full networking task, so no functionality was lost.

## Final State

Wave `pxe.maas.seed-server` passes all phases:
- Apply: 7/7 units succeeded
- Test playbook: MaaS 3.7.2 API healthy, 11 boot resources confirmed
- 3-VM split running: maas-db-1 (10.0.10.12), maas-region-1 (10.0.10.11), maas-rack-1 (10.0.10.13 + 10.0.12.2)
- DHCP active on provisioning VLAN 10.0.12.100-200
- maas-region-1 has static route to 10.0.12.0/24 via 10.0.10.13 for SSH jump box function
