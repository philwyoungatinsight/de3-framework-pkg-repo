# fw-repos-gui-stack-dir-fix — Fix GUI reading wrong state file

**Date**: 2026-04-25
**Commit**: `da3adda` (de3-runner)

## Problem

The fw-repos Mermaid viewer was always reading de3-runner's state file instead of the
deployment repo's state file. This meant `pwy-home-pkg` never appeared and backend data
was never shown — both exist only in pwy-home-lab-pkg's state file at
`config/tmp/fw-repos-visualizer/known-fw-repos.yaml`.

**Root cause**: The GUI `run` script determines its git root via `git rev-parse --show-toplevel`.
Because `infra/de3-gui-pkg` in pwy-home-lab-pkg is a symlink, following the symlink resolves
to de3-runner's physical directory — so `GIT_ROOT` was always de3-runner's root. The script
then sourced de3-runner's `set_env.sh`, which unconditionally set `_STACK_DIR="$_GIT_ROOT"`,
overwriting any deployment context, and the GUI's Python module read `_STACK_DIR` at import
time to locate the state file.

## Fix

**`infra/_framework-pkg/_framework/_git_root/set_env.sh`** — changed line:
```bash
# Before
export _STACK_DIR="$_GIT_ROOT"
# After
export _STACK_DIR="${_STACK_DIR:-$_GIT_ROOT}"
```
This makes `set_env.sh` idempotent with respect to `_STACK_DIR`: it only sets it when the
caller hasn't already established a deployment context.

**`infra/de3-gui-pkg/_application/de3-gui/run`** — same change:
```bash
# Before
export _STACK_DIR="$_GIT_ROOT"
# After
export _STACK_DIR="${_STACK_DIR:-$_GIT_ROOT}"
```

## How it works now

1. User sources pwy-home-lab-pkg's `set_env.sh` from within that repo (git root resolves
   to pwy-home-lab-pkg) → `_STACK_DIR=/home/pyoung/git/pwy-home-lab-pkg` is set.
2. User launches the GUI via `./run -r` (inside pwy-home-lab-pkg's de3-gui-pkg symlink tree).
3. `run` script calls `git rev-parse --show-toplevel` → de3-runner (symlink physical dir).
4. `. set_env.sh` sources de3-runner's set_env.sh; `_STACK_DIR` is already set → **not overwritten**.
5. `export _STACK_DIR="${_STACK_DIR:-$_GIT_ROOT}"` → no-op.
6. GUI Python reads `_STACK_DIR=/home/pyoung/git/pwy-home-lab-pkg` → correct state file.

## Restart required

The running GUI process has the old `_STACK_DIR` baked in. To pick up the fix:
```bash
# In pwy-home-lab-pkg:
source "$(git rev-parse --show-toplevel)/set_env.sh"
infra/de3-gui-pkg/_application/de3-gui/run --stop
infra/de3-gui-pkg/_application/de3-gui/run --run
```
