---
date: 2026-04-09
title: Simplify root.hcl — remove cloud_public/cloud_secret two-path system
---

## What changed

### root.hcl

Removed the dead `cloud_public` / `cloud_secret` / `_provider_ancestor_params` locals that
formed an obsolete second path for provider configuration.

**Removed locals:**
- `cloud_public` — read `providers.<name>.*` from public package YAML; always `{}` after
  the providers sections were removed in the prior commit
- `cloud_secret` — read `providers.<name>.*` from secrets YAML; always `{}` after the
  SOPS migration
- `_provider_ancestor_params` — grouped per-provider ancestor params; only used as a
  fallback alongside `_ancestor_param_list`

**Simplified `_secret_params`:** removed the `merge()` with `cloud_secret.config_params`
(always empty); now reads only from `_package_sec_cfg.config_params`.

**Simplified `_provider_template_vars`:** removed all `local.cloud_public.*` and
`local.cloud_secret.*` fallback arguments. Each variable is now a single `try()` sourced
exclusively from `unit_params` (public) or `unit_secret_params` (secrets):

```hcl
# Before
PROJECT = try(local.unit_params["_provider_${local.p_tf_provider}_project"], local.cloud_public.project, "")
USERNAME = try(local.unit_secret_params.username, local.cloud_secret.username, "")

# After
PROJECT  = try(local.unit_params["_provider_${local.p_tf_provider}_project"], "")
USERNAME = try(local.unit_secret_params.username, "")
```

Updated comment block above `_provider_template_vars` to reflect the single-source design.

### Unit HCL files (34 files)

Bulk-updated all unit `terragrunt.hcl` files that still referenced the removed locals:

- `cloud_secret.cloud_init_password` fallback → removed (14 Proxmox VM units across
  pwy-home-lab-pkg, proxmox-pkg, image-maker-pkg)
- `cloud_secret.password` / `cloud_secret.username` fallbacks → removed (4 UniFi units
  across pwy-home-lab-pkg and unifi-pkg)
- `_provider_ancestor_params[p_tf_provider]` → `_ancestor_param_list` (all Kairos,
  packer, and pxe units that iterate over ancestor params)

## Why

The `providers:` sections in public and secrets YAML files were removed in the prior
commit. With nothing supplying `cloud_public` or `cloud_secret`, every `try()` fallback
that referenced them was dead code — it could never match. The single-source design
(`config_params` → `unit_params`/`unit_secret_params`) is simpler, more consistent, and
matches the stated CLAUDE.md convention: "all provider config comes from config_params".
