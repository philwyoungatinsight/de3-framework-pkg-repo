---
date: 2026-04-19
session: ephemeral-dirs-automation
---

# Ephemeral dirs automation

Implemented `framework.ephemeral_dirs` in `config/framework.yaml` so directories
can be declared as RAM-backed without hardcoding paths anywhere.

## What was done

- Added `_EPHEMERAL_DIR=$_DYNAMIC_DIR/ephemeral` to `set_env.sh`
- Added `framework.ephemeral_dirs` section to `config/framework.yaml` (list of
  `{env_var, size_mb}` entries)
- Created `framework/make-ephemeral-dirs/run` — reads the YAML, resolves env vars,
  calls `framework/ephemeral/ephemeral.sh` for each entry; skips in CI/non-interactive
- Created `framework/make-ephemeral-dirs/README.md`
- Updated `scripts/human-only-scripts/setup-ephemeral-dirs/run` to delegate to the
  framework script instead of hardcoding the path

## To add more ephemeral dirs in future

Add an entry to `framework.ephemeral_dirs` in `config/framework.yaml`:

```yaml
- env_var: _SOME_OTHER_DIR
  size_mb: 128
```

Then export that var from `set_env.sh` and add it to the `mkdir -p` line.
