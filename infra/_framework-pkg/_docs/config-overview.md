# Config Overview

How configuration flows from YAML files through the framework into Terraform.

---

## Entry point: `set_env.sh`

Source this file before any `terragrunt`, `ansible`, or utility command:

```bash
source "$(git rev-parse --show-toplevel)/set_env.sh"
```

On every source it:
1. Exports all path variables (`_GIT_ROOT`, tool paths, dynamic dirs, `_GCS_BUCKET`)
2. Creates runtime directories under `config/tmp/dynamic/`
3. Runs **config-mgr generate** — pre-merges all package YAML into `$_CONFIG_DIR` so
   Terragrunt can read config fast without shelling out to `sops` at every invocation

---

## Two kinds of config files

### Package config — what each Terraform unit gets

Every package keeps its config alongside its code:

```
infra/<pkg>/_config/
├── <pkg>.yaml               # public config   (top-level key: <pkg>:)
└── <pkg>_secrets.sops.yaml  # encrypted secrets (top-level key: <pkg>_secrets:)
```

Config is indexed by unit path. `root.hcl` collects all ancestor-path entries for a
unit's path, merges them deepest-wins, and exposes the result as `local.up` in every
`terragrunt.hcl`. See [framework/config-files.md](framework/config-files.md) for the
full merge mechanics.

### Framework config — how the framework tools themselves operate

Framework settings (state backend, package registry, wave ordering, etc.) live in
`_framework_settings/` directories. The lookup uses a 3-tier priority:

```
1. config/                                                  highest — ad-hoc dev overrides
2. infra/<config-package>/_config/_framework_settings/      deployment package overrides
3. infra/_framework-pkg/_config/_framework_settings/        lowest — framework defaults
```

The "main package" is declared in `config/_framework.yaml` at the repo root:

```yaml
_framework:
  main_package: pwy-home-lab-pkg
```

`set_env.sh` reads this file and exports `_FRAMEWORK_MAIN_PACKAGE` (the package name) and
`_FRAMEWORK_MAIN_PACKAGE_DIR` (its realpath-resolved absolute path). See
[`_framework_settings/README.md`](../_config/_framework_settings/README.md) for the
full lookup rules.

---

## Key framework config files

All of the following live in
`infra/<config-package>/_config/_framework_settings/` for the active deployment
(falling back to `infra/_framework-pkg/_config/_framework_settings/` as defaults):

| File | Purpose |
|------|---------|
| `framework_backend.yaml` | GCS state bucket — read by `set_env.sh` to set `_GCS_BUCKET` |
| `waves_ordering.yaml` | Authoritative ordered wave list — read by `./run` and `clean-all` |
| `framework_packages.yaml` | Package registry with config_source chains |
| `framework_config_mgr.yaml` | Config-mgr merge method and output mode |
| `framework_ansible_inventory.yaml` | Ansible inventory generation settings |

---

## Reading and writing config with `$_CONFIG_MGR`

`$_CONFIG_MGR` is the CLI for all programmatic config access. Use it instead of editing
YAML directly — it routes writes through `config_source` chains and centralises all
SOPS calls.

| Subcommand | What it does |
|------------|-------------|
| `generate` | Pre-merge all package YAML into `$_CONFIG_DIR` (run automatically on every `source set_env.sh`) |
| `get <unit-path>` | Print the merged `config_params` for a unit path |
| `set <unit-path> <key> <value>` | Write a `config_params` key to the correct source YAML (add `--sops` for secrets) |
| `set-raw <pkg> <dot.key.path> <value>` | Write an arbitrary key in a package YAML, not scoped to `config_params` (add `--sops` for secrets) |
| `move <src> <dst>` | Rename `config_params` keys (delegates to unit-mgr's `migrate_config_params`) |

All subcommands regenerate `$_CONFIG_DIR` after writing so the next `terragrunt` run
sees the update immediately.

---

## SOPS encryption

`.sops.yaml` at the repo root defines encryption rules for all
`*_secrets.sops.yaml` files under `infra/`. The default rule matches
`infra/[^/]+/_config/.*\.sops\.yaml$` and encrypts with the PGP keys listed there.

CLAUDE.md documents the correct SOPS usage patterns — never use `>` or `tee` on `.sops.yaml` files.

---

## Further reading

- [framework/config-files.md](framework/config-files.md) — full config merge mechanics,
  package variables (`vars:`), ancestor-path inheritance, `p_package` derivation
- [framework/package-system.md](framework/package-system.md) — what a package owns,
  how to add a new package, external packages and `_ext_packages/`
