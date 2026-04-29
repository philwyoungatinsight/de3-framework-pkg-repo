# GUI run script: venv setup via uv

## Summary

Added automatic Python venv creation/activation to the de3-gui `run` script. When `--deps` is invoked, the script now ensures a `.venv` exists in the app directory (created via `uv`) before installing requirements. A bad commit had accidentally deleted the `run` file entirely; it was restored with the new changes applied.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/run`** — added `_ensure_venv()` helper: checks `$VIRTUAL_ENV` first (skip if already active), requires `uv` (fails with install URL if missing), creates `.venv` in `$SCRIPT_DIR` if absent, activates it; `_deps()` now calls `_ensure_venv` and passes the absolute `$SCRIPT_DIR/requirements.txt` path to `install-requirements.sh`

## Root Cause

The `run` file was accidentally deleted by a previous commit (`72908cb`) that staged renames but also dropped the untracked `run` file from the working tree. The file had to be reconstructed from `git show HEAD~1`.

## Notes

The `install-requirements.sh` utility already detects `$VIRTUAL_ENV` and uses `uv pip install` (not `--system`) when a venv is active, so the chain works end-to-end without further changes.
