# UniFi VLAN redesign: fix PXE boot + MaaS script silent failures

## Problem

ms01-01 was stuck at "start pxe ... a2" — the machine PXE-booted on the data NIC (MAC a2)
but DHCP negotiation never completed. Root cause: the USW-Flex PXE ports (4/5/6) were on
`pxe_mgmt_public` which has native VLAN 11 (management). UniFi DHCP on VLAN 11 answered
PXE requests without PXE boot options, so the machine got a DHCP lease but no next-server
or boot filename. MaaS DHCP only runs on VLAN 12 (provisioning), so it never received the
DHCP request.

Secondary issue: the configure-server `null_resource` hash only included `maas-pkg.yaml`,
not `pwy-home-lab-pkg.yaml`, so smart_plug_host changes for ms01-01 didn't trigger a
re-run of the Ansible configure-server playbook → Tapo credentials missing from
smart-plug-proxy config.json.

## Changes

### Network redesign (`pwy-home-lab-pkg.yaml`)

- VLAN 11 (management): `dhcp_enabled: false` — UniFi DHCP disabled; AMT static IPs only
- VLAN 12 (provisioning): kept as-is; MaaS is the only DHCP authority here
- New port profile `amt_mgmt`: native VLAN 11, no tagged VLANs — for AMT NICs (USW-Flex 1/2/3)
- New port profile `pxe_provisioning`: native VLAN 12, no tagged VLANs — for PXE/data NICs (USW-Flex 4/5/6)
- `hypervisor_trunk`: added VLAN 12 to tagged_vlans so pve-1 can reach the provisioning VLAN
- Pro Max port 18 (`Temp-2-PVE-10G`): assigned to `hypervisor_trunk`
- AMT static IPs unchanged: 10.0.11.10/11/12 for ms01-01/02/03

### configure-server hash fix (`configure-server/terragrunt.hcl`)

Changed `config_files` from a hardcoded list of specific packages to a glob:
```hcl
config_files = [
  for f in fileset("${include.root.locals.stack_root}/infra", "*/_config/*.yaml") :
  "${include.root.locals.stack_root}/infra/${f}"
  if !endswith(f, ".sops.yaml")
]
```
Any package config change now triggers configure-server re-run.

### UniFi CSRF fix (clear-excluded-refs.py, clear-port-overrides.py)

Both scripts were extracting CSRF tokens by decoding the JWT `TOKEN` cookie, which
broke with `IndexError: list index out of range` when the cookie wasn't a JWT.
Fixed to use `x-updated-csrf-token` response header from the login call (same approach
as `query-unifi-switch`). Also extended `clear-excluded-refs.py` to auto-clear client
fixed IPs instead of failing with exit 1.

### MaaS commission script fix (`trigger-commission.sh`)

Root cause of commissioning failure: `commissioning_scripts=none` is an INVALID MaaS API
parameter (`Select a valid choice. none is not one of the available choices`). The script
silently swallowed the API error (used `_ssh_run` with `|| true`), then misleadingly logged
"Commission triggered (current: New)".

Fixes:
1. Removed invalid `commissioning_scripts=none`; kept valid `testing_scripts=none`
2. Added `_ssh_run_strict` helper that checks for MaaS API error responses (JSON dict with
   array values) and exits 1 immediately
3. Changed WARNING to ERROR + exit 1 when machine status is not Commissioning 5s after
   commission command

### MaaS script silent failure improvements

Added exit code logging to `_ssh_run` in all 5 lifecycle scripts:
- `trigger-commission.sh`, `allocate-machine.sh`, `trigger-deploy.sh`
- `wait-for-ready.sh`, `wait-for-deployed.sh`

When `_ssh_run` swallows a non-zero SSH exit code, it now logs a WARNING. For critical
state-changing operations, the existing post-call status checks already catch failures; for
recovery operations (abort, interface reset), the WARNING is appropriately best-effort.

### Docs update (`machine-onboarding.md`)

Updated port profile references: `pxe_mgmt_public` → `amt_mgmt` for AMT NICs,
added description of `pxe_provisioning` for PXE NICs. Updated MEBx appendix to
reference `amt_mgmt` instead of old `management_only` name.

## Result

ms01-01 is now commissioning successfully (verified: MaaS status=Commissioning,
power_state=on, PXE boot events at 18:10-18:12 UTC, IP 10.0.12.x on VLAN 12).
