# Populate _unit_purpose for all units

## What

Added `_unit_purpose` to every `config_params` entry across all packages —
112 total entries (59 in pwy-home-lab-pkg, 35 in proxmox-pkg, 8 in maas-pkg,
3 in mesh-central-pkg, 1 in image-maker-pkg, 6 in gcp-pkg).

This is phases 2–4 of the rollout plan documented in `docs/framework/unit_params.md`.

## Files changed

| File | Count |
|------|-------|
| `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` | 59 entries |
| `infra/proxmox-pkg/_config/proxmox-pkg.yaml` | 35 entries |
| `infra/maas-pkg/_config/maas-pkg.yaml` | 8 entries |
| `infra/mesh-central-pkg/_config/mesh-central-pkg.yaml` | 3 entries |
| `infra/image-maker-pkg/_config/image-maker-pkg.yaml` | 1 entry |
| `infra/gcp-pkg/_config/gcp-pkg.yaml` | 6 entries |

Two new `config_params` entries were also added (no prior entry existed):
- `proxmox-pkg/_stack/null/examples/pwy-homelab/proxmox/install-proxmox`
- `proxmox-pkg/_stack/null/examples/pwy-homelab/proxmox/wait-for-proxmox`

One new entry added to pwy-home-lab-pkg:
- `pwy-home-lab-pkg/_stack/null/pwy-homelab/local/update-ssh-config`

## What each purpose string captures

- **Proxmox node ancestors** (`pve-1`, `pve-2`, `ms01-01`): hardware description, IP, node_name, which VMs live there
- **ISOs / snippets**: what image is uploaded and why it exists
- **VMs** (utility + test): role in the lab, hosting node, networking (static vs DHCP)
- **MaaS machines**: hardware type, power driver (Kasa/Proxmox/AMT), VLAN assignments, post-deploy role
- **Null orchestration units**: already done in phase 1; confirmed correct
- **GCP resources**: cluster, kubeconfig writer, test buckets — scoped to dev/demo use
- **UniFi units**: what each unit manages (VLAN network, port profiles, APs)
- **AWS / Azure**: test buckets, dev-only resources

## Implementation notes

Used a text-based insertion script (`/tmp/add_unit_purposes.py`) to avoid YAML
reformatting. A follow-up quoting pass wrapped values containing `: ` in single
quotes (bare scalars with colon-space are invalid in YAML).

Two paths not found in proxmox-pkg (no entries expected):
- `pve-1/isos/ubuntu-22` (only exists in pve-2 in proxmox-pkg)
- `pve-1/vms/utils/mesh-central` (lives in mesh-central-pkg, not proxmox-pkg)
