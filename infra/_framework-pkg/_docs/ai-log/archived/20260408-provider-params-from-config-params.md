# 2026-04-08 Provider parameters from config_params — eliminate providers: section values

## Summary

Moved all provider-configuration values out of the `providers:` section in package
`config.yaml` files and into `config_params`. Updated unit HCL files to read provider
parameters from `unit_params` instead of `cloud_public`.

## Motivation

`providers:` was a parallel config structure that duplicated what `config_params` can
already express. Moving values into `config_params` means they are inherited via the
same ancestor-merge mechanism as all other unit parameters, enabling per-subtree overrides
and multi-provider support (e.g., two aliased AWS providers for VPC peering) without
any special-casing in root.hcl.

## Changes

### config_params additions (per-package)

Values moved from `providers.<name>` to `config_params` at the shallowest
`<pkg>/_stack/<provider>/...` key for each provider subtree:

| Package | Values moved |
|---------|-------------|
| `gcp-pkg` | `_provider_project`, `project_prefix` → `gcp-pkg/_stack/gcp/examples` |
| `aws-pkg` | `_provider_auth_method`, `_provider_profile`, `project_prefix` → `aws-pkg/_stack/aws/examples` |
| `azure-pkg` | `project_prefix` → `azure-pkg/_stack/azure/examples` |
| `unifi-pkg` | `project_prefix` → `unifi-pkg/_stack/unifi/examples` |
| `proxmox-pkg` | `project_prefix` removed (unused — no proxmox unit reads it) |
| `demo-buckets-example-pkg` | `_provider_project`, `project_prefix` → GCP/AWS examples subtrees |
| `pwy-home-lab-pkg` | All values distributed to their respective subtree roots; new `aws/us-east-1` entry added; `_provider: aws` moved up from `dev` to region level |

`_provider_*` keys are picked up by `_provider_template_vars` in root.hcl (already
tried `unit_params._provider_*` first before `cloud_public.*`).

### providers: sections

All `providers:` entries simplified to empty `{}` bodies. The section is retained as
a placeholder for future provider-level config (e.g., multi-provider credentials).

### Unit HCL file updates (20 files)

- `cloud_public.project_prefix` → `unit_params.project_prefix` in 16 files
  (GCP bucket/cluster naming, AWS bucket naming, Azure resource group naming)
- `cloud_public.api_url` fallback removed from 4 unifi files
  (already redundant — `unit_params._provider_api_url` was the primary and always set)

## Backward compat

`cloud_public` and `cloud_secret` remain in root.hcl as fallbacks. Any package not yet
migrated continues to work. `cloud_public` now resolves to `{}` for all migrated packages.
