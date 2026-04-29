---
date: 2026-04-09
title: Apply _provider_<name>_<key> convention to all secret params
---

## What changed

### SOPS secrets files (5 files migrated)

Provider-credential keys in `config_params` renamed to follow the same
`_provider_<name>_<key>` naming convention used by public params.

| Old key | New key |
|---------|---------|
| `username` (proxmox) | `_provider_proxmox_username` |
| `password` (proxmox) | `_provider_proxmox_password` |
| `token.id` (proxmox, nested) | `_provider_proxmox_token_id` (flat) |
| `token.secret` (proxmox, nested) | `_provider_proxmox_token_secret` (flat) |
| `username` (unifi) | `_provider_unifi_username` |
| `password` (unifi) | `_provider_unifi_password` |
| `access_key` (aws) | `_provider_aws_access_key` |
| `secret_key` (aws) | `_provider_aws_secret_key` |
| `client_id` (azure) | `_provider_azure_client_id` |
| `client_secret` (azure) | `_provider_azure_client_secret` |
| `subscription_id` (azure) | `_provider_azure_subscription_id` |
| `tenant_id` (azure) | `_provider_azure_tenant_id` |
| `api_key` (maas) | `_provider_maas_api_key` |

Keys that are **not** renamed (module inputs, not provider template vars):
`cloud_init_password`, `nodeName`, `amt_password`, `amt_user`,
`smart_plug_*`, `power_*`, `admin_password`, `db_password`, etc.

Files: `aws-pkg_secrets`, `azure-pkg_secrets`, `maas-pkg_secrets`,
`proxmox-pkg_secrets`, `pwy-home-lab-pkg_secrets`, `unifi-pkg_secrets`.

### root.hcl — `_provider_template_vars` secrets section

All secret lookups now use the same bracket-interpolation pattern as public params:

```hcl
# Before
USERNAME = try(local.unit_secret_params.username, "")
TOKEN_ID = try(local.unit_secret_params.token.id, "")

# After
USERNAME = try(local.unit_secret_params["_provider_${local.p_tf_provider}_username"], "")
TOKEN_ID = try(local.unit_secret_params["_provider_${local.p_tf_provider}_token_id"], "")
```

Also flattened the nested `token.id` / `token.secret` access since the keys are now flat.

### Unit HCL files (4 files)

UniFi units that read credentials directly as module inputs updated:

```hcl
# Before
unifi_username = try(include.root.locals.unit_secret_params.username, "")
# After
unifi_username = try(include.root.locals.unit_secret_params["_provider_unifi_username"], "")
```

Files: `pwy-home-lab-pkg/_stack/unifi/pwy-homelab/{network,port-profile}` and
`unifi-pkg/_stack/unifi/examples/pwy-homelab/{network,port-profile}`.

## Why

Public params already used `_provider_<name>_<key>` for collision-safety and explicitness.
Secrets used bare key names (`username`, `password`) — inconsistent, and prone to collision
if two providers' secrets ever merged into the same unit's `unit_secret_params`.
Now both sections of `_provider_template_vars` follow the identical pattern.
