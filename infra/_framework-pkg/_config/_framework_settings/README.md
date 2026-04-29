# `_framework_settings/` — Framework Defaults

This directory contains the default values for all framework config files
(`framework_*.yaml`). It is the lowest-priority tier — values here are used
only when no override exists in the deployment package or in `config/`.

## Lookup order (lowest → highest priority)

1. `infra/_framework-pkg/_config/_framework_settings/`  ← **this directory**
2. `infra/<config-package>/_config/_framework_settings/` — deployment overrides (set via `config/_framework.yaml`)
3. `config/`                                             — ad-hoc per-developer overrides

## Overrides are per-file, not per-directory

Each framework config file is resolved independently. Only the files you place in
a higher-priority tier take effect — missing files fall back through the chain to
the framework defaults here. You do not need to copy every file; only override the
ones you need to change.

## To override a file for your deployment

Copy the file into `infra/<your-package>/_config/_framework_settings/` and edit it.
Declare your package as the config package in `config/_framework.yaml`:

```yaml
_framework:
  config_package: <your-package-name>
```

## Important: only two packages are ever consulted

The framework only reads `_config/_framework_settings/` from exactly two packages:
`_framework-pkg` (this package) and whichever package is declared in
`config/_framework.yaml`. Any other package that happens to have a
`_config/_framework_settings/` directory is ignored.
