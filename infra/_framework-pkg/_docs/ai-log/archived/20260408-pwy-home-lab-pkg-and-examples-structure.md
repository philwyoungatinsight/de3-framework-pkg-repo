# 2026-04-08 pwy-home-lab-pkg + examples structure

## Summary

Introduced a deployment-package / example-code separation across all infra packages.
Created `infra/pwy-home-lab-pkg/` as the canonical pwy-homelab deployment package.

## Design

- `infra/<pkg>/_stack/<provider>/examples/<top>/` — example/template units, skipped by default
- `infra/pwy-home-lab-pkg/_stack/<provider>/<top>/` — actual deployment units

The `skip: true` parameter in config_params is inherited by all units under the examples
subtree via the existing ancestor-merge mechanism. Changing it to `false` (or removing it)
allows examples to be run directly — useful for testing the example code.

## Skip mechanism

In each package's `_config/config.yaml`, a config_params entry at the top of the examples
subtree carries `skip: true`:

```yaml
proxmox-pkg/_stack/proxmox/examples:
  skip: true
```

root.hcl already checks `_unit_skip = try(local.unit_params.skip, false)` and excludes the
unit when true. No root.hcl path-detection logic was added.

## root.hcl change: `_tg_scripts_dir` / `_wave_scripts_dir`

Added config_params override support so deployment packages can point at canonical package
scripts without copying them:

```hcl
_tg_scripts   = "${local.stack_root}/infra/${try(local.unit_params._tg_scripts_dir, "${local.p_package}/_tg_scripts")}"
_wave_scripts = "${local.stack_root}/infra/${try(local.unit_params._wave_scripts_dir, "${local.p_package}/_wave_scripts")}"
```

`pwy-home-lab-pkg/_config/config.yaml` sets `_tg_scripts_dir` at each provider subtree:
- `proxmox` units → `proxmox-pkg/_tg_scripts`
- `null/pwy-homelab/proxmox` → `proxmox-pkg/_tg_scripts`
- `null/pwy-homelab/maas` → `maas-pkg/_tg_scripts`
- `null/pwy-homelab/mesh-central` → `mesh-central-pkg/_tg_scripts`
- `null/pwy-homelab/local` → `default-pkg/_tg_scripts`
- `null/pwy-homelab/configure-physical-machines` → `maas-pkg/_tg_scripts`
- `maas` units → `maas-pkg/_tg_scripts`
- `gcp` units → `gcp-pkg/_tg_scripts`
- `unifi` units → `unifi-pkg/_tg_scripts`

## Units moved to examples

| Package | Moved |
|---------|-------|
| proxmox-pkg | `null/pwy-homelab` → `null/examples/pwy-homelab`; `proxmox/pwy-homelab` → `proxmox/examples/pwy-homelab` |
| maas-pkg | `maas/pwy-homelab` → `maas/examples/pwy-homelab`; `null/pwy-homelab` → `null/examples/pwy-homelab` |
| gcp-pkg | `gcp/us-central1` → `gcp/examples/us-central1` |
| image-maker-pkg | `proxmox/pwy-homelab` → `proxmox/examples/pwy-homelab` |
| mesh-central-pkg | `null/pwy-homelab` → `null/examples/pwy-homelab` |
| unifi-pkg | `unifi/pwy-homelab` → `unifi/examples/pwy-homelab` |
| default-pkg | `null/pwy-homelab` → `null/examples/pwy-homelab` |
| aws-pkg | `aws/us-east-1` → `aws/examples/us-east-1` |
| azure-pkg | `azure/eastus` → `azure/examples/eastus` |
| demo-buckets-example-pkg | both providers |

Cross-package dependency paths in examples updated to include `examples/` (3 files:
`_proxmox_deps.hcl`, `_maas_deps.hcl`, `configure-server/terragrunt.hcl`).

## pwy-home-lab-pkg

Created at `infra/pwy-home-lab-pkg/` with:
- `_config/config.yaml` — top key `pwy-home-lab-pkg:`; provider configs (proxmox, null, maas,
  gcp, unifi, aws, azure) with all config_params keyed at `pwy-home-lab-pkg/_stack/...`
- No secrets file yet — create with `sops --encrypt --output` when needed
- `_stack/` populated by merging units from all package examples:
  - `null/pwy-homelab/` — proxmox install/configure, maas configure-server/sync-api-key/
    configure-physical-machines, mesh-central configure/update, local update-ssh-config
  - `proxmox/pwy-homelab/` — pve-1/pve-2/ms01-01 isos/snippets/VMs + image-maker
  - `maas/pwy-homelab/machines/` — ms01-01, ms01-02, ms01-03, nuc-1, pxe-test-vm-1
  - `gcp/us-central1/` — GKE cluster, buckets
  - `unifi/pwy-homelab/` — device, network, port-profile
  - `aws/us-east-1/` and `azure/eastus/` — test buckets

Internal dependency files (`_proxmox_deps.hcl`, `_maas_deps.hcl`, `configure-server`)
updated to reference `pwy-home-lab-pkg/_stack/...` paths.

## Future: provider config inheritance

Currently pwy-home-lab-pkg holds complete provider configs (endpoint, credentials structure).
Later, the package-level provider config may be inherited from canonical packages and only
deployment-specific overrides (passwords, endpoints) stored in the deployment package —
consistent with the user's note about "commenting out the provider config."
