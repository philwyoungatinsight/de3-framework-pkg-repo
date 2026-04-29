# Plan: Automate Ephemeral Dir Setup from framework.yaml

## Goal

Allow `framework.yaml` to declare which `_DYNAMIC_DIR` subdirectories should be
RAM-backed, and have a single script mount them all — idempotently, in the right order,
without manual intervention.

## Current State

- `framework/ephemeral/ephemeral.sh` — mounts one dir as RAM drive; exits 0 if already mounted
- `set_env.sh` exports `_EPHEMERAL_DIR=$_DYNAMIC_DIR/ephemeral` and `mkdir -p`s it
- `scripts/human-only-scripts/setup-ephemeral-dirs/run` calls `ephemeral.sh` for `_EPHEMERAL_DIR`
- No automation; user must run `setup-ephemeral-dirs/run` manually after login

## Proposed Design

### 1. Declare dirs in `framework.yaml`

Add an `ephemeral_dirs` section:

```yaml
framework:
  ephemeral_dirs:
    - env_var: _EPHEMERAL_DIR
      size_mb: 64        # optional, default 64
```

Each entry names the **env var** (not a hardcoded path) that holds the directory.
Path resolution happens at runtime by reading the env var — no hardcoded paths in YAML.

### 2. `framework/make-ephemeral-dirs/run`

A new script that:
1. Sources `set_env.sh`
2. Reads `framework.ephemeral_dirs` from `config/framework.yaml` (Python or `yq`)
3. For each entry, expands the env var and calls `ephemeral.sh --path <resolved> [--size N]`
4. Skips entries whose env var is unset (warns, does not fail)

```
framework/make-ephemeral-dirs/
  run          ← executable script
  README.md
```

### 3. Update `scripts/human-only-scripts/setup-ephemeral-dirs/run`

Replace the hardcoded call with a delegation to `framework/make-ephemeral-dirs/run`.
The human-only script becomes a thin wrapper — useful for manual one-shot invocation
and for documentation purposes.

### 4. Optional: hook into set_env.sh

`set_env.sh` currently calls `validate-config.py` on every source. A similar
`make-ephemeral-dirs/run` call there would auto-mount on every new shell — but only if:

- The call is made conditional: skip if not on Linux/macOS, skip if not interactive
- The sudo prompt from `mount` is acceptable in that context (it is, since `ephemeral.sh`
  exits 0 immediately when already mounted — sudo is only hit once per boot)

Decision: **defer this hook** until there is a real need. The human-only script is
sufficient for now and avoids surprising sudo prompts in CI/automated contexts.

## Files to Create/Modify

| File | Action |
|------|--------|
| `config/framework.yaml` | Add `ephemeral_dirs` section |
| `framework/make-ephemeral-dirs/run` | Create — reads YAML, mounts all dirs |
| `framework/make-ephemeral-dirs/README.md` | Create |
| `scripts/human-only-scripts/setup-ephemeral-dirs/run` | Update to delegate to framework script |

## Open Questions

1. **`yq` vs Python**: `validate-config.py` already uses Python + PyYAML — prefer
   Python for consistency and macOS compat. Use `yq` only if it is already a declared
   dependency.
2. **`size_mb` default**: 64 MB is fine for secrets. Make it overridable per-entry.
3. **CI guard**: `make-ephemeral-dirs/run` should detect non-interactive / CI
   environments (`CI=true`, no TTY) and skip rather than hanging on a sudo prompt.
