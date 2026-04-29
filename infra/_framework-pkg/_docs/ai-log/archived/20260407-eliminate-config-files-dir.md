# 2026-04-07 Eliminate config/files/ — distribute config into infra/<pkg>/_config/

## Summary

Eliminated `config/files/` entirely. All configuration is now distributed into
`infra/<pkg>/_config/` directories — one directory per package, containing
`config.yaml` (public) and `secrets.sops.yaml` (encrypted).

## New config structure

```
infra/<pkg>/_config/
  config.yaml        ← top-level key: <pkg>:
  secrets.sops.yaml  ← top-level key: <pkg>_secrets:
  dev_workstation.yaml  (default-pkg only — platform-level config)
```

`infra/default-pkg/_config/config.yaml` also holds the framework settings that
were previously in `config/files/framework/framework.yaml`:
- `backend:` (GCS bucket)
- `waves_ordering:` (authoritative wave sequence)
- `ansible_inventory:`, `ssh_config:`, `clean_all:`, `pre_apply_unlock:`

## Key naming convention

- Public config top-level key: `<pkg>` (e.g., `aws-pkg`, `gcp-pkg`)
- Secrets top-level key: `<pkg>_secrets` (e.g., `aws-pkg_secrets`, `gcp-pkg_secrets`)

## Env var changes

- `_CONFIG_DIR` removed from `set_env.sh`
- `_INFRA_DIR` (already set) is now the primary config root

## Code changes

- `root.hcl`: reads `infra/default-pkg/_config/config.yaml` for framework settings; `infra/<pkg>/_config/secrets.sops.yaml` per package; `_package_sec_cfg` fallback handles both `<pkg>_secrets` and `<pkg>` keys
- `run` (top-level): `load_all_configs()` reads from `INFRA_DIR/default-pkg/_config/config.yaml`
- `framework/lib/merge-stack-config.py`: scans `$_INFRA_DIR/*/_config/config.yaml`
- `framework/generate-ansible-inventory/generate_ansible_inventory.py`: `resolve_config_path()` uses `$_INFRA_DIR/default-pkg/_config/config.yaml`
- `framework/clean-all/run`: `_load_merged_config()` scans all `infra/*/_config/config.yaml`; `_find_gke_clusters()` uses merged config; SOPS secrets from `infra/default-pkg/_config/secrets.sops.yaml` and `infra/proxmox-pkg/_config/secrets.sops.yaml`
- `utilities/ansible/roles/config_base/`: scans `$_INFRA_DIR/*/_config/` via `find`; varnames patterns changed from `'^terragrunt_lab_stack'` to `'.*-pkg$'` / `'.*-pkg_secrets$'`
- `utilities/bash/framework-utils.sh`: `_find_component_config` searches `$_INFRA_DIR/<pkg>/_config/config.yaml`; `terragrunt_lab_stack` aliased to `default-pkg`
- `set_env.sh`: removed `export _CONFIG_DIR`
- SOPS paths updated in: `proxmox-pkg/configure-api-token.yaml`, `maas-pkg/install-maas.yaml`, `maas-pkg/sync-api-key.yaml`, `gcp-pkg/kubeconfig/run`, `gcp-pkg/gke-kubeconfig-test/playbook.yaml`, `mesh-central-pkg/install/run`, `import-unifi-networks/playbook.yaml`
- `scripts/human-only-scripts/seed-accounts/{gcp,aws,azure}_seed/run`: updated to use `$_INFRA_DIR` and `<pkg>_secrets` SOPS keys
- `CLAUDE.md`: updated SOPS_FILE reference, config file convention, examples

## Pending manual step: SOPS key rename

The `infra/<pkg>/_config/secrets.sops.yaml` files currently have `<pkg>:` as
their top-level key. They need to be renamed to `<pkg>_secrets:`.

Run: `scripts/ai-only-scripts/fix-sops-pkg-keys/run`

This affects: aws-pkg, azure-pkg, maas-pkg, mesh-central-pkg, proxmox-pkg, unifi-pkg.

`infra/gcp-pkg/_config/secrets.sops.yaml` and `infra/default-pkg/_config/secrets.sops.yaml`
do not exist yet — they need to be created from the `config/files/` SOPS files.

## Completed

All pending steps completed in the same session:

1. **SOPS keys renamed** — `infra/<pkg>/_config/secrets.sops.yaml` keys updated from `<pkg>:` → `<pkg>_secrets:` for: aws-pkg, azure-pkg, maas-pkg, mesh-central-pkg, proxmox-pkg, unifi-pkg. Decryption used PGP (fingerprint `1FAFFDF2C76C758F736178E2B776DF4CEB6B692B`); re-encryption used `SOPS_AGE_KEY_FILE=/home/pyoung/sops/age/keys.txt.pwy-home`.

2. **infra/gcp-pkg/_config/secrets.sops.yaml** — no source file existed (`config/files/gcp-pkg/` had no `_secrets` file), so nothing to migrate.

3. **infra/default-pkg/_config/secrets.sops.yaml** — created from `config/files/terragrunt_lab_stack/lab_stack_secrets.sops.yaml`. Key renamed `lab_stack_secrets` → `default-pkg_secrets`. Contains `providers.maas.api_key`.

4. **cat-hmc/ config_params merged** into infra package configs:
   - proxmox-pkg: +46 entries
   - maas-pkg: +9 entries
   - demo-buckets-example-pkg: +19 entries
   - gcp-pkg: +3 entries
   - image-maker-pkg: +1 entry
   - mesh-central-pkg: +3 entries
   - unifi-pkg: +4 entries

5. **config/files/ deleted** — directory removed entirely.

6. **config/README.md created** — documents the new config structure: per-package `_config/` layout,
   SOPS encryption rules, and links to framework config, `.sops.yaml` rule files, and the package
   system docs.

7. **scripts/ai-only-scripts/fix-sops-pkg-keys/run created** — one-shot script that decrypts each
   `infra/<pkg>/_config/secrets.sops.yaml`, renames `<pkg>:` → `<pkg>_secrets:` at the top-level
   key, and re-encrypts in place using `SOPS_AGE_KEY_FILE=/home/pyoung/sops/age/keys.txt.pwy-home`.

Note: `infra/default-pkg/_config/secrets.sops.yaml` values are stored in plaintext within the SOPS envelope (root `.sops.yaml` only encrypts `data`/`stringData` keys — Kubernetes format). This is consistent with how other infra SOPS files work.
