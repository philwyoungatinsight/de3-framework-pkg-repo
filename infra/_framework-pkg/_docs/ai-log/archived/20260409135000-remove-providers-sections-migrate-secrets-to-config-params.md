---
date: 2026-04-09
title: Remove providers sections from all package configs; migrate AWS/Azure credentials to config_params
---

## What changed

### Secrets files (SOPS migration)

`aws-pkg_secrets.sops.yaml` and `azure-pkg_secrets.sops.yaml` had provider
credentials stored under `providers.<name>.*` — the old config format.
These were migrated to `config_params[<path>].*` (the current format) so they
are picked up by `unit_secret_params` during ancestor-merge in root.hcl.

- `azure-pkg_secrets`: `providers.azure.{client_id, client_secret,
  subscription_id, tenant_id}` → `config_params["azure-pkg/_stack/azure/examples"].*`
- `aws-pkg_secrets`: `providers.aws.{access_key_id, secret_access_key}` →
  `config_params["aws-pkg/_stack/aws/examples"].{access_key, secret_key}`
  (key names corrected to match what root.hcl looks for in unit_secret_params)

### Public YAML files (all packages)

Removed the `providers:` section from every package public config YAML.
All entries were empty `{}` maps — they carried no configuration and served
no function. The provider a unit uses is already declared via `_provider` in
`config_params`, and the provider template is resolved via `_providers/*.tpl`
files.

### root.hcl (no changes needed)

`cloud_public` and `cloud_secret` locals both resolve to `{}` via `try(..., {})`
when no `providers` section is present — identical to the previous behaviour
since all public providers sections were already empty. Template variable
resolution in `_provider_template_vars` checks `unit_secret_params` first
(new format) before `cloud_secret` (old format), so credentials are found at
the new location automatically.

## Why

Per CLAUDE.md: all provider config comes from config_params (unit params).
The `providers` section was an old indirection layer that has been fully
superseded by the per-path config_params model.
