# GUI run script: use _activate_python_locally from python-utils.sh

## Summary

Replaced the hand-rolled `_ensure_venv` function in the de3-gui `run` script with the
shared `_activate_python_locally` utility from `_utilities/bash/python-utils.sh`. The
call is now at the global scope of the script so every subcommand (`--run`, `--build`,
`--test`, etc.) automatically gets a valid venv with requirements installed, not just
`--deps`.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/run`** — removed custom `_ensure_venv`;
  removed requirements install from `_deps`; added global `uv` check + source of
  `python-utils.sh` + `_activate_python_locally "$SCRIPT_DIR"` before the dispatch
  loop so venv setup runs unconditionally on every invocation
- **`infra/de3-gui-pkg/_application/de3-gui/README.md`** — updated `--deps` / `make deps`
  descriptions to reflect that they are now no-ops (setup happens at startup)

## Root Cause

The previous approach only called `_ensure_venv` inside `_deps`. Since `make` runs each
target in a separate shell, the venv activated during `deps` was not active when `run`
or `build` started. Running `./run --run` directly also skipped venv setup entirely,
causing `reflex` to be missing from PATH.

## Notes

`_activate_python_locally` also handles stale venvs (path mismatch after directory move)
by detecting the embedded `VIRTUAL_ENV=` path in `bin/activate` and recreating if stale.
This is a robustness improvement over the previous custom code.
