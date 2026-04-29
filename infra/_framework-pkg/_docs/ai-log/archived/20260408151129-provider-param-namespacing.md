# 2026-04-08 Provider param namespacing: _provider_<PROVIDER>_*

## Summary

Renamed all `_provider_*` config_params keys to `_provider_<PROVIDER>_*` to
eliminate ambiguity and prevent collisions when multiple providers coexist on
the same unit subtree. Updated `root.hcl` to derive the key name dynamically
from `p_tf_provider` at plan time.

## Motivation

The old `_provider_api_url`, `_provider_endpoint`, etc. had no provider
namespace — a unit with both a proxmox and maas provider entry would have no
way to distinguish `_provider_endpoint` (proxmox) from `_provider_api_url`
(maas). The new naming makes each param unambiguous regardless of what other
providers are defined in the same subtree.

## Changes

### `root.hcl` — dynamic key lookup

`_provider_template_vars` now constructs the config_params key name at plan
time using `p_tf_provider`:

```hcl
# Before:
PROJECT = try(local.unit_params._provider_project, local.cloud_public.project, "")

# After:
PROJECT = try(local.unit_params["_provider_${local.p_tf_provider}_project"], local.cloud_public.project, "")
```

This applies to all 23 provider template variables (PROJECT, ACCOUNT_ID,
ENDPOINT, API_URL, INSECURE, SSH_USERNAME, etc.).

### Config param renames

| Old key | New key | Provider |
|---|---|---|
| `_provider_endpoint` | `_provider_proxmox_endpoint` | proxmox |
| `_provider_insecure` | `_provider_proxmox_insecure` / `_provider_unifi_insecure` | proxmox / unifi |
| `_provider_ssh_agent` | `_provider_proxmox_ssh_agent` | proxmox |
| `_provider_ssh_username` | `_provider_proxmox_ssh_username` | proxmox |
| `_provider_api_url` | `_provider_maas_api_url` / `_provider_unifi_api_url` | maas / unifi |
| `_provider_project` | `_provider_gcp_project` | gcp |
| `_provider_account_id` | `_provider_aws_account_id` | aws |
| `_provider_auth_method` | `_provider_aws_auth_method` | aws |
| `_provider_profile` | `_provider_aws_profile` | aws |

### Files updated

Config YAMLs:
- `infra/proxmox-pkg/_config/config.yaml`
- `infra/maas-pkg/_config/config.yaml`
- `infra/unifi-pkg/_config/config.yaml`
- `infra/aws-pkg/_config/config.yaml`
- `infra/gcp-pkg/_config/config.yaml`
- `infra/image-maker-pkg/_config/config.yaml`
- `infra/demo-buckets-example-pkg/_config/config.yaml`
- `infra/pwy-home-lab-pkg/_config/config.yaml`

Terragrunt HCL (direct `unit_params` access):
- `infra/pwy-home-lab-pkg/_stack/unifi/pwy-homelab/port-profile/terragrunt.hcl`
- `infra/pwy-home-lab-pkg/_stack/unifi/pwy-homelab/network/terragrunt.hcl`
- `infra/unifi-pkg/_stack/unifi/examples/pwy-homelab/port-profile/terragrunt.hcl`
- `infra/unifi-pkg/_stack/unifi/examples/pwy-homelab/network/terragrunt.hcl`

Ansible tasks (config_params key references):
- `infra/unifi-pkg/_wave_scripts/common/verify-unifi-networking/tasks/capture-config-fact.yaml`
- `infra/unifi-pkg/_wave_scripts/test-ansible-playbooks/network/network-validate-config/tasks/capture-config-fact.yaml`
