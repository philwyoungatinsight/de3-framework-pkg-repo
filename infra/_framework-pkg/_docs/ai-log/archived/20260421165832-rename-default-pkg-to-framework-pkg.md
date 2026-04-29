# 20260421165832 — rename default-pkg → _framework-pkg

## What changed

Renamed `infra/default-pkg/` to `infra/_framework-pkg/` across the entire repository.

The underscore prefix follows the repo convention that `_`-prefixed names are
reserved/special. The framework package orchestrates all other packages — it is not
a domain package — so the prefix makes this clear at a glance in directory listings.

## Scope

- Directory: `infra/default-pkg/` → `infra/_framework-pkg/`
- Config file: `_config/default-pkg.yaml` → `_config/_framework-pkg.yaml`
- YAML top-level key: `default-pkg:` → `_framework-pkg:`
- Env var: `_DEFAULT_PKG_DIR` → `_FRAMEWORK_PKG_DIR` (set_env.sh + ~20 Python/bash files)
- HCL var: `DEFAULT_PKG_DIR` → `FRAMEWORK_PKG_DIR` (root.hcl + run)
- root.hcl secrets path: `default-pkg.secrets.yaml` → `_framework-pkg.secrets.yaml`
- 8 root-level symlinks (CLAUDE.md, set_env.sh, run, root.hcl, Makefile, .sops.yaml,
  README.md, .gitlab-ci.yml) updated to point to new path
- `pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`: `_modules_dir: default-pkg/_modules`
  → `_modules_dir: _framework-pkg/_modules`
- 30+ forward-facing docs updated; historical ai-log/archived docs left unchanged
- Plan archived at `_docs/ai-plans/rename-default-pkg-to-framework-pkg.md`

## Version bump

`1.3.1` → `1.4.0` (minor bump — rename is a breaking change for any external reference
to the old package name or env var)
