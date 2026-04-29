# Remove remaining default-pkg references from code

## Summary

Completed removal of all `default-pkg` references from code files. These were
left over after the `default-pkg` → `null-pkg` + `config/framework.yaml`
refactoring in the previous session.

## Files Changed

### Code fixes (actual bugs)

- **`infra/pwy-home-lab-pkg/_tg_scripts/local/update-ssh-config/run`**
  - Changed `_find_component_config terragrunt_lab_stack` to direct path
    `$GIT_ROOT/config/framework.yaml`
  - Changed `cfg.get('default-pkg', {})` to `cfg.get('framework', {})`

- **`infra/mesh-central-pkg/_tg_scripts/mesh-central/install/run`**
  - Updated secrets file path from `default-pkg/_config/default-pkg_secrets.sops.yaml`
    to `mesh-central-pkg/_config/mesh-central-pkg_secrets.sops.yaml`
  - Updated secrets key path from
    `default-pkg_secrets.providers.null.config_params["cat-hmc/null/..."]`
    to `mesh-central-pkg_secrets.config_params["mesh-central-pkg/_stack/null/..."]`

- **`infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-managed-vms-test/run`**
  - Fixed `check-maas-machines` path from
    `scripts/wave-scripts/default-pkg/common/check-maas-machines/run`
    to `infra/maas-pkg/_wave_scripts/common/check-maas-machines/run`

- **`scripts/ai-only-scripts/recover-ms01-network/run`**
- **`scripts/ai-only-scripts/push-debian-preseed/run`**
- **`scripts/ai-only-scripts/fix-ms01-interface-link/run`**
- **`scripts/ai-only-scripts/reset-ms01-01/run`**
  - All four: replaced broken `VENV_BASE` pointing at non-existent
    `wave-scripts/default-pkg/test-ansible-playbooks` with `$SCRIPT_DIR`
    (each ai-only-script creates its own venv in its own directory)

- **`utilities/bash/framework-utils.sh`**
  - Removed legacy `default-pkg` comment from `_find_component_config`
  - Extended function to also search `$GIT_ROOT/config/` (framework config dir)
    before falling back to `$_INFRA_DIR/*/_config/`

- **`run`** (Python orchestrator)
  - Updated comment: `infra/default-pkg/_config/default-pkg.yaml` → `config/framework.yaml`

## Verification

`grep -r "default-pkg" --include="*.hcl" --include="*.py" --include="*.sh"
--include="run" --include="*.yaml" --include="*.yml"` returns no matches
in code files.
