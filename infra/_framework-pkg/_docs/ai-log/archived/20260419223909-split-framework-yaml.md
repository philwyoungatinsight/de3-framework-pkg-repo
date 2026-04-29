# split framework.yaml into per-key files under _config/

**Date**: 2026-04-19

## Summary

Split `infra/default-pkg/_config/framework.yaml` into one file per top-level key:
- `framework_backend.yaml`
- `framework_ansible_inventory.yaml`
- `framework_clean_all.yaml`
- `framework_ephemeral_dirs.yaml`
- `framework_external_capabilities.yaml`
- `framework_pre_apply_unlock.yaml`
- `framework_validate_config.yaml`
- `framework_package_repositories.yaml`
- `framework_packages.yaml`

Each file uses a top-level key matching its filename stem (e.g. `framework_backend:` in `framework_backend.yaml`).

## Created

- `infra/default-pkg/_framework/_utilities/python/framework_config.py` — shared helper that assembles split files into a unified dict via `load_framework_config(config_dir)` and `find_framework_config_dir(root)`.

## Updated consumers

- `root.hcl` — reads `framework_backend.yaml` directly via `yamldecode(file(...))[\"framework_backend\"]`; removed `_framework_cfg` local
- `infra/default-pkg/_framework/_utilities/python/gcs_status.py` — reads `framework_backend.yaml` directly
- `infra/default-pkg/_framework/_utilities/bash/gcs-status.sh` — reads `framework_backend.yaml` directly
- `infra/default-pkg/_framework/_pkg-mgr/run` — reads `framework_backend.yaml` directly
- `infra/default-pkg/_framework/_unit-mgr/unit_mgr/main.py` — reads `framework_backend.yaml` directly via `_read_framework_backend()`
- `infra/default-pkg/_framework/_human-only-scripts/purge-gcs-status/run` — reads `framework_backend.yaml` directly
- `infra/default-pkg/_framework/_utilities/python/validate-config.py` — uses `framework_config` helper
- `run` (main orchestrator) — uses `framework_config` helper via `load_framework_config(find_framework_config_dir(STACK_ROOT))`
- `infra/default-pkg/_framework/_clean_all/run` — inlines the same assembly logic (no import of shared helper to keep it self-contained)
- `infra/default-pkg/_framework/_ephemeral/run` — reads `framework_ephemeral_dirs.yaml` directly
- `infra/default-pkg/_framework/_generate-inventory/generate_ansible_inventory.py` — `load_stack_config()` accepts a config dir and assembles split files
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml` — loads `framework_backend.yaml` with `include_vars`; updated var name to `_framework_backend`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml` — same as above

## Deleted

- `infra/default-pkg/_config/framework.yaml` — replaced by the split files above
