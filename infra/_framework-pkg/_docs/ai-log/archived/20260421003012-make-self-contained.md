---
date: 2026-04-21
task: make-self-contained
plan: infra/default-pkg/_docs/ai-plans/make-self-contained.md
---

# Make `make` Self-Contained

## What was done

Added `./run --sync-packages` (calls `pkg-mgr --sync`) as the first step of `make build`,
so that a fresh `git clone` can run `make` without manually populating `_ext_packages/`.

### Changes

**`infra/default-pkg/_framework/_git_root/run`**
- Added `PKG_MGR` path constant pointing to `_framework/_pkg-mgr/run`
- Added `sync_packages()` function that calls `pkg-mgr --sync` and hard-fails on error
- Added `-Y|--sync-packages` argparse flag (`dest='sync_packages_flag'`)
- Added `sync_packages_flag` to `mode_flags` list
- Added standalone dispatch block for `--sync-packages` (before `--setup-packages`)
- Updated usage docstring

**`Makefile`**
- `build` target now calls `./run --sync-packages` before `./run --build`

## Why

After a fresh `git clone`, `infra/<pkg>` symlinks are dangling — `_ext_packages/` doesn't
exist yet. `setup_packages()` globs `infra/*/_setup/run` at call time, so dangling symlinks
caused all external package setups to be silently skipped. `pkg-mgr --sync` clones the
repos and creates the symlinks; running it first fixes the silent skip.
