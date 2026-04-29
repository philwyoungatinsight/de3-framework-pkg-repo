# Cleanup: Remove terragrunt_lab_stack refs, add common_tags, fix docs

## Summary

Multi-part cleanup session covering:
1. `common_tags` completeness — added `common_tags_list` to `root.hcl` and applied to all Proxmox VMs
2. `_managed_by` unit param — new inheritable tag parameter
3. `root.hcl` comment accuracy — fixed stale skip-params comments
4. Ansible inventory path rename — `terragrunt_lab_stack/hosts.yml` → `inventory/hosts.yml`
5. Full `terragrunt_lab_stack` reference cleanup across all packages, scripts, docs, and framework

---

## 1. `common_tags_list` for Proxmox

Proxmox VM tags are `list(string)` not `map(string)`, so `common_tags` map
cannot be passed directly. Added `common_tags_list` to `root.hcl`:

```hcl
common_tags_list = compact([
  local.common_tags.environment,
  "managed-by-${local.common_tags.managed_by}",
  local.common_tags.owner       != "" ? "owner-${local.common_tags.owner}"             : "",
  local.common_tags.application != "" ? "app-${local.common_tags.application}"         : "",
  local.common_tags.cost_center != "" ? "cost-center-${local.common_tags.cost_center}" : "",
])
```

Applied `common_tags_list` to all 31 Proxmox VM terragrunt.hcl units across
`proxmox-pkg`, `pwy-home-lab-pkg`, and `image-maker-pkg`. Two patterns fixed:
- `tags = concat([p_env], local.additional_tags)` → `tags = concat(common_tags_list, local.additional_tags)`
- `tags = [p_env, "managed-by-terragrunt"]` → `tags = common_tags_list`

Added `CLAUDE.md` rule: all taggable resources must accept and apply
`common_tags` (cloud) or `common_tags_list` (Proxmox).

## 2. `_managed_by` unit param

Added `managed_by = try(tostring(local.unit_params._managed_by), "terragrunt")`
to `root.hcl` `common_tags` block. Documented in `docs/framework/unit_params.md`.

## 3. Ansible inventory path

Renamed `_DYNAMIC_DIR/ansible/terragrunt_lab_stack/hosts.yml` →
`_DYNAMIC_DIR/ansible/inventory/hosts.yml`. Single source of truth: the
`output_file` key in `config/framework.yaml`. Updated `framework/generate-ansible-inventory/README.md` and the CLAUDE.md de3-gui-pkg entry.

## 4. `terragrunt_lab_stack` reference elimination

The old monolithic config system (`terragrunt_lab_stack.yaml`) was replaced by
per-package YAML files at `infra/<pkg>/_config/<pkg>.yaml`. All references to
the old filename and path conventions were removed:

**HCL files (7 packages):**
- `terragrunt_lab_stack.yaml` → `<pkg>.yaml`
- `terragrunt_lab_stack_secrets.sops.yaml` → `<pkg>_secrets.sops.yaml`
- `terragrunt_lab_stack_<pkg>.providers.` → `<pkg>.providers.`

**Documentation and scripts:**
- All README, playbook, and task files updated to reference `pwy-home-lab-pkg.yaml`
  (the deployment config) or `config/framework.yaml` (for waves)
- `generate_ansible_inventory.py` doc comments updated
- `docs/README.md` title corrected
- `docs/framework/package-system.md` — major rewrite:
  - "How root.hcl Routes to a Package" section: corrected `p_package` derivation
    (`path_parts[0]` from filesystem path, not a unit_param), documented 3-tier
    fallback for modules and providers, documented `_modules_dir`/`_tg_scripts_dir`/
    `_wave_scripts_dir` overrides
  - "Adding a New Package" section: updated directory structure and config file
    naming to current conventions
- `docs/framework/unit_params.md`:
  - Fixed `terragrunt_lab_stack.yaml` reference → `config/framework.yaml`
  - Replaced stale `_package` section (which claimed it was a settable unit_param
    controlling `p_package`) with accurate `_modules_dir` and `_tg_scripts_dir`/
    `_wave_scripts_dir` sections — `p_package` is derived from the path, not a param

**`.claude/settings.local.json`:**
- Removed 3 stale allow entries pointing to deleted `deploy/config/files/...` paths
- Updated SOPS path to current `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml`

## Files changed

- `root.hcl` — `common_tags_list`, `_managed_by`, comment fixes
- `CLAUDE.md` — `common_tags` rule added
- `config/framework.yaml` — inventory output path
- `framework/generate-ansible-inventory/generate_ansible_inventory.py` — doc comments
- `framework/generate-ansible-inventory/README.md` — path references
- `docs/README.md` — title
- `docs/framework/package-system.md` — major rewrite of routing + adding sections
- `docs/framework/unit_params.md` — `_package` → `_modules_dir`/`_tg_scripts_dir`, wave ref fix
- `docs/idempotence-and-tech-debt.md` — config file reference
- 31× Proxmox VM `terragrunt.hcl` — `common_tags_list`
- All `.hcl` files in 7 packages — config file name references
- Multiple Ansible playbooks, tasks, READMEs — config file name references
- `infra/de3-gui-pkg/_applications/de3-gui/homelab_gui/homelab_gui.py` — key rename
- `infra/de3-gui-pkg/_applications/de3-gui/CLAUDE.md` — inventory path
- `.claude/settings.local.json` — stale allow entries removed
