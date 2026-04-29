# Ephemeral Dir: Skip Creation When size_mb=0

## Summary

Added support for `size_mb: 0` in `framework_ephemeral_dirs.yaml` to opt out of ephemeral
RAM-drive setup for a directory. When `size_mb` is 0, the `_ephemeral/run` script now skips
that entry entirely — the directory is not created and no RAM disk is mounted. The
`_EPHEMERAL_DIR` entry was updated to `size_mb: 0` to disable it.

## Changes

- **`infra/_framework-pkg/_framework/_ephemeral/run`** — added early-continue guard when `size_mb == 0` so `ephemeral.sh` is never called and `mkdir -p` never runs for that path

## Notes

The check is placed before the `env_var` path-resolution check so the skip message is clear
and no filesystem side effects occur at all when `size_mb: 0`.
