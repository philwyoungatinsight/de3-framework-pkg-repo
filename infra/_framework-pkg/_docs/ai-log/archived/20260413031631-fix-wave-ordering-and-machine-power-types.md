# Fix wave ordering gaps and physical machine power types

## Summary

Fixed two missing wave definitions and corrected power management config for physical MaaS machines discovered during autonomous `make` debugging.

## Changes

### 1. `config/waves_ordering.yaml` — Added two missing waves

- Added `pxe.maas.test-vms` between `pxe.maas.seed-server` and `maas.lifecycle.new`
- Added `pxe.maas.machine-entries` between `maas.lifecycle.deployed` and `hypervisor.proxmox.install`

Both waves were referenced in unit configs (`_wave:` field) but never listed in the ordering file, causing the runner to silently skip all their units.

### 2. `infra/maas-pkg/_config/maas-pkg.yaml` — Added wave definitions

Added `pxe.maas.test-vms` and `pxe.maas.machine-entries` wave metadata (description, test_ansible_playbook, update_inventory) so the wave runner recognises them.

### 3. `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` — Two changes

- **pxe-test-vm-1 MaaS unit**: Changed `_wave: maas.lifecycle.new` → `pxe.maas.test-vms`. The Proxmox VM and its MaaS machine entry are now in the same wave; the DAG handles VM creation before MaaS import.
- **ms01-03**: Changed `power_type: manual` → `power_type: amt`. AMT at 10.0.11.12:16993 is confirmed reachable from the MaaS server. The machine had `power_pass` in secrets all along; the "not responding" note was a stale comment from an earlier issue.

### 4. Cloud test playbook (`demo-buckets-example-pkg/.../cloud-resources-all-resources-test/playbook.yaml`)

Fixed to SKIP (not FAIL) when a unit's state exists but is empty `{}` — happens for units excluded via `_skip_on_build`.

## Remaining blockers (require physical intervention)

### ms01-01 — AMT unreachable
- AMT at 10.0.11.10 returns "No route to host" even from the MaaS server
- No smart plug configured
- Cannot be auto-powered; needs either AMT configured in BIOS or a smart plug added
- The `power_type: manual` setting is correct but means the machine times out in the auto-import hook every run

### nuc-1 — Not booting onto provisioning VLAN
- Smart plug at 192.168.1.225 is working (power on/off succeeds via proxy)
- NUC is powered on but not requesting DHCP on VLAN 12 (provisioning)
- Previous lease (Apr 12 23:19) showed `vendor-class-identifier: "Linux ipconfig"` — Ubuntu was running
- After multiple power cycles (2026-04-13 02:53 and 03:15), no new DHCP lease appears
- Possible causes: BIOS not configured for PXE first, disk boot failing silently, or network cable disconnected from provisioning VLAN port
- Needs physical access to investigate (check display output, BIOS, cable connections)

## Status

Wave `pxe.maas.test-vms` passed (pxe-test-vm-1 created and imported). Wave `maas.lifecycle.new` still failing due to the two physical machine issues above.
