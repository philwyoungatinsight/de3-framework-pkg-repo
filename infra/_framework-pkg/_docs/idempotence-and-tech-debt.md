# Idempotence and Tech Debt

The goal is that `make clean-all && make` — given a working cloud seed account and any
pre-existing external servers — produces a fully working system with no manual intervention.
Code blocks and polls as needed to handle complex dependencies via the wave system.

Known gaps where manual steps are still required are tracked below.

---

## One-time Physical Prerequisites

**ms01-01/02/03 require AC power before Intel AMT automation can manage them**

Intel AMT (Active Management Technology) operates in standby mode and requires the machine
to have AC power connected. Without AC power, the AMT port (16993) is completely unreachable.

- AMT IP addresses: ms01-01=10.0.11.10, ms01-02=10.0.11.11, ms01-03=10.0.11.12 (VLAN 11)
- Without AC power: `nc -z -w3 <amt_ip> 16993` returns closed from MaaS server
- With AC power but machine off: `nc -z -w3 <amt_ip> 16993` succeeds — AMT is in standby
- The pre-wave precheck (maas.machine.config.power) verifies AMT reachability and fails fast if not reachable

**Action**: Ensure ms01-01/02/03 are physically connected to AC power before running
`make` or wave 10 (`maas.machine.config.power`). After first-time AMT/MEBx setup and
AC power is connected, `make clean-all && make` runs fully automatically.

---

## Active Tech Debt

**`make clean-all` does not destroy cloud.storage wave resources before wiping state**
`make clean-all` wipes the GCS state bucket but does NOT run `terraform destroy` on the
`cloud.storage` wave (AWS S3, Azure Blob, GCP GCS buckets). Those resources are orphaned
in the cloud with no state entry after the wipe, causing `BucketAlreadyExists` / 409 errors
on the next `make`.

Impacted units (as of 2026-04-09):
- `pwy-home-lab-pkg/_stack/aws/us-east-1/dev/test-bucket` — bucket `pwy-tg-stack-hmc-bucket`
- `pwy-home-lab-pkg/_stack/gcp/us-central1/dev/test-bucket` — bucket `tg-lab-stack-test-bucket`
- `pwy-home-lab-pkg/_stack/gcp/us-central1/dev/test-bucket-pwy-3` — bucket `tg-lab-stack-test-bucket-pwy-3`
- `pwy-home-lab-pkg/_stack/azure/eastus/dev/buckets/test-bucket-hmc-a` — RG `pwy-tg-stack-hmc-bucket-rg`, SA `pwytgstackhmcbkt`, container `test-bucket-hmc-a`
- `pwy-home-lab-pkg/_stack/azure/eastus/dev/buckets/test-bucket-hmc-a/all-config` — blob `all-config`

Manual recovery commands run on 2026-04-09 to unblock `make` (these should not be
necessary once the root cause is fixed):
```bash
cd /path/to/pwy-home-lab && source set_env.sh

# GCP
cd infra/pwy-home-lab-pkg/_stack/gcp/us-central1/dev/test-bucket
terragrunt import google_storage_bucket.this tg-lab-stack-test-bucket

cd ../test-bucket-pwy-3
terragrunt import google_storage_bucket.this tg-lab-stack-test-bucket-pwy-3

# AWS
cd ../../aws/us-east-1/dev/test-bucket   # relative from gcp path; adjust as needed
terragrunt import aws_s3_bucket.this pwy-tg-stack-hmc-bucket

# Azure
cd infra/pwy-home-lab-pkg/_stack/azure/eastus/dev/buckets/test-bucket-hmc-a
SUB=9539a5b9-872e-496a-9dbe-c59eb07ad428
terragrunt import azurerm_resource_group.this    /subscriptions/$SUB/resourceGroups/pwy-tg-stack-hmc-bucket-rg
terragrunt import azurerm_storage_account.this   /subscriptions/$SUB/resourceGroups/pwy-tg-stack-hmc-bucket-rg/providers/Microsoft.Storage/storageAccounts/pwytgstackhmcbkt
terragrunt import azurerm_storage_container.this https://pwytgstackhmcbkt.blob.core.windows.net/test-bucket-hmc-a

cd all-config
terragrunt import azurerm_storage_blob.this https://pwytgstackhmcbkt.blob.core.windows.net/test-bucket-hmc-a/all-config
```

Fix: add a pre-purge step in `run --clean-all` (alongside the existing Proxmox VM and GKE
cluster purge stages) that runs `terragrunt run --all destroy --non-interactive` for the
`cloud.storage` wave before wiping state. The wave should be listed in
`infra/_framework-pkg/_config/config.yaml` under a `pre_state_wipe_destroy_waves` key (or
similar), mirroring the existing Proxmox/GKE purge pattern.

**`make clean-all` does not destroy UniFi networks before wiping state**
The `network.unifi` wave has `_skip_on_wave_run: true` to protect the physical switch from
being wiped on `make clean`. However, `make clean-all` should override all skip flags
(`_FORCE_DELETE=YES`) but it currently does NOT destroy UniFi resources before wiping
state. After `make clean-all`, `make` fails with `api.err.VlanUsed (400)` for all VLANs.

Impacted unit: `pwy-home-lab-pkg/_stack/unifi/pwy-homelab/network` — all 5 VLANs.

Manual recovery commands run on 2026-04-09:
```bash
cd /path/to/pwy-home-lab && source set_env.sh
cd infra/pwy-home-lab-pkg/_stack/unifi/pwy-homelab/network

# VLAN IDs queried from UniFi controller at https://192.168.2.1
terragrunt import 'unifi_network.this["cloud_public"]' 69adf3aad53f2b819edd8601
terragrunt import 'unifi_network.this["management"]'   69adf3aad53f2b819edd8607
terragrunt import 'unifi_network.this["provisioning"]' 69d7d9d27f94d2d618524d93
terragrunt import 'unifi_network.this["guest"]'        69d7d9d17f94d2d618524d91
terragrunt import 'unifi_network.this["storage"]'      69d7d9d27f94d2d618524d95
# Note: UniFi controller rate-limits logins (429); wait ~15s between each import.
```

Fix: `make clean-all` should run `terragrunt run --all destroy` on `network.unifi` before
wiping the state bucket. The `_skip_on_wave_run` wave flag should not apply when
`_FORCE_DELETE=YES` is set.

**MeshCentral agent not supported on Rocky Linux 10**
The meshagent binary segfaults immediately on Rocky 10 (glibc 2.39+) with a crash in
`ILibParsers.c`. Rocky 9 (glibc 2.34) works fine. Rocky 10 hosts are explicitly skipped
during `update-mesh-central` with a warning.
Fix: wait for a MeshCentral release with a Rocky 10-compatible binary, then remove the
OS check from `infra/mesh-central-pkg/_tg_scripts/mesh-central/update/tasks/install-agent.yaml`.

**MaaS server IP referenced in two places**
`maas_server_ip` is set in `providers.maas.config_params` (for Terraform) and also
appears in `ansible_ssh_common_args` for VLAN-12 hosts (e.g. ms01-01's Proxmox node
entry in `providers.proxmox.config_params`). If the MaaS server IP changes, both
locations must be updated manually.

**`make clean` / `make clean-all` leaves stale SSH known_hosts entries for MaaS server**
After `make clean` or `make clean-all`, the MaaS server VM is destroyed and later
reprovisioned with a new host key. The developer's `~/.ssh/known_hosts` retains the old
key for `10.0.10.11` (the MaaS server static IP). On the next build, `commission-and-wait.sh`
SSH calls to the MaaS server fail with "REMOTE HOST IDENTIFICATION HAS CHANGED" even
though they use `StrictHostKeyChecking=no`, because that option does not bypass *changed*
keys that already exist in `known_hosts`.

Workaround applied: added `UserKnownHostsFile=/dev/null` to all `commission-and-wait.sh`
SSH calls so a stale key can never block commissioning again.

Remaining gap: `auto-import/run` (Python, calls `subprocess` ssh) and any other scripts
that SSH to `10.0.10.11` without `UserKnownHostsFile=/dev/null` can still be blocked.

Fix: add a step in `run --clean` and `run --clean-all` (after MaaS VM is destroyed) that
runs `ssh-keygen -R 10.0.10.11 -f ~/.ssh/known_hosts` to purge the stale entry
automatically. The MaaS server IP should be read from config, not hardcoded.

**MaaS-provisioned Proxmox node IP is DHCP-assigned**
ms01-01 gets its provisioning IP from MaaS DHCP on VLAN 12 (10.0.12.x). If MaaS
redeploys ms01-01 and assigns a different IP, `ansible_host` in `pwy-home-lab-pkg.yaml`
must be updated manually in `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`.
Mitigation: add a static DHCP reservation in MaaS for ms01-01's MAC address
(`38:05:25:31:2f:a3`) via the MaaS web UI → Subnet → Reserved ranges.

---

## Resolved

- Proxmox VE installation and configuration on MaaS-provisioned hosts
  (`install-proxmox` + `configure-proxmox` fully automated as of 2026-03-15).

---

## MikroTik CRS317 Bootstrap — Endpoint Swap After First Apply

**Status**: Tracked. One-time manual config change required after initial `network.mikrotik` wave.

**What**: The CRS317 ships with factory default IP `192.168.88.1`. The first Terraform apply
must target this address (direct laptop RJ45 connection). After apply, the switch gains
management IP `10.0.11.5` on VLAN 11. The config must then be updated to target `10.0.11.5`
so ongoing applies reach the switch over the lab network.

**Current transport**: `apis://` (ROS API-SSL, port 8729, TLS). Switch is on RouterOS 7.22.1.

**Manual step (after first apply)**:
1. Verify `ping 10.0.11.5` succeeds (switch reachable on VLAN 11 via network).
2. In `infra/mikrotik-pkg/_config/mikrotik-pkg.yaml`, update:
   ```yaml
   _provider_routeros_endpoint: "apis://10.0.11.5:8729"
   ```
3. Re-run `terragrunt apply` in the crs317-pwy-homelab unit (idempotent).
4. Disconnect laptop RJ45 from CRS317.

**Why not automated**: RouterOS cannot provide connectivity to `10.0.11.5` before Terraform
configures it. A chicken-and-egg dependency that requires a one-time address change.

**Future**: A pre-apply hook could detect whether `192.168.88.1` or `10.0.11.5` is reachable
and set the endpoint accordingly. Not worth the complexity for a one-time operation.

---

## MikroTik CRS317 — Admin Password Not Managed by Terraform

**Status**: Tracked. Password set manually; Terraform does not rotate it.

**What**: The `_provider_routeros_password` in SOPS is used by the provider to connect, but
no `routeros_user` Terraform resource manages the admin password lifecycle. If the password
is changed manually, the SOPS secret must be updated by hand.

**Manual step**: To change the admin password, SSH to the switch and run:
```
/user set [find name=admin] password="<new-password>"
```
Then update the SOPS secret:
```bash
sops --set '["mikrotik-pkg_secrets"]["config_params"]["mikrotik-pkg/_stack/routeros/pwy-homelab"]["_provider_routeros_password"] "<new-password>"' \
  infra/mikrotik-pkg/_config/mikrotik-pkg_secrets.sops.yaml
```

**Future**: Add a `routeros_user` resource to the `routeros_switch` module to manage password rotation.

---

