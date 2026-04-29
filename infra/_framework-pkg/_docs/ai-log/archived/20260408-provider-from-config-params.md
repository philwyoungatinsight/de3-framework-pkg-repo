# 2026-04-08 Provider from config_params — eliminate path-encoded provider

## Summary

The Terraform provider was previously derived from the directory path (`path_parts[2]`). It is now set via `_provider` in `config_params` and inherited via ancestor-merge. The directory path structure no longer encodes the provider.

## What changed in root.hcl

- `p_tf_provider = local.path_parts[2]` removed from path parsing section
- Config loading restructured: flat `_config_params` loaded first (no provider needed), `unit_params` merged, then `p_tf_provider = try(tostring(local.unit_params._provider), local.path_parts[2])`
- `cloud_public` / `cloud_secret` now loaded AFTER provider is known
- `_secret_params` supports both flat (new style) and provider-scoped (backward compat) secrets `config_params`
- `_tg_scripts_dir` / `_wave_scripts_dir` `config_params` overrides added (allows deployment packages to point at canonical package scripts)
- New comment: "The Terraform provider is NOT derived from the path — it is set via `_provider` in config_params"

## What changed in infra/\<pkg\>/_config/config.yaml (all 10 packages)

- `providers.<provider>.config_params` moved to top-level `config_params`
- `_provider: <provider>` added at the shallowest `<pkg>/_stack/...` key per provider subtree
- `null` provider written as quoted string `'null'`
- Stale `cat-hmc/...` config_params keys removed (dead — no units at those paths)
- `providers.<provider>` retains only provider-level settings (endpoint, project_prefix, credentials structure)

## Example (proxmox-pkg)

```yaml
proxmox-pkg:
  providers:
    proxmox:
      project_prefix: pwy-tg-stack
    null: {}
  config_params:
    proxmox-pkg/_stack/proxmox/examples:
      _provider: proxmox
      skip: true
    proxmox-pkg/_stack/null/examples:
      _provider: 'null'
      skip: true
```

## Backward compatibility

`p_tf_provider = try(tostring(local.unit_params._provider), local.path_parts[2])` — falls back to `path_parts[2]` if `_provider` is not set, so packages not yet migrated continue to work.

## Why

Provider was encoded in the directory path (`_stack/<provider>/...`), coupling path layout to Terraform backend choice. Moving provider to `config_params` decouples layout from provider, and allows deployment packages (like `pwy-home-lab-pkg`) to reorganize units without being constrained by provider naming in directory structure.

## Files changed

- `root.hcl` — config loading order restructured; provider resolution logic updated
- `infra/aws-pkg/_config/config.yaml`
- `infra/azure-pkg/_config/config.yaml`
- `infra/demo-buckets-example-pkg/_config/config.yaml`
- `infra/gcp-pkg/_config/config.yaml`
- `infra/image-maker-pkg/_config/config.yaml`
- `infra/maas-pkg/_config/config.yaml`
- `infra/mesh-central-pkg/_config/config.yaml`
- `infra/proxmox-pkg/_config/config.yaml`
- `infra/pwy-home-lab-pkg/_config/config.yaml`
- `infra/unifi-pkg/_config/config.yaml`

11 files changed, 1485 insertions, 2115 deletions.
