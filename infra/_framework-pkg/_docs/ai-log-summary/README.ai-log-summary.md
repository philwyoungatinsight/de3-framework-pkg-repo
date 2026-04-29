# Goal
- Keep a compacted version of the ai-logs that reflects the current state of the code.
- Individual ai-log files are deleted after their content is consolidated here.
- Git history has the full change record; this file captures current-state facts and
  non-obvious decisions that aren't obvious from reading the code.

# Action
- When significant work is done, add a reverse-chronological entry to `ai-log-summary.md`.
- Periodically update the Current State Summary below to reflect the real current state.
- Delete individual ai-log files once summarized.

---

# Current State Summary (as of 2026-04-10)

## Safety Rules Established

### SOPS Secrets File
Never use shell redirects, Write, or Edit tools on `.sops.yaml` files.
- `sops --set` for single-key updates (atomic, in-place)
- `sops "$SOPS_FILE"` for interactive full-file edits
- Creating from scratch: `EDITOR="cp /tmp/plain.yaml" sops "$SOPS_FILE"` — sops edit mode
  uses the target path for rule matching, so the `.sops.yaml` path_regex applies correctly.
  (`sops --encrypt --output` fails when input is in `/tmp` because path_regex matches input path.)

### SOPS config location
- Root `.sops.yaml` is the single source of truth for all encryption rules
- `config/.sops.yaml` is a symlink to `../.sops.yaml`
- path_regex: `.*infra/[^/]+/_config/.*\.sops\.yaml$` — matches all package secrets
- No `encrypted_regex` — all values encrypted by default

### Network Service Rule
Never `state: stopped` on systemd-networkd (or any service managing an active NIC) over SSH.
Stopping networkd releases the DHCP lease and drops the SSH connection.
Fix: `masked: true` (mask only) + reboot.

## Repository Structure

```
pwy-home-lab/           ← repo root = stack root (no deploy/ wrapper)
  .sops.yaml            ← SOPS creation rules for all infra/<pkg>/_config/*.sops.yaml files
  set_env.sh            ← sources all path vars; source before any terragrunt/ansible command
  root.hcl              ← stack root HCL; derives p_package/p_tf_provider from path
  run                   ← main build/clean orchestrator
  Makefile
  config/               ← real directory; config/.sops.yaml is a symlink to ../.sops.yaml
  utilities/            ← real directory (not symlink); git-tracked
    bash/               ← init.sh, framework-utils.sh, python-utils.sh
    ansible/roles/      ← config_base role (used by all playbooks)
  infra/<pkg>/          ← self-contained packages (see Package System below)
  framework/            ← stack-wide config, generate-ansible-inventory
  scripts/
    ai-only-scripts/    ← AI-generated one-off scripts
    human-only-scripts/ ← manually-invoked utilities (gpg, sops, kubeconfig, converters)
  docs/
    ai-log-summary/     ← this file + consolidated log
    framework/          ← architecture docs
```

## Package System — Current Architecture

All infrastructure is organized into self-contained packages under `infra/<pkg>/`.
`p_package` (from `unit_params._package`, default `"_framework-pkg"`) controls module,
provider template, and script paths.

### Directory layout per package

```
infra/<pkg>/
  _stack/<provider>/<path...>/<leaf-unit>/  ← terragrunt units
  _modules/<provider>/<pkg>/<module>/       ← Terraform modules
  _providers/<provider>.tpl                 ← provider connection template
  _tg_scripts/<role>/<name>/run             ← Terragrunt hook scripts
  _wave_scripts/test-ansible-playbooks/<role>/<name>/  ← wave test playbooks
  _config/<pkg>.yaml                        ← per-package config YAML (top-level key: <pkg>:)
  _config/<pkg>_secrets.sops.yaml           ← per-package secrets (top-level key: <pkg>_secrets:)
  _setup/run                                ← OS-level tool installation
  _docs/                                    ← package documentation (no README at package root)
  _clean_all/run                            ← optional pre-destroy purge script
```

### Provider template lookup (3-tier)
1. `_providers/<p_package>/<provider>.tpl` — unit's own package
2. `_providers/<provider>-pkg/<provider>.tpl` — canonical provider package
3. `_providers/_framework-pkg/<provider>.tpl` — last resort (null only)

Same 3-tier for `.entry.tpl` files (`_extra_providers`).

### Current packages

| Package | Owns |
|---|---|
| `_framework-pkg` | null provider; local update scripts; generate-inventory |
| `aws-pkg` | AWS provider template, S3 modules |
| `azure-pkg` | Azure provider template, Blob/Container modules |
| `gcp-pkg` | GCP provider template, GCS + GKE modules |
| `maas-pkg` | MaaS provider template, maas_machine module, configure-server, tg-scripts |
| `proxmox-pkg` | Proxmox provider template, VM/ISO/file modules, tg-scripts |
| `unifi-pkg` | UniFi provider template, network/port-profile/device modules |
| `image-maker-pkg` | Image-maker VM + Packer build scripts |
| `mesh-central-pkg` | MeshCentral VM + configure scripts |
| `demo-buckets-example-pkg` | Config-coordinator only (no modules/templates) |

### Config YAML convention

Every config file is named after the top-level key it contains:
- `infra/<pkg>/_config/<pkg>.yaml` — top-level key: `<pkg>:`
- `infra/<pkg>/_config/<pkg>_secrets.sops.yaml` — top-level key: `<pkg>_secrets:`
- Component configs in any `_config/` dir: `<key>.yaml` / `<key>_secrets.sops.yaml`

`_find_component_config <key>` searches `$_INFRA_DIR/*/_config/<key>.yaml` (or `.sops.yaml`).
Files can be moved to any package's `_config/` without code changes.

`merge-stack-config.py` and `run` discover configs by iterating `infra/*/` dirs and loading
`_config/<dirname>.yaml` — no glob on `config.yaml` any more.

Adding a new package = add `infra/<pkg>/_config/<pkg>.yaml`; no changes to `root.hcl`.

### Package variable interpolation

`vars:` section in package YAMLs supports `${varname}` (local) and `${pkg-name.varname}`
(cross-package) string interpolation, resolved in `merge-stack-config.py` before merge.

### `_extra_providers` mechanism
Units can declare secondary provider plugins: `_extra_providers: ["null"]`.
`root.hcl` injects entry templates into `required_providers {}`. YAML reserved words must be quoted.

### Dynamic provider aggregation
`config_base` role provides `_tg_providers` and `_tg_providers_secrets` — dynamically
aggregated across all packages. Ansible playbooks use these instead of hardcoded package
variable names; new packages are auto-discovered.

## Infrastructure Facts

- **MaaS server:** 10.0.10.11 (static), VLAN 10; rack controller at 10.0.12.2
- **Provisioning subnet:** 10.0.12.0/24 (VLAN 12) — not directly routable; use MaaS server as SSH jump host
- **pve-1:** 10.0.10.115 — externally provisioned (`node_name: pve`, `datastore_vm: local-zfs`)
- **pve-2:** 10.0.10.200 — externally provisioned (`node_name: pve-2`, `datastore_vm: local-zfs`)
- **ms01-01:** MaaS-deployed (trixie), `cloud_public_ip: 10.0.10.116`, Proxmox installed by tg-script
- **Physical machines:** ms01-01/02/03 — `power_type: amt`; nuc-1 — `power_type: smart_plug (kasa)`; `release_erase: true`
- **AMT IPs:** ms01-01 → 10.0.11.10, ms01-02 → 10.0.11.11, ms01-03 → 10.0.11.12 (port 16993, management VLAN 11)
- **AMT VLAN note:** switch port (management_only profile, native VLAN 11) provides untagged traffic; AMT MEBx must have VLAN disabled (tag=0)
- **State backend:** GCS bucket `seed-tf-state-pwy-homelab-20260308-1700`
- **Stale lock:** `gsutil rm gs://seed-tf-state-pwy-homelab-20260308-1700/<path>/default.tflock`

## VM Directory Structure

VMs under `infra/proxmox-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-{1,2}/vms/`:
- `vms/utils/` — infrastructure VMs: maas-server-1, mesh-central, image-maker, pxe-test-vm-1
- `vms/test/` — test/lab VMs: all test-* VMs

## Waves — Current List (ordered)

Category ordering: `cloud → util → network → hw → pxe → hypervisor → vm → service → local`

| Wave | Description |
|---|---|
| `cloud.storage` | S3, GCS, Azure Blob buckets |
| `cloud.k8s` | GKE cluster + kubeconfig |
| `network.unifi` | VLANs, port profiles, switch config |
| `network.unifi.validate-config` | Pure-test wave: validates VLAN/port/device config via UniFi API (87 checks) |
| `hw.storage` | Externally-managed storage |
| `hw.power` | OOB power management verification |
| `hw.servers` | pve-1 ISOs and snippets |
| `pxe.maas.server` | MaaS seed server VM + configure-server + sync-api-key |
| `pxe.maas.machines` | Physical machines via MaaS (ms01-01/02/03, nuc-1) |
| `hypervisor.proxmox.install` | Proxmox packages installed on MaaS-deployed nodes |
| `hypervisor.proxmox.configure` | Proxmox configured (API tokens, storage, networking) |
| `hypervisor.proxmox.storage` | ISOs and snippets provisioned |
| `pxe.maas.vms` | MaaS test VMs (pxe-test-vm-1) |
| `vm.mesh-central` | MeshCentral VM + configure |
| `vms.proxmox.from-web.ubuntu` | Ubuntu test VMs |
| `vms.proxmox.from-web.rocky` | Rocky Linux test VMs |
| `vms.proxmox.custom-images.image-maker` | Image-maker VM (builds Packer and Kairos images) |
| `vms.proxmox.from-packer` | Test VMs cloned from Packer templates |
| `vms.proxmox.from-kairos` | Test VMs from Kairos ISOs |
| `local.updates` | Regenerates Ansible inventory + writes `~/.ssh/conf.d/dynamic_ssh_config` |

## clean-all / run Behavior

- **Pre-apply unlock:** Stale `.tflock` GCS objects deleted before each wave apply
- **GCS state preservation:** Waves with `skip_on_clean_all: true` have GCS state preserved during Stage 3 wipe
- **GKE pre-purge:** `make clean-all` runs `gcloud container clusters delete` before Terraform destroy
- **`_FORCE_DELETE=YES`:** Skips the "Type DELETE" confirmation prompt

## MaaS Machine Automation

All five machines: ms01-01 (tmhaff), ms01-02 (4x63rt), ms01-03 (dkx7sn), nuc-1 (6rbdfr), pxe-test-vm-1 (mxt6ke).

Key behaviors:
- `_stale_os_wipe()`: wipes boot disk, removes non-PXE EFI entries, power off → PXE fallback
- `release_erase: true`: MaaS erases disk on destroy
- `maas_release_on_destroy`: null_resource destroy provisioner releases machine to Ready
- Smart-plug power via MaaS rack proxy at localhost:7050

## Proxmox

- pve-1/pve-2: externally provisioned, managed via API; VLAN-aware bridge (`vmbr0`)
- ms01-01: MaaS-deployed (trixie); Proxmox installed by `install-proxmox` tg-script
- API token format: `root@pam!tg-token` (full token ID), `privsep=0`
- Static IP conversion: vmbr0 DHCP → static during configure-linux-bridge (mask networkd + reboot)
- Cloud public VLAN: `vmbr0.10` created on hosts with `cloud_public_ip`

## Packer / Image-maker

- Ubuntu 24.04: GRUB `c` command, `autoinstall` on cmdline, cidata ISO for config
- Rocky 9: BIOS/SeaBIOS, OEMDRV CD kickstart, `iso_file` (not `boot_iso`)
- All ISOs pre-downloaded to Proxmox via `proxmox_virtual_environment_download_file`
- `proxmox_token_id` as username (full token ID), `proxmox_token_secret` as token
- Static route `10.0.12.0/24 via 10.0.10.11` on image-maker for Packer SSH to VLAN 12 VMs

## Path Conventions

- **Unit paths:** `<pkg>/_stack/<provider>/<env>/...` (no `cat-hmc` or `cat-N` prefix — fully removed)
- **Package docs:** `infra/<pkg>/_docs/` — all packages have this dir; no README at package root
- **Pre-destroy scripts:** `infra/<pkg>/_clean_all/run` (receives `_CLEAN_ALL_CONFIG_PARAMS` + `_CLEAN_ALL_SECRET_PARAMS` as JSON env vars)
- **`pre_destroy_order`** in `config/framework.yaml`: proxmox-pkg → gcp-pkg → unifi-pkg → maas-pkg

## Key Architecture Facts

- **root.hcl:** derives `p_package` from path (`infra/<pkg>/_stack/...`); `_ancestor_paths` starts from index 1
- **Provider detection:** `_provider_matches` requires exactly 1 provider with config_params matching unit ancestors
- **`project_prefix`:** read as `cloud_public.project_prefix` — no per-subtree override
- **`p_package`:** defaults to `"_framework-pkg"` — controls module, provider template, and script paths
- **Deterministic MACs:** hash of `_rel_path_full` (full untruncated path), NOT 63-char `_rel_path_label`
- **Ansible inventory:** `generate_ansible_inventory.py` auto-injects `-J ubuntu@{maas_server_ip}` for MaaS machines
- **SSH jump:** VLAN 12 (10.0.12.x) not directly routable; MaaS server (10.0.10.11) is jump host
- **ProxyCommand** (not `-J`): required for VLAN 12 to propagate `StrictHostKeyChecking=no`
