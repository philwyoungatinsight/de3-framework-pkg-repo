# pxe.maas.configure-plain-hosts — New Wave for OVS Automation

**Date:** 2026-04-14  
**Context:** Plain managed hosts (ms01-02 Rocky 9, ms01-03 Ubuntu 24.04) need OVS bridges
configured post-MaaS-deploy. Previously done by the ad-hoc ai-only script
`configure-plain-host-ovs` (run manually after deploy). This adds a proper automation wave.

---

## Problem

OVS bridge configuration was the only remaining manual step after `maas.lifecycle.deployed`
completed. The ai-only script required:
1. Manual `MACHINE=ms01-02 scripts/ai-only-scripts/configure-plain-host-ovs/run` invocation
2. Knowing when MaaS deployment finished
3. Repeating for each plain host

This broke the "make clean && make restores everything automatically" contract.

---

## Solution: New Wave `pxe.maas.configure-plain-hosts`

Inserted between `maas.lifecycle.deployed` and `pxe.maas.machine-entries` in `waves_ordering.yaml`.
Marked `skip_on_clean: true` because OVS state lives on the hosts — Terraform destroy of this
unit does not undo the bridge config, and re-deploying the host via MaaS wipes it anyway.

### Files created/modified

| File | Change |
|------|--------|
| `config/waves_ordering.yaml` | Insert `pxe.maas.configure-plain-hosts` after `maas.lifecycle.deployed` |
| `infra/maas-pkg/_config/maas-pkg.yaml` | Add wave definition (`_skip_on_clean: true`, `test_action: reapply`) |
| `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/run` | tg-script (build/clean/deps/clean-all) |
| `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/ansible.cfg` | Ansible config (same as configure-machines) |
| `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/requirements.txt` | Python deps (jmespath) |
| `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/playbook.configure-plain-hosts.yaml` | Multi-machine OVS playbook |
| `infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/maas/configure-plain-hosts/terragrunt.hcl` | Terraform null unit |
| `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` | config_params entry for the unit |

### Playbook design

**Play 1 (localhost):** Reads config_base, iterates ALL `config_params` entries to find
machines with `bridges: [{technology: ovs}]`. Uses `provisioning_ip` + MaaS jump box as SSH
target (before OVS gives the machine its `cloud_public_ip`). Builds a dynamic `plain_hosts`
group via `add_host`. No hardcoded machine names.

**Play 2 (plain_hosts):** Distro-aware OVS configuration:
- Ubuntu: installs `openvswitch-switch`, writes `/etc/netplan/60-ovs-bridges.yaml`, applies
- Rocky/RHEL: installs EPEL + openvswitch, uses nmcli `ovs-bridge/ovs-port/ovs-interface`
  connections for persistent state
- Verification: `ovs-vsctl list-br` must contain all declared bridges

### Terraform deps

Depends on:
- `configure-region` — MaaS server up, config_params loaded
- `ms01-02/commission/ready/allocated/deploying/deployed` — host is deployed
- `ms01-03/commission/ready/allocated/deploying/deployed` — host is deployed

Trigger: `sha256(config + playbook files) + ms01-02.deployed_at + ms01-03.deployed_at`

### SSH via provisioning VLAN

Plain hosts are on `10.0.12.x` (DHCP, provisioning VLAN) immediately post-deploy.
`provisioning_ip` is set in YAML for ms01-02 (`10.0.12.239`) and ms01-03 (`10.0.12.238`).
The playbook uses `-J ubuntu@{maas_server_ip}` jump box for all provisioning-VLAN targets.
When the bridge is configured, `cloud_public_ip` becomes reachable — subsequent runs fall
through to the `cloud_public_ip` path (but `provisioning_ip` also still works).

---

## What To Run

To apply this wave on fresh machines:

```bash
# Destroy + re-run from the lifecycle waves onwards:
# (wave system handles sequencing — just re-run waves from maas.lifecycle.new or deployed)

# Or if machines are already deployed, run the new wave directly:
source set_env.sh
cd infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/maas/configure-plain-hosts
terragrunt apply
```

---

## Related Files

- `scripts/ai-only-scripts/configure-plain-host-ovs/` — superseded (kept for manual emergency use)
- `infra/pwy-home-lab-pkg/_docs/maas-machines.md` — machine reference doc (updated in same session)
- `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/templates/curtin_userdata_rocky9.j2` — Rocky preseed (also added in this session)
