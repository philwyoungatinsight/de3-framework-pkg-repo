# Config Files and the Package System

How stack configuration is structured, loaded, and extended via packages.

---

## The Core Idea

All configuration for every unit lives in YAML files — never hardcoded in HCL.
Each package owns its own config file. The framework deep-merges all package
configs at Terragrunt init time, so adding a new package means dropping a new
YAML file under `infra/`. No code changes required.

---

## Where Config Files Live

Every package keeps its config alongside its code:

```
infra/<pkg>/
└── _config/
    ├── <pkg>.yaml                 ← public config   (top-level key: <pkg>:)
    └── <pkg>_secrets.sops.yaml   ← encrypted secrets (top-level key: <pkg>_secrets:)
```

**Rule:** every file is named after the top-level key it contains. This lets
`_find_component_config <key>` locate any config file by name across all
packages without knowing which package owns it.

---

## File Structure

### Public config (`<pkg>.yaml`)

```yaml
<pkg>:
  vars:                          # optional — string interpolation for this package
    my_host: 10.0.10.11

  providers:
    <provider>:                  # provider-level settings (endpoint, project, region)
      config_params:
        <unit-path-prefix>:      # ancestor path — all descendant units inherit these keys
          _wave: some.wave
          _provider: <provider>
          some_key: some_value
          _provider_<PROVIDER>_endpoint: http://${my_host}:1234

  config_params:                 # flat config_params not scoped to a provider
    <unit-path-prefix>:
      key: value
```

### Secrets (`<pkg>_secrets.sops.yaml`)

Same structure as public config but SOPS-encrypted. Top-level key is
`<pkg>_secrets:` to distinguish it from public config.

---

## How the Merge Works

`root.hcl` loads config for each unit in two steps:

**1. Package config** — `root.hcl` reads `infra/<pkg>/_config/<pkg>.yaml` directly
(where `<pkg>` comes from the unit's path). Secrets are decrypted via
`sops_decrypt_file()` in HCL.

**2. Framework config** — `root.hcl` reads `infra/_framework-pkg/_config/_framework-pkg.yaml`
for stack-wide settings (waves ordering, state backend). This is always loaded
regardless of which package owns the unit.

**3. Ancestor-path merge** — within a package's `config_params`, `root.hcl`
collects every entry whose key is a prefix of the unit's path, then merges
them in order (deepest wins):

```
Unit path:  <pkg>/_stack/<provider>/<env>/<cluster>/<node>/vms/<vm>

Matches:
  <pkg>/_stack/<provider>/<env>                → region, provider endpoint…
  <pkg>/_stack/<provider>/<env>/<cluster>/<node>  → node_name, datastore…
  <pkg>/_stack/…/<node>/vms/<vm>              → vm-specific overrides
```

The merged result is `unit_params` in `root.hcl`, accessible in every
`terragrunt.hcl` as `local.up = include.root.locals.unit_params`.

**Deep merge vs shallow merge:** HCL's built-in `merge()` is shallow.
`framework/lib/merge-stack-config.py` does a proper recursive merge so
packages can add keys inside another package's `config_params` subtree
without wiping out existing entries.

---

## Package Variables

A package YAML may declare a `vars:` block. Values are resolved in every
string value across the file before the deep-merge runs.

```yaml
<pkg>:
  vars:
    my_host: 10.0.10.11

  providers:
    <provider>:
      config_params:
        <pkg>/_stack/<provider>/<env>:
          endpoint: http://${my_host}:5240   # → http://10.0.10.11:5240
          host: ${my_host}                   # → 10.0.10.11
```

| Syntax | Meaning |
|--------|---------|
| `${varname}` | Local — resolves from this package's `vars:` |
| `${pkg-name.varname}` | Qualified — resolves from another package's `vars:` |

`vars:` values must be literals — nested `${...}` inside `vars:` is not
supported. Unrecognised references are left unchanged.

Resolution runs in two places so both consumers see identical values:

- **`merge-stack-config.py`** (Terraform path) — two-pass Python: collect all
  `vars:` sections, then walk every string value and substitute `${...}` tokens.
- **`config_base` Ansible role** (Ansible path) — same substitution before
  `_tg_providers` aggregation.

---

## How `p_package` Is Derived

`root.hcl` derives `p_package` from the unit's filesystem path — no config key
required:

```
infra/<pkg>/_stack/<provider>/<path...>/<unit>/
      ^^^^
      p_package = this directory name
```

`p_tf_provider` comes from `_provider` in `unit_params` (set once at an
ancestor path in the YAML). It falls back to `path_parts[2]` for packages
that haven't migrated.

---

## The Package System

Each package under `infra/<pkg>/` is self-contained. `p_package` drives module
source paths, provider template lookup, and script paths automatically — see
[code-architecture.md](code-architecture.md) for the 3-tier lookup rules.

### What a Package Owns

| Component | Location |
|-----------|----------|
| Terraform modules | `infra/<pkg>/_modules/<provider>/<module>/` |
| Provider templates | `infra/<pkg>/_providers/<provider>.tpl` |
| Terragrunt hook scripts | `infra/<pkg>/_tg_scripts/<role>/<name>/run` |
| Wave test/pre playbooks | `infra/<pkg>/_wave_scripts/test-ansible-playbooks/<role>/<name>/` |
| Public config | `infra/<pkg>/_config/<pkg>.yaml` |
| Encrypted secrets | `infra/<pkg>/_config/<pkg>_secrets.sops.yaml` |
| Stack units | `infra/<pkg>/_stack/<provider>/<path...>/<unit>/` |
| Tool setup | `infra/<pkg>/_setup/run` |

A package does not need to own all of these. A stack package (one with only
units) typically has no `_modules/` or `_providers/` — it uses the 3-tier
fallback to consume them from a provider package.

---

## Adding a New Package

1. **Create the directory:** `infra/<new-pkg>/`

2. **Create the config file:**
   ```
   infra/<new-pkg>/_config/<new-pkg>.yaml
   ```
   Top-level key must be `<new-pkg>:`. The merge script discovers it
   automatically — no code changes needed.

3. **Set `_provider` at ancestor paths** so descendant units know which
   provider to use:
   ```yaml
   <new-pkg>:
     config_params:
       <new-pkg>/_stack/<provider>/<env>:
         _provider: <provider>
         _wave: <wave-name>
   ```

4. **Add a wave entry** in `infra/_framework-pkg/_config/_framework-pkg.yaml`
   under `waves_ordering:` if the package introduces new waves.

5. **Add modules / provider templates** under `_modules/` and `_providers/`
   only if this package introduces a new provider. Reuse existing provider
   packages via the 3-tier lookup otherwise.

---

## Finding Config Files

`_find_component_config <key>` (in `utilities/bash/framework-utils.sh`) locates
any config file by its top-level key name, searching all `infra/*/_config/`
directories:

```bash
# Find a public config:
_find_component_config gcp-pkg       # → infra/gcp-pkg/_config/gcp-pkg.yaml

# Find a secrets file:
_find_component_config gcp_seed_secrets  # → infra/<pkg>/_config/gcp_seed_secrets.sops.yaml
```

Because every file is named after its key, files can be moved between packages
without changing any code — only the location changes.

---

## Framework Config File Locations

Framework-level config files (prefixed `framework_`) are distinct from package config.
They configure how the framework tools themselves operate, not unit_params for Terraform.

### `config/_framework.yaml` — the one true anchor

`config/_framework.yaml` declares which package is the "main package" for this
deployment. All framework config files can live in that package's `_config/` directory.

```yaml
_framework:
  main_package: pwy-home-lab-pkg
```

`set_env.sh` reads this file on every source and exports:
- `_FRAMEWORK_MAIN_PACKAGE` — the package name (e.g. `pwy-home-lab-pkg`)
- `_FRAMEWORK_MAIN_PACKAGE_DIR` — realpath-resolved absolute path to `infra/<pkg>`

A pre-existing `_FRAMEWORK_MAIN_PACKAGE` env var wins over the file, enabling per-developer
or CI overrides without touching config. `config/_framework.yaml` is the one file that
cannot itself move — it is the anchor for everything else.

In repos generated by `fw-repo-mgr`, this file is written automatically when a package
declares `is_main_package: true` in `framework_repo_manager.yaml`. See
[framework-repo-manager.md](framework-repo-manager.md#the-is_main_package-flag) for details.

Legacy aliases `_FRAMEWORK_CONFIG_PKG` and `_FRAMEWORK_CONFIG_PKG_DIR` are re-exported
by `set_env.sh` for backward compatibility and will be removed in a future release.

### Discovery pattern — three-tier lookup

All framework config lookups use this priority order (lowest → highest):

```
1. infra/_framework-pkg/_config/               framework defaults
2. infra/$_FRAMEWORK_MAIN_PACKAGE/_config/     main package (if set)
3. config/                                     ad-hoc/dev overrides (always highest)
```

`config/` stays as the top tier so it remains usable for quick per-developer overrides
without touching the named package's files.

| Tool | Discovery mechanism |
|------|-------------------|
| `framework_config.py` (`load_framework_config`) | `find_framework_config_dirs()` → three-tier order |
| `root.hcl` | `fileexists()` chain: `config/` → `_FRAMEWORK_MAIN_PACKAGE_DIR/_config/` → `_framework-pkg/_config/` |
| `packages.py` (`_fw_cfg_path`) | `config/` → `_FRAMEWORK_MAIN_PACKAGE_DIR/_config/` → `_framework-pkg/_config/` |
| `pkg-mgr/run` | `_fw_cfg()` shell function → same three-path order |
| `set_env.sh` (`_GCS_BUCKET`) | same three-path order |

### Hardcoded paths (no override support)

`config/_framework.yaml` itself is hardcoded — it is the single bootstrap anchor.

`_framework-pkg.yaml` (the version/capability file) lives in `infra/_framework-pkg/_config/`
but is not a framework config file — it is package metadata read directly by pkg-mgr as
`$_FRAMEWORK_PKG_DIR/_config/_framework-pkg.yaml`. It does not need to move.

### Current file locations

| File | Location | Category |
|------|----------|----------|
| `_framework-pkg.yaml` | `infra/_framework-pkg/_config/` | Package version/capability — not a framework config file |
| `framework_backend.yaml` | `config/` | Deployment — GCS bucket name |
| `framework_ansible_inventory.yaml` | `config/` | Deployment |
| `framework_clean_all.yaml` | `config/` | Deployment |
| `framework_config_mgr.yaml` | `config/` | Deployment — config-mgr merge settings |
| `framework_ephemeral_dirs.yaml` | `config/` | Deployment |
| `framework_external_capabilities.yaml` | `config/` | Deployment |
| `framework_repo_manager.yaml` | `infra/<main-pkg>/_config/_framework_settings/` | Deployment — fw-repo-mgr repo definitions; see [framework-repo-manager.md](framework-repo-manager.md) |
| `framework_package_management.yaml` | `config/` | Deployment — pkg-mgr external_package_dir |
| `framework_package_repositories.yaml` | `config/` | Deployment — registered repo catalog |
| `framework_pre_apply_unlock.yaml` | `config/` | Deployment |
| `framework_validate_config.yaml` | `config/` | Deployment |
| `gcp_seed.yaml` | `config/` | Deployment — GCP seed project config |
| `framework_packages.yaml` | `config/` | Deployment — package registry |
| `gcp_seed_secrets.sops.yaml` | `config/` | Deployment — GCP seed secrets |
| `waves_ordering.yaml` | `config/` | Deployment — wave definitions |

### Adding a new framework config file

- If the file is **deployment-specific** (values differ between deployments): place it in
  `config/` and load it via `load_framework_config()` or the two-path helper in the
  consuming tool.
- If the file is **framework-owned** (same for all deployments): place it in
  `infra/_framework-pkg/_config/` and load it via the same helpers (the fallback path
  covers this case automatically).
- Never add a new hardcoded single-path read unless there is a genuine bootstrap reason.
