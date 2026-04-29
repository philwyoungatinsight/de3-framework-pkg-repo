# Fix wave-mgr: update _EPHEMERAL → _RAMDISK_MGR after rename

## Summary

The `ephemeral→ramdisk` rename commit (`20ed79c`) updated `set_env.sh` to export `_RAMDISK_MGR` but missed `wave-mgr`, which still consumed the now-deleted `_EPHEMERAL` env var. This caused a `KeyError: '_EPHEMERAL'` crash on every `./run` invocation.

## Changes

- **`infra/_framework-pkg/_framework/_wave-mgr/wave-mgr`** — renamed `_EPHEMERAL_RUN` → `_RAMDISK_MGR_RUN` and updated env var lookup from `ENV['_EPHEMERAL']` to `ENV['_RAMDISK_MGR']`; updated docstring to say "ramdisk mounts" instead of "ephemeral mounts"

## Root Cause

The rename commit only updated `set_env.sh` (where the env var is exported) and the ramdisk config files, but didn't grep for all consumers of `_EPHEMERAL`. `wave-mgr` consumed the env var at module load time, so it crashed immediately before any wave logic ran.

## Notes

The fix is a straightforward variable rename — no functional change. `_RAMDISK_MGR` points to the same script (`_ramdisk-mgr/ramdisk-mgr`) that `_EPHEMERAL` previously pointed to under its old name.
