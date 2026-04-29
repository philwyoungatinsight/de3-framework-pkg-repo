# config-mgr

Pre-processor, reader, and writer for framework package config. It merges all package
YAML configs into `$_CONFIG_DIR` and routes reads/writes through `config_source` chains.
Called automatically by `set_env.sh` on every shell session.

## Quick start

```bash
source set_env.sh          # exports $_CONFIG_MGR and adds tool dirs to $PATH
config-mgr get <unit_path>
```

`set_env.sh` adds all framework tool directories to `$PATH` (idempotent), so bare
command names (`config-mgr`, `pkg-mgr`, `unit-mgr`, etc.) work directly.

---

## Commands

### `generate` — rebuild merged config

Reads all package YAML files, merges `config_params`, copies encrypted SOPS files
unchanged to `$_CONFIG_DIR`. Skips packages whose source files are unchanged (manifest
tracking).

```bash
config-mgr generate                      # normal: prints only regenerated packages
config-mgr generate --output-mode silent
config-mgr generate --output-mode verbose  # one line per package, including skipped
```

Example output (verbose):

```
config-mgr: aws-pkg up to date
config-mgr: pwy-home-lab-pkg regenerated
```

---

### `get` — read merged config for a unit

Reads `$_CONFIG_DIR/<pkg>.yaml`, extracts `config_params`, then applies **ancestor-merge**:
keys at each path segment are merged top-down, so deeper keys override shallower ones.

```bash
config-mgr get <unit_path>
```

**Example — read a stack-level path (inherits from package root):**

```bash
config-mgr get pwy-home-lab-pkg/_stack/aws/us-east-1
```

Output:

```yaml
_provider: aws
_provider_aws_auth_method: profile
_provider_aws_profile: pwy-hl-20260406-1842
project_prefix: pwy-tg-stack
```

**Example — read a leaf unit (all ancestor keys merged in):**

```bash
config-mgr get pwy-home-lab-pkg/_stack/aws/us-east-1/dev/test-bucket
```

Output:

```yaml
_env: dev
_provider: aws
_provider_aws_account_id: 792566780889
_provider_aws_auth_method: profile
_provider_aws_profile: pwy-hl-20260406-1842
_region: us-east-1
_unit_purpose: AWS S3 test bucket for cloud.storage wave validation.
_wave: cloud.storage
bucket_name: pwy-tg-stack-hmc-bucket
force_destroy: true
project_prefix: pwy-tg-stack
versioning_enabled: false
```

---

### `set` — write a config_params key

Writes `<key>` under `config_params[<unit_path>]` in the correct source YAML file,
then refreshes `$_CONFIG_DIR` with a silent generate.

```bash
config-mgr set <unit_path> <key> <value>
```

Dot-separated keys navigate nested dicts:

```bash
config-mgr set pwy-home-lab-pkg/_stack/aws/us-east-1/dev/test-bucket force_destroy false
config-mgr set proxmox-pkg/_stack/proxmox/pwy-homelab/vms/my-vm  disk.size 32
```

**Write a secret (SOPS):**

```bash
config-mgr set pwy-home-lab-pkg/_stack/maas/pwy-homelab _provider_maas_api_key "abc123" --sops
```

Calls `sops --set` internally. The file on disk stays encrypted.

---

### `set-raw` — write an arbitrary top-level key

Like `set`, but not scoped to `config_params`. Use for metadata fields such as
`_provides_capability`.

```bash
config-mgr set-raw <pkg> <yaml_key_path> <value>
config-mgr set-raw pwy-home-lab-pkg _provides_capability.0 "pwy-home-lab-pkg: 1.2.0"
```

---

### `move` — rename a unit path in config

Used by `unit-mgr` after renaming a unit directory. Migrates `config_params` keys from
source to destination and refreshes merged output.

```bash
config-mgr move <src_unit_path> <dst_unit_path>
```

---

## Reading SOPS secrets

`config-mgr` never decrypts SOPS files to disk. To read a secret at runtime:

**Single key (shell):**

```bash
# Source file is always under infra/<pkg>/_config/
SOPS_FILE="infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml"

sops --extract \
  '["pwy-home-lab-pkg_secrets"]["config_params"]["pwy-home-lab-pkg/_stack/maas/pwy-homelab"]["_provider_maas_api_key"]' \
  "$SOPS_FILE"
```

**Full file into memory (Python):**

```python
import subprocess, yaml

result = subprocess.run(
    ["sops", "--decrypt", "infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml"],
    capture_output=True, text=True, check=True
)
secrets = yaml.safe_load(result.stdout)
api_key = secrets["pwy-home-lab-pkg_secrets"]["config_params"] \
              ["pwy-home-lab-pkg/_stack/maas/pwy-homelab"]["_provider_maas_api_key"]
```

**HCL (Terragrunt):**

```hcl
locals {
  secrets = yamldecode(sops_decrypt_file("${get_repo_root()}/$_CONFIG_DIR/<pkg>.secrets.sops.yaml"))
}
```

The `$_CONFIG_DIR` copy of the SOPS file is an encrypted-only mirror for HCL consumers.
Direct `sops` commands must target the source file under `infra/<pkg>/_config/`.

---

## File layout

| Path | Purpose |
|------|---------|
| `infra/<pkg>/_config/<pkg>.yaml` | Public config; contains `config_params` |
| `infra/<pkg>/_config/<pkg>_secrets.sops.yaml` | Age-encrypted secrets |
| `$_CONFIG_DIR/<pkg>.yaml` | Merged output (written by `generate`) |
| `$_CONFIG_DIR/<pkg>.secrets.sops.yaml` | Encrypted copy for HCL `sops_decrypt_file()` |
| `$_CONFIG_DIR/.manifest` | JSON mtime cache; controls skipping unchanged packages |

---

## Config structure

```yaml
# infra/<pkg>/_config/<pkg>.yaml
<pkg-name>:
  _provides_capability:
    - <pkg-name>: 1.0.0
  config_params:
    <pkg>/_stack/<provider>/<region>:       # stack level — inherited by children
      _provider: aws
      project_prefix: my-stack
    <pkg>/_stack/<provider>/<region>/dev:   # env level
      _env: dev
      _wave: cloud.storage
    <pkg>/_stack/<provider>/<region>/dev/my-unit:  # leaf unit
      bucket_name: my-bucket
      force_destroy: true
```

`config-mgr get` on the leaf unit returns all three levels merged, with deeper keys
winning on collision.

---

## config_source chains

Some packages point to another package as their authoritative config location:

```yaml
# framework_packages.yaml
- name: proxmox-pkg
  config_source: pwy-home-lab-pkg
```

All `config-mgr set` and `set --sops` calls follow the chain to the terminal package
automatically. `generate` merges both source and target using `merge_method` from
`framework_config_mgr.yaml` (`interleave` or `source_only`).
