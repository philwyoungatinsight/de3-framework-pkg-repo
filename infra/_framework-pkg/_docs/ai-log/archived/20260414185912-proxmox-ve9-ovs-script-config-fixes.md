# Proxmox VE 9 Docs Update + OVS Script Provisioning-IP Fix

## Summary

Updated all Proxmox documentation and playbook comments from VE 8 to VE 9 following a
distro upgrade from Debian 12 (bookworm) to Debian 13 (trixie). Fixed the
`configure-plain-host-ovs` ai-only script to SSH via provisioning VLAN (using
`provisioning_ip` + MaaS jump box) instead of always targeting `cloud_public_ip`.
Added several missing config fields to `pwy-home-lab-pkg.yaml`.

## Changes

- **`infra/proxmox-pkg/_docs/README.md`** — updated all "VE 8" → "VE 9" references;
  clarified that bookworm→PVE 8 and trixie→PVE 9; updated machine table and Appendix A title

- **`infra/proxmox-pkg/_tg_scripts/proxmox/install/README.md`** — updated "VE 8" → "VE 9"
  in description, steps header, and config example comment

- **`infra/proxmox-pkg/_tg_scripts/proxmox/install/playbook.install-proxmox.yaml`** —
  updated header comment from bookworm/VE 8 to trixie/VE 9; updated reference URL

- **`scripts/ai-only-scripts/configure-plain-host-ovs/playbook.yaml`** — now prefers
  `provisioning_ip` over `cloud_public_ip` as SSH target when `provisioning_ip` is set;
  injects `-J ubuntu@<maas_server_ip>` jump box for provisioning VLAN targets (10.0.12.x
  is not directly routable); dynamically resolves MaaS server IP from parent config entry

- **`infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`** — added missing fields:
  - `amt_port: 16993` for ms01-01 and ms01-03 (was missing, defaulted incorrectly)
  - `provisioning_ip: 10.0.12.239` for ms01-02 (needed by configure-plain-hosts wave)
  - `deploy_osystem: ubuntu` for ms01-03 (needed by MaaS deployment logic)
  - Updated ms01-02 `_unit_purpose` to mention provisioning IP

- **`infra/pwy-home-lab-pkg/_docs/maas-machines.md`** — expanded machine summary table
  with cloud_public NIC, connection type, switch/port, and provisioning NIC columns;
  updated ms01-01 from PVE 8 → PVE 9; updated build notes to reference the new
  `pxe.maas.configure-plain-hosts` wave instead of manual script steps

- **`CLAUDE.md`** — added `Planning (ai-plans)` convention: write plan to
  `docs/ai-plans/<task>.md` before non-trivial multi-file changes

## Notes

The OVS script fix ensures the script works immediately post-MaaS-deploy when machines
only have a VLAN 12 provisioning DHCP IP. Previously the script always targeted
`cloud_public_ip`, which is only reachable after OVS is configured — a chicken-and-egg
problem. The `provisioning_ip` field in YAML is the stable solution.
