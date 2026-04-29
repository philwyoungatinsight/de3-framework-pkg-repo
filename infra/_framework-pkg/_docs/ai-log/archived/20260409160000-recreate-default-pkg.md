---
date: 2026-04-09
title: Recreate infra/default-pkg — consolidate framework/_modules and null-pkg
---

## What changed

### Consolidate `framework/_modules` + `null-pkg` → `infra/default-pkg/`

The previous 2026-04-08 session eliminated `infra/default-pkg/` by distributing
its content to `framework/_modules/` (modules) and `infra/null-pkg/` (provider
templates + setup). This created complexity in `root.hcl` lines 108–158:

- `framework/_modules` lives outside `infra/`, requiring a special resolution path
  separate from the uniform `infra/<pkg>/` pattern
- The null provider was hardcoded as a special case in module lookup
- The provider template fallback (`null-pkg`) used a different name than the module
  fallback (`framework/`), contradicting the docs which said `default-pkg` for both
- `_modules_dir_resolved` needed a ternary branch just to handle the
  `"framework/_modules"` string resolving relative to stack_root instead of infra/

Fixed by recreating `infra/default-pkg/` as the single canonical fallback package:

```
git mv infra/null-pkg/_config    → infra/default-pkg/_config
git mv infra/null-pkg/_providers → infra/default-pkg/_providers
git mv infra/null-pkg/_setup     → infra/default-pkg/_setup
git mv framework/_modules        → infra/default-pkg/_modules
```

Config key renamed: `null-pkg:` → `default-pkg:` in `default-pkg.yaml`.

### `root.hcl` module resolution simplified

**Before:** 5-level ternary with special-case for `"framework/_modules"` string,
special-case for null provider, two intermediate locals (`_modules_dir_override`,
`_modules_dir_resolved`), and two different resolution roots (stack_root vs infra/).

**After:** Uniform 3-tier lookup, one local, one resolution root:

```hcl
_modules_dir_override = try(local.unit_params._modules_dir, null)
modules_dir = (
  local._modules_dir_override != null
  ? "${local.stack_root}/infra/${local._modules_dir_override}"
  : fileexists(".../${local.p_package}/_modules/.modules-root")
  ? "${local.stack_root}/infra/${local.p_package}/_modules"
  : fileexists(".../${local.p_tf_provider}-pkg/_modules/.modules-root")
  ? "${local.stack_root}/infra/${local.p_tf_provider}-pkg/_modules"
  : "${local.stack_root}/infra/default-pkg/_modules"
)
```

### Provider template and extra-provider fallbacks updated

`null-pkg/_providers/` → `default-pkg/_providers/` in both `_provider_tpl_path`
and `_extra_provider_entry_paths` fallback tiers.

### YAML config overrides updated (10 occurrences)

`_modules_dir: framework/_modules` → `_modules_dir: default-pkg/_modules` in:
- `infra/gcp-pkg/_config/gcp-pkg.yaml` (1)
- `infra/proxmox-pkg/_config/proxmox-pkg.yaml` (4)
- `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` (5)

### Other updates

- `run` orchestrator: `null-pkg/_setup/run` → `default-pkg/_setup/run`
- `infra/default-pkg/_setup/run`: setup messages updated
- `docs/framework/code-architecture.md`: directory layout description updated
- `config/README.md`: stale reference to `infra/default-pkg/_config/config.yaml`
  corrected to `config/framework.yaml`

## Scope

`framework/generate-ansible-inventory/`, `framework/clean-all/`, and
`framework/lib/` are **not moved** — they are operational tools, not Terraform
package content, and do not contribute to root.hcl complexity.

## Why

The code-architecture.md docs already described `default-pkg` as the fallback for
both module and provider template resolution. The code did not match. This restores
consistency: one name, one location, uniform resolution logic.
