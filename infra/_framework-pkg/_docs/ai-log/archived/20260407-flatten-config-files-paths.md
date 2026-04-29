# 2026-04-07 Flatten config/files/ paths

## Summary

Eliminated the `platform-config/terragrunt/terragrunt_lab_stack/` intermediate path.
Config files now live directly under `config/files/`.

## New structure

```
config/files/
  terragrunt_lab_stack/   ← main stack config (was platform-config/terragrunt/terragrunt_lab_stack/)
  aws-pkg/                ← peer dirs (were subdirs of terragrunt_lab_stack/)
  azure-pkg/
  demo-buckets-example-pkg/
  gcp-pkg/
  image-maker-pkg/
  maas-pkg/
  mesh-central-pkg/
  proxmox-pkg/
  unifi-pkg/
  platform-config/        ← kept for non-terragrunt config (dev_workstation, platform_secrets)
```

`_CONFIG_DIR` unchanged (`$GIT_ROOT/config/files`).

## Code changes

- `framework/lib/merge-stack-config.py`: rglob from `config_dir` directly for
  `terragrunt_lab_stack*.yaml` (was `config_dir/platform-config/terragrunt`)
- `framework/generate-ansible-inventory/generate_ansible_inventory.py`: path to
  `terragrunt_lab_stack.yaml` updated
- `framework/clean-all/run`: fallback rglob updated from `deploy/config/` to `config/files/`
- `infra/gcp-pkg/_tg_scripts/gke/kubeconfig/run`: `GCP_PKG_YAML` path updated
- `infra/gcp-pkg/_wave_scripts/.../gke-kubeconfig-test/playbook.yaml`: `tg_dir` updated
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`: SOPS path
- `infra/maas-pkg/_tg_scripts/maas/sync-api-key/playbook.yaml`: SOPS path
- `infra/mesh-central-pkg/_tg_scripts/mesh-central/install/run`: SOPS path
- `infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/configure-api-token.yaml`: SOPS path (×2)
- `scripts/ai-only-scripts/import-unifi-networks/playbook.yaml`: `tg_dir` updated
- `config/.sops.yaml`: `path_regex` updated from `.*platform-config.*` to `.*config/files/.*`
- `CLAUDE.md`: `SOPS_FILE` reference updated
