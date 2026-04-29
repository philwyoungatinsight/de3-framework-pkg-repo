# Decouple proxmox-pkg from MaaS: extract maas_machine_release module

## Problem

`proxmox-pkg/_modules/proxmox_virtual_environment_vm/` contained two optional
variables (`maas_release_hostname`, `maas_server_ip`), a `null_resource` with a
destroy-time provisioner, and a `scripts/release-maas-machine.sh` script — all
MaaS-specific logic embedded in a Proxmox module. This coupled the packages at
the module level: extracting proxmox-pkg into a standalone repo would carry an
undeclared MaaS dependency.

## Solution

Move the release logic to its natural owner (`maas-pkg`) and wire it into the
deployment layer (`pwy-home-lab-pkg`) as a sibling unit.

### New: `infra/maas-pkg/_modules/maas_machine_release/`

Thin Terraform module owned by `maas-pkg`:
- `main.tf` — `null_resource.release` with `when = destroy` provisioner
- `variables.tf` — `hostname`, `maas_server_ip`, `vm_id`
- `scripts/release-maas-machine.sh` — moved here from `proxmox-pkg/_modules/`

`vm_id` is used as a trigger so the resource is destroyed+recreated whenever the
parent Proxmox VM is recreated with a new ID. This preserves the original
behaviour: the release fires on both full destroy AND VM recreation.

### New: `maas-release` sibling units

Two new `maas-release/terragrunt.hcl` units, one per `pxe-test-vm-1` instance:
- `infra/pwy-home-lab-pkg/.../pxe-test-vm-1/maas-release/`
- `infra/proxmox-pkg/.../examples/.../pxe-test-vm-1/maas-release/`

Each unit:
- Declares a `dependency "vm"` on the sibling VM unit to read `vm_id` and `vm_name`
- Uses `_modules_dir: maas-pkg/_modules` + `_provider: 'null'` in config
- Includes `_proxmox_deps.hcl` to inherit the full proxmox-ready dependency chain

Terraform dependency ordering ensures `maas-release` is destroyed before the VM
on `make clean` / `make clean-all`.

### Removed from proxmox module

- `var.maas_release_hostname` and `var.maas_server_ip` from `variables.tf`
- `resource "null_resource" "maas_release_on_destroy"` from `main.tf`
- `scripts/release-maas-machine.sh` (deleted — now lives in maas-pkg)
- `maas_release_hostname` and `maas_server_ip` inputs removed from both
  `pxe-test-vm-1/terragrunt.hcl` files

## Result

`proxmox-pkg` no longer has any MaaS knowledge. The integration logic lives in
the deployment layer (`pwy-home-lab-pkg`), and MaaS owns the release script and
module. The behaviour is identical: MaaS is released on VM destroy and on VM
recreation.
