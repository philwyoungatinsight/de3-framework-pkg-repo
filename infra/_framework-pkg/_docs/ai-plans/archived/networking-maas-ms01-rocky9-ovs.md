# Plan: Deploy ms01-02 (Rocky 9) + ms01-03 (Ubuntu) via MaaS with OVS + MikroTik

**Date**: 2026-04-14  
**Status**: READY TO EXECUTE

---

## Context

The previous session completed the automation foundations:

| Area | Status |
|---|---|
| Rocky 9 MaaS image import pipeline (`import-rocky-image.yaml`) | ✅ done |
| Rocky 9 curtin preseed (`curtin_userdata_rocky9.j2`) | ✅ done |
| `pxe.maas.configure-plain-hosts` wave + playbook | ✅ done |
| MikroTik CRS317 on RouterOS 7.22.1 + Terraform `apis://` | ✅ done |
| ms01-02 config: `deploy_distro: rocky-9`, `cloud_init_user: rocky` | ✅ done |
| ms01-03 config: `deploy_distro: noble`, `deploy_osystem: ubuntu` | ✅ done |
| Both machines `_skip_on_build: false` | ✅ done |
| Wave ordering includes `pxe.maas.configure-plain-hosts` | ✅ done |
| MikroTik ports sfpplus3 (ms01-02) and sfpplus4 (ms01-03) configured | ✅ done |
| DHCP reservations for ms01-02 (10.0.12.239) and ms01-03 (10.0.12.238) | ✅ done |
| `bridges[0].nic` filled in for ms01-02 (`enp2s0f0np0`) | ✅ done |
| `bridges[0].nic` tentatively set for ms01-03 (`enp2s0f0np0`, same HW) | ✅ done |
| YAML parse error in `_unit_purpose` for configure-plain-hosts fixed | ✅ done |
| ms01-02 AMT tech-debt entry removed (AMT confirmed working) | ✅ done |

---

## Current Infrastructure State (2026-04-14)

**ms01-02**: Running Ubuntu 24.04 from a prior deploy at 10.0.12.238 (NOT Rocky 9 — needs redeployment). Not currently registered in MaaS. AMT at 10.0.11.11 is working.

- 10G NIC `enp2s0f0np0`: 10Gbps, link UP, MAC `38:05:25:31:81:0e` → CRS317 sfpplus3 ✓
- Provisioning NIC `enp87s0`: 2.5Gbps, MAC `38:05:25:31:81:10` → UniFi switch

**ms01-03**: Not deployed. Not registered in MaaS.

**MaaS machine list**: Empty — both ms01-02 and ms01-03 need to be enrolled and deployed from scratch. ms01-01 and nuc-1 status unknown (likely also not in MaaS).

---

## Execution Steps

### Phase 1: Run configure-region (imports Rocky 9 image + preseed + DHCP reservations)

The Rocky 9 image import pipeline, preseed deployment, and DHCP reservations for ms01-02/ms01-03 must all be applied before the lifecycle waves run.

```bash
source set_env.sh
cd infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/maas/configure-region
terragrunt apply
```

Watch for:
- `custom/rocky-9` boot resource reaching `Uploaded` state
- `curtin_userdata_custom_amd64_generic_rocky-9` preseed written to MaaS snap rev dir
- DHCP reservations: `ms01-02-pxe → 10.0.12.239`, `ms01-03-pxe → 10.0.12.238`

### Phase 2: Run MaaS lifecycle waves

Run waves in order. Use the wave runner (`./run --build` with wave filter or run individually):

```
maas.lifecycle.new          → creates ms01-02/ms01-03 machine records in MaaS
maas.lifecycle.commissioning → PXE-boots machines, discovers hardware
maas.lifecycle.ready         → waits for Ready state
maas.lifecycle.allocated     → allocates machines for deployment
maas.lifecycle.deploying     → triggers OS install (Rocky 9 for ms01-02, Ubuntu for ms01-03)
maas.lifecycle.deployed      → polls until Deployed + SSH verify
pxe.maas.configure-plain-hosts → OVS bridge setup (runs automatically after deployed)
```

**For ms01-02** (AMT at 10.0.11.11): MaaS will use AMT to power on/off the machine.
The old Ubuntu install will be wiped by MaaS curtin when the Rocky 9 image is DD'd.

**ms01-02 Rocky 9 deploy flow**:
1. MaaS powers on via AMT
2. Machine PXE-boots into commissioning environment (Ubuntu ephemeral)
3. MaaS discovers hardware (NICs, disks, CPUs)
4. Machine goes Ready → Allocated → Deploying
5. Curtin downloads `custom/rocky-9` ddgz, DD's to disk
6. `curtin_userdata_custom_amd64_generic_rocky-9` preseed runs: mounts EFI, reinstalls
   GRUB2 --removable, writes fstab, copies SSH keys, sets datasource to MAAS
7. Machine boots Rocky 9, cloud-init runs (MAAS datasource injects SSH key)
8. Machine reaches Deployed state

### Phase 3: configure-plain-hosts wave applies OVS automatically

The `pxe.maas.configure-plain-hosts` wave triggers automatically (it depends on
`ms01-02.deployed_at` and `ms01-03.deployed_at`). The playbook:

1. SSHes to ms01-02 via `rocky@10.0.12.239` (jump: `ubuntu@10.0.10.11`)
2. Installs EPEL + openvswitch on Rocky 9
3. Creates OVS bridge `ovs0` with uplink `enp2s0f0np0`
4. Creates nmcli connections: `ovs-bridge-ovs0`, `ovs-port-ovs0`, `ovs-iface-ovs0-host`
   (static IP `10.0.10.117/24`, gateway `10.0.10.1`)
5. Adds physical NIC connection: `ovs-port-enp2s0f0np0`, `ovs-eth-enp2s0f0np0`
6. Verifies via `ovs-vsctl list-br`

Same process for ms01-03 via `ubuntu@10.0.12.238` (netplan instead of nmcli).

### Phase 4: Verify end-to-end

After configure-plain-hosts completes:

```bash
ping 10.0.10.117    # ms01-02 cloud_public (via OVS, CRS317 sfpplus3)
ping 10.0.10.118    # ms01-03 cloud_public (via OVS, CRS317 sfpplus4)
ssh rocky@10.0.10.117 "ovs-vsctl list-br; ip addr show ovs0"
ssh ubuntu@10.0.10.118 "ovs-vsctl list-br; ip addr show ovs0"
```

---

## Files Modified (this session)

| File | Change |
|---|---|
| `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` | Add DHCP reservations ms01-02-pxe + ms01-03-pxe |
| `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` | Set `bridges[0].nic: enp2s0f0np0` for ms01-02 (confirmed) and ms01-03 (inferred) |
| `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` | Fix `_unit_purpose` YAML parse error (unquoted colon in configure-plain-hosts) |
| `docs/idempotence-and-tech-debt.md` | Remove ms01-02 AMT TLS tech-debt entry (AMT confirmed working) |

---

## Risks and Gotchas

### Rocky 9 GRUB boot after deploy
The curtin preseed (`curtin_userdata_rocky9.j2`) sets `GRUB_TIMEOUT=0` so the machine
boots immediately without waiting at the GRUB menu. This is critical for AMT-managed
machines that don't get a PXE one-shot override on reboot.

### ms01-03 NIC name unverified
`enp2s0f0np0` for ms01-03 is inferred from ms01-02 (same hardware). If it differs,
the `configure-plain-hosts` wave will create the OVS bridge without an uplink (it warns
rather than fails when `nic` doesn't exist). Verify with `ovs-vsctl list-br` and
`ip link show` after deploy. Update `bridges[0].nic` and re-run the wave if wrong.

### DHCP reservation timing
The reservations (`ms01-02-pxe`, `ms01-03-pxe`) must be in MaaS before the machines
try to PXE boot. configure-region must complete before commissioning starts.

### ms01-02 still alive on old IP
ms01-02 is running Ubuntu at 10.0.12.238 (and 10.0.12.239). Once MaaS commissions it,
AMT will power-cycle it and curtin will wipe the disk. The SSH connection to the old
Ubuntu install will break — this is expected.
