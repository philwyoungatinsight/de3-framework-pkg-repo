# Consolidate top-level dirs into infra/default-pkg

Moved all framework code, config, docs, scripts, and utilities from top-level directories
into `infra/default-pkg/` under `_`-prefixed subdirectories, leaving only entry-points
(`run`, `Makefile`, `set_env.sh`, `root.hcl`, `CLAUDE.md`, `.sops.yaml`, `.gitlab-ci.yml`)
at the repo root.

## What moved

| From | To |
|---|---|
| `framework/clean-all/` | `infra/default-pkg/_clean_all/` |
| `framework/ephemeral/` | `infra/default-pkg/_ephemeral/` |
| `framework/generate-ansible-inventory/` | `infra/default-pkg/_generate-inventory/` |
| `framework/unit-mgr/` | `infra/default-pkg/_unit-mgr/` |
| `framework/pkg-mgr/` | `infra/default-pkg/_pkg-mgr/` |
| `utilities/` | `infra/default-pkg/_utilities/` |
| `docs/` | `infra/default-pkg/_docs/` |
| `scripts/ai-only-scripts/` | `infra/default-pkg/_scripts/ai-only/` |
| `scripts/human-only-scripts/` | `infra/default-pkg/_scripts/human-only/` |
| `config/*.yaml` | `infra/default-pkg/_config/` |
| `config/tech-debt/` | `infra/default-pkg/_config/tech-debt/` |

## Code changes

- `set_env.sh`: updated `_UTILITIES_DIR`, `_CONFIG_TMP_DIR`, `_GENERATE_INVENTORY`,
  ephemeral script path, and validate-config.py invocation.
- `run` (Python): replaced `FRAMEWORK_DIR` constant with `DEFAULT_PKG_DIR`; updated
  `GENERATE_INVENTORY`, `NUKE_ALL`, `INIT_SH` path constants.
- `framework/ephemeral/run` (now `_ephemeral/run`): updated sibling `EPHEMERAL_SH` and
  `FRAMEWORK_YAML` paths.
- `framework/pkg-mgr/run` (now `_pkg-mgr/run`): updated `PKG_REPOS_CFG`,
  `FRAMEWORK_PKGS_CFG`, and inline Python `_gcs_bucket()` path.
- `framework/unit-mgr/unit_mgr/main.py` (now `_unit-mgr/`): `_read_framework_config()`
  now searches `infra/default-pkg/_config/framework.yaml` first, falling back to
  `config/framework.yaml` for legacy repos.
- `scripts/human-only-scripts/setup-ephemeral-dirs/run`: updated ephemeral/run path.
- `scripts/ai-only-scripts/query-unifi-switch/run`, `upgrade-routeros/run`: updated
  generate-ansible-inventory inventory path.
- `scripts/ai-only-scripts/maas-power-control/run`: replaced hardcoded GIT_ROOT playbook
  path with `$SCRIPT_DIR/playbook.yaml`.
- `CLAUDE.md`: all `docs/`, `scripts/`, and `utilities/` path references updated.
