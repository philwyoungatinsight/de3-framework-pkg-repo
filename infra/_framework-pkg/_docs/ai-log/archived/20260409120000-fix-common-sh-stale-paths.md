---
date: 2026-04-09
title: Fix stale STACK_ROOT and STACK_CONFIG in framework/lib/common.sh
---

## What changed

`framework/lib/common.sh` had two bugs left over from the repo refactor that
moved the file from `scripts/wave-scripts/default/lib/` to `framework/lib/`:

1. **`STACK_ROOT`** — was computed 4 levels up (`../../../..`), which resolved
   to `/home/pyoung` instead of the repo root. The comment even preserved the
   old path hierarchy (`lib → default → wave-scripts → scripts → lab_stack`).
   Fixed to 2 levels up (`../..`: `lib → framework → repo root`).

2. **`STACK_CONFIG`** — called `_find_component_config terragrunt_lab_stack`,
   but no `terragrunt_lab_stack.yaml` exists. The framework config now lives at
   `config/framework.yaml` (key: `framework:`). Fixed to
   `_find_component_config framework`.

## Impact

`ensure_backend` (called by `./run --ensure-backend` and at the start of
`./run --build`) would fail or operate on the wrong directory tree. The
`_backend_exists` check read the wrong config file, and the bootstrap
`find "$STACK_ROOT/infra"` searched under `/home/pyoung/infra` (nonexistent).
