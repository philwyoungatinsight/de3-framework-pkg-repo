# OVS: Debian distro fix, configure-plain-host-ovs script

## Summary

Fixed a Debian gap in `_configure-ovs-bridge.yaml` (Proxmox VE hosts run Debian, not
Ubuntu — the distro guard would have hit the `fail` task). Created the
`configure-plain-host-ovs` ai-only script for OVS on plain (non-Proxmox) managed hosts
(Ubuntu + Rocky/RHEL). Answered: neither ms01-02 nor ms01-03 uses Rocky Linux today.

## Changes

### Bug fix — Debian support in `_configure-ovs-bridge.yaml`

- **`infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/_configure-ovs-bridge.yaml`**
  - Added `"Debian"` to the supported distros list — Proxmox VE hosts are Debian GNU/Linux,
    not Ubuntu. Without this, the `ansible_distribution not in [...]` guard would fail on
    all real Proxmox nodes.
  - Combined the Ubuntu and Debian install steps into a single `"Install OpenVSwitch packages
    (Debian/Ubuntu)"` task (`when: ansible_distribution in ["Debian", "Ubuntu"]`) — same
    package names on both (`openvswitch-switch` + `openvswitch-common`).
  - Updated header comment and `fail` message to list Debian.

### New script — `configure-plain-host-ovs`

- **`scripts/ai-only-scripts/configure-plain-host-ovs/run`** — bash entry point.
  `MACHINE=ms01-03 ./run`. Requires `MACHINE` env var; fails clearly if absent.

- **`scripts/ai-only-scripts/configure-plain-host-ovs/playbook.yaml`** — two-play Ansible:

  **Play 1 (localhost)**: loads `config_base` (sets `_tg_providers`), finds the target
  machine entry in `_tg_providers.maas.config_params` by matching `'/machines/<name>'`
  in the path, extracts `bridges:` filtered to `technology: ovs`, adds the machine's
  `cloud_public_ip` as a dynamic host.

  **Play 2 (target host)**: becomes root, gathers distribution facts, installs OVS:
  - Debian/Ubuntu: `apt install openvswitch-switch openvswitch-common`
  - Rocky: `dnf install epel-release && dnf install openvswitch`
  - RHEL: CRB repo enable → EPEL via direct RPM URL → `dnf install openvswitch`;
    also enables and starts the `openvswitch` systemd service (needed on EL distros).
  - Other: `fail` with instructions.

  Creates OVS bridge with `ovs-vsctl --may-exist add-br` + `add-port` (when nic set).
  Persists IP assignment per distro:
  - **Ubuntu/Debian**: writes `/etc/netplan/60-ovs-bridges.yaml` with `openvswitch: {}`
    and `addresses:/routes:` under the bridge entry; runs `netplan apply`.
  - **Rocky/RHEL**: creates nmcli connections in sequence:
    `ovs-bridge` → `ovs-port` (for bridge) → `ovs-interface` (host IP endpoint) →
    `ovs-port` + `ethernet` (for physical NIC if set). Uses `args: creates:` for
    idempotency (skips if connection file already exists).

  Verifies all configured bridge names appear in `ovs-vsctl list-br`.

### Rocky Linux on ms01-02/ms01-03 — not yet possible

Neither machine uses Rocky Linux today (both are `deploy_distro: noble`). Rocky Linux
deployment via MaaS requires:
1. A Packer build to produce a MaaS-compatible `.tar.gz` image (the build script
   `infra/image-maker-pkg/_tg_scripts/image-maker/build-images/packer/rocky-9.pkr.hcl`
   exists but produces a Proxmox template, not a MaaS image).
2. Import that image into MaaS as a custom boot resource
   (`maas maas-admin boot-resources create name=rocky/9 ...`).

This pipeline is documented in a `debug: msg` warning in `import-maas-images.yaml` but
not yet automated. To run the Rocky OVS validation path, the MaaS Rocky image work must
be done first (separate task).
