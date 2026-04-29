---
date: 2026-04-09
title: Move ensure_backend into framework-utils.sh; delete framework/lib/
---

## What changed

- Moved `_backend_exists` and `ensure_backend` from `framework/lib/common.sh`
  into `utilities/bash/framework-utils.sh`, where all other reusable bash
  functions live.
- Deleted `framework/lib/common.sh` (and the now-empty `framework/lib/`
  directory) — its only purpose was to source `init.sh` and expose those two
  functions.
- Updated `run` to source `utilities/bash/init.sh` directly (which sources
  `framework-utils.sh`) instead of `framework/lib/common.sh`.

## Simplifications in the moved functions

- `STACK_ROOT` variable eliminated — `ensure_backend` now uses `$_INFRA_DIR`
  (already set by `set_env.sh`, sourced transitively by `init.sh`).
- `STACK_CONFIG` variable eliminated — `_backend_exists` now calls
  `_find_component_config framework` inline (already defined in
  `framework-utils.sh`).
