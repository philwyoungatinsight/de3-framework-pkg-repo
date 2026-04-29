# Package System

How infrastructure code and config is organised into packages, and how to add a new one.

For the full config file / deep-merge mechanics see
[config-files.md](config-files.md).

---

## What Is a Package?

A **package** is the unit of future separation into independent git repos.
Everything needed to deploy a specific workload (modules, provider templates,
hook scripts, wave scripts, config YAML, and infra units) belongs to exactly
one package.

The package system allows adding new workloads without touching any existing
code — drop a config YAML, create directories, done.

---

## What a Package Owns

| Component | Location |
|-----------|----------|
| Terraform modules | `infra/<pkg>/_modules/<provider>/<pkg>/` |
| Provider templates | `infra/<pkg>/_providers/` (optional — falls back to `_framework-pkg`) |
| Terragrunt hook scripts | `infra/<pkg>/_tg_scripts/<role>/<name>/run` |
| Wave test/precheck scripts | `infra/<pkg>/_wave_scripts/test-ansible-playbooks/<role>/<name>/` |
| Public config | `infra/<pkg>/_config/<pkg>.yaml` (top-level key: `<pkg>:`) |
| Encrypted secrets | `infra/<pkg>/_config/<pkg>_secrets.sops.yaml` (top-level key: `<pkg>_secrets:`) |
| Setup script | `infra/<pkg>/_setup/run` — installs CLI tools; called by `make setup` |
| Seed script | `infra/<pkg>/_setup/seed` — provisions cloud accounts; called by `make seed` (optional) |
| Infra units | `infra/<pkg>/_stack/<provider>/...` |
| Package docs | `infra/<pkg>/_docs/` |
| Package variables | `vars:` block at the top of the package YAML (optional) |

---

## Current Packages

| Package | What it owns | Source |
|---------|-------------|--------|
| `_framework-pkg` | Null run-scripts, local SSH config update, generate-inventory | local |
| `aws-pkg` | AWS provider template, S3 modules | `de3-runner` (ext) |
| `azure-pkg` | Azure provider template, Blob/Container modules | `de3-runner` (ext) |
| `gcp-pkg` | GCP provider template, GCS + GKE modules, kubeconfig fetch | `de3-runner` (ext) |
| `image-maker-pkg` | Image-maker VM + Packer build scripts, Kairos ISOs | `de3-runner` (ext) |
| `maas-pkg` | MaaS provider template, maas_machine module, configure-server/configure-machines | `de3-runner` (ext) |
| `mesh-central-pkg` | MeshCentral VM + configure scripts | `de3-runner` (ext) |
| `proxmox-pkg` | Proxmox provider template, VM/ISO/file modules, install/configure scripts | `de3-runner` (ext) |
| `unifi-pkg` | UniFi provider template, network/port-profile/device modules | `de3-runner` (ext) |
| `mikrotik-pkg` | MikroTik provider template and network modules | `de3-runner` (ext) |
| `de3-gui-pkg` | GUI launcher — reads `_browser_url` from units | `de3-runner` (ext) |
| `demo-buckets-example-pkg` | Config-coordinator only (no modules/templates) | `de3-runner` (ext) |
| `pwy-home-lab-pkg` | Deployment stack — no modules; config only, references all other packages | local |

Package names must NOT collide with provider names (`aws`, `gcp`, `azure`,
`maas`, `proxmox`, `unifi`, `null`). Use a workload-oriented name with a
`-pkg` suffix (e.g. `monitoring-pkg`, not `monitoring` or `grafana`).

### External packages and `_ext_packages/`

Most packages live in an external git repo (`de3-runner`) and are pulled into
this repo under `infra/_ext_packages/` as either a symlink (default) or a
shallow clone. The mechanism is configured in
`infra/_framework-pkg/_config/framework_package_management.yaml`:

```yaml
framework_package_management:
  default_inclusion_method: linked_copy   # full git clone at $HOME/git/de3-ext-packages/<slug>/
  external_package_dir: 'git/de3-ext-packages'
```

| Inclusion method | Where the repo lives | `infra/<pkg>/` entry |
|-----------------|----------------------|----------------------|
| `linked_copy` | `$HOME/<external_package_dir>/<slug>/` | symlink → clone |
| `local_copy` | `infra/_ext_packages/<slug>/` (shallow clone) | symlink → clone |

`./run --sync-packages` fetches/updates all external packages. Local packages
(`_framework-pkg`, `pwy-home-lab-pkg`) are checked in directly and are not listed
in `framework_package_management.yaml`.

---

## Package Variables (`vars:`)

A package YAML may declare a `vars:` block directly under its top-level key.
Values defined there can be referenced anywhere else in the same file using
`${varname}`, and from any other package YAML using the qualified form
`${pkg-name.varname}`.

```yaml
# infra/maas-pkg/_config/maas-pkg.yaml
maas-pkg:
  vars:
    maas_server: 10.0.10.11   # single source of truth

  providers:
    maas:
      config_params:
        pwy-home-lab-pkg/_stack/maas/pwy-homelab:
          _provider_api_url: http://${maas_server}:5240/MAAS   # local ref
          maas_host: ${maas_server}
          maas_server_ip: ${maas_server}
```

Cross-package reference from another file:

```yaml
# infra/proxmox-pkg/_config/proxmox-pkg.yaml
proxmox-pkg:
  providers:
    proxmox:
      config_params:
        proxmox-pkg/_stack/proxmox/pwy-homelab:
          maas_server_ip: ${maas-pkg.maas_server}   # qualified ref
```

### Rules

- `vars:` values must be **literals** — no `${...}` inside `vars:` (no chained
  resolution).
- Unrecognised references (e.g. a typo) are left unchanged rather than silently
  replaced with an empty string, making bad references easy to spot.
- Resolution happens **before** the deep-merge, so resolved values propagate
  correctly when ancestor paths are inherited by descendant units.
- Both the Terraform path (`merge-stack-config.py`) and the Ansible path
  (`config_base` role) resolve variables, so every consumer sees the same
  expanded values. See [config-files.md](config-files.md) for
  implementation details.

---

## How `root.hcl` Derives the Package

`root.hcl` splits the unit's filesystem path on `/` and takes the first
segment after `infra/`:

```hcl
path_parts = split("/", trimprefix(rel_path_raw, "infra/"))
p_package  = local.path_parts[0]   # e.g. "proxmox-pkg" from infra/proxmox-pkg/...
```

`p_package` is **always derived from the path** — there is no unit_param that
overrides it. This means the directory a unit lives in determines which package
config, state path, and default resources it gets.

`p_package` controls:

```hcl
# Package config and secrets loaded from:
infra/${p_package}/_config/${p_package}.yaml
infra/${p_package}/_config/${p_package}_secrets.sops.yaml

# Module directory (3-tier fallback — see below):
modules_dir = infra/${p_package}/_modules   # Tier 1 (if .modules-root present)

# Provider template (3-tier fallback):
infra/${p_package}/_providers/${provider}.tpl   # Tier 1

# Script directories (default — overridable):
_tg_scripts   = infra/${p_package}/_tg_scripts
_wave_scripts = infra/${p_package}/_wave_scripts
```

### 3-tier module and provider fallback

Both `modules_dir` and `_provider_tpl_path` use a 3-tier lookup, but the
resolution rules differ slightly:

**Module directory** (`modules_dir`) — uses a `.modules-root` sentinel file at
each tier:

1. **This package** — `infra/<p_package>/_modules/` (if `.modules-root` sentinel present)
2. **Canonical provider package** — `infra/<provider>-pkg/_modules/` (if `.modules-root` sentinel present)
3. **_framework-pkg** — `infra/_framework-pkg/_modules/` (always present)

**Provider template** (`_provider_tpl_path`) — checks file existence directly
(no sentinel):

1. **This package** — `infra/<p_package>/_providers/<provider>.tpl` (if file exists)
2. **Canonical provider package** — `infra/<provider>-pkg/_providers/<provider>.tpl` (if file exists)
3. **_framework-pkg** — `infra/_framework-pkg/_providers/<provider>.tpl` (framework fallback)

### Deployment packages and cross-package overrides

A deployment package (e.g. `pwy-home-lab-pkg`) holds no modules of its own.
Its units reference modules from canonical packages by setting override params
in `config_params`:

```yaml
"pwy-home-lab-pkg/_stack/proxmox/pwy-homelab":
  _tg_scripts_dir:   proxmox-pkg/_tg_scripts    # relative to infra/
  _wave_scripts_dir: proxmox-pkg/_wave_scripts

"pwy-home-lab-pkg/_stack/null/pwy-homelab":
  _modules_dir: _framework-pkg/_modules   # relative to infra/
```

Units in `terragrunt.hcl` reference the resolved locals without knowing which
package owns the resource:

```hcl
terraform {
  source = "${include.root.locals.modules_dir}/null_resource__run-script"
}

---

## Package Setup Scripts (`_setup/`)

Each package may contain up to two scripts under `infra/<pkg>/_setup/`:

### `_setup/run` — CLI tool installation

Called by `make setup` (`./run --setup-packages`) with **no arguments**.  
Responsible for installing the CLI tools the package needs (e.g. `aws`, `gcloud`, `az`).

Rules:
- Idempotent — check whether each tool is present before installing.
- Branch on platform: Homebrew (macOS), apt (Debian/Ubuntu), dnf (Fedora/RHEL).

```bash
# Pattern
_install_tools() {
    echo "=== <pkg> setup ==="
    _setup_<cli>
    echo "=== <pkg> setup complete ==="
}

_install_tools
```

`_framework-pkg` installs the core framework tools (jq, uv, python3, yq, sops,
opentofu, terragrunt, kubectl, helm) and is always run first.  Per-package
`_setup/run` scripts install provider-specific CLIs (e.g. `gcloud`, `aws`).

### `_setup/seed` — Cloud account provisioning

Called by `make seed` (`./run --seed-packages`) which runs **login → seed → test** for every
package that has this script.  Only needed for packages that own cloud accounts or bootstrap
resources (state buckets, IAM users, service accounts).

Sub-commands (all idempotent):

| Flag | Short | Action |
|------|-------|--------|
| `--seed` | `-b` | Create/confirm cloud accounts, state bucket, IAM user/SA |
| `--login` | `-l` | Verify existing auth; open browser OAuth only if expired/missing |
| `--test` | `-t` | Verify connectivity (e.g. S3 read/write, GCS access, az account show) |
| `--status` | `-S` | Print current resource status |
| `--clean` | | Remove local credential files |
| `--clean-all` | | Destroy all provisioned seed resources (destructive — prompts for confirmation) |

Config is read from the package's existing `_config/<pkg>.yaml` under a `seed:` sub-key, and
secrets from `_config/<pkg>_secrets.sops.yaml` under `seed:`.  Example:

```yaml
# infra/aws-pkg/_config/aws-pkg.yaml
aws-pkg:
  seed:
    aws_account_id: "123456789012"
    state_bucket: "my-tf-state"
    region: "us-east-1"

# infra/aws-pkg/_config/aws-pkg_secrets.sops.yaml
aws-pkg_secrets:
  seed:
    profile_name: "terraform"
    iam_user_name: "terragrunt-user"
    user_policy_json: '{"Version":"2012-10-17",...}'
```

---

## Adding a New Package

1. **Pick a name** — must not collide with a provider name. Use a workload name
   with a `-pkg` suffix, e.g. `monitoring-pkg`.

2. **Create the package skeleton:**
   ```
   infra/monitoring-pkg/
     _config/monitoring-pkg.yaml        # public config (top-level key: monitoring-pkg:)
     _setup/run                         # CLI tool installer (called by make setup)
     _setup/seed                        # cloud account provisioner (called by make seed, optional)
     _modules/<provider>/monitoring-pkg/<resource>/   # Terraform modules
     _providers/monitoring-pkg.tpl      # only if custom provider config needed
     _tg_scripts/<role>/<name>/run      # Terragrunt hook scripts
     _wave_scripts/test-ansible-playbooks/<role>/<name>/  # wave playbooks
     _stack/<provider>/...              # Terragrunt units
     _docs/README.md                    # package documentation
   ```
   `_providers/` is optional — `root.hcl` falls back to `_framework-pkg` if absent.
   Add a `.modules-root` sentinel file in `_modules/` so `root.hcl` Tier-1
   lookup finds it.

3. **Create the package config YAML:**
   ```
   infra/monitoring-pkg/_config/monitoring-pkg.yaml
   ```
   Top-level key must be `monitoring-pkg:`. `root.hcl` loads it automatically
   based on the unit's path — no code changes needed.

4. **Set `_provider`, `_region`, `_env`, and `_wave`** at ancestor paths in
   `config_params` so descendant units inherit without per-unit overrides.

5. **Create infra units** under `infra/monitoring-pkg/_stack/`. Each unit's
   `terragrunt.hcl` references `include.root.locals.modules_dir` — the path is
   resolved automatically from `p_package`.

6. **Name waves** using the `<category>.<pkg>` convention (e.g.
   `monitoring.grafana`). Set `_wave` in the config YAML and add a wave entry
   to `waves:` in `config/framework.yaml`. See [waves.md](waves.md).

7. **(Optional) Create a SOPS secrets file:**
   ```
   infra/monitoring-pkg/_config/monitoring-pkg_secrets.sops.yaml
   ```
   Top-level key must be `monitoring-pkg_secrets:`. `root.hcl` loads it
   automatically if the file exists.
