# pkg-mgr: Auto-Migrate Inclusion Method Changes

## Summary

`pkg-mgr --sync` now automatically migrates repos when their `inclusion_method` changes
in config. Previously, switching `local_copy` → `linked_copy` errored out, and switching
`linked_copy` → `local_copy` silently did nothing (leaving the symlink in place).

## Changes

- **`infra/default-pkg/_framework/_pkg-mgr/run`** — updated `_ensure_cloned` to detect
  and handle both migration directions:
  - **`local_copy` → `linked_copy`**: detects that `_ext_packages/<slug>` is a real
    directory; performs a full `git clone` to `$external_package_dir/<slug>`, removes the
    shallow clone dir, then creates the symlink
  - **`linked_copy` → `local_copy`**: detects that `_ext_packages/<slug>` is a symlink;
    removes it, does a fresh `git clone --depth=1` in its place, and prints a note that
    the external full clone is now unused (user removes manually if desired)

## Notes

- Migration is triggered automatically by `--sync` whenever the on-disk state doesn't
  match the configured method — no manual cleanup required
- For `local_copy` → `linked_copy`: any uncommitted local changes in the shallow clone
  are lost (unlikely in practice; `local_copy` is intended as read-only)
- For `linked_copy` → `local_copy`: the external full clone (`$HOME/.de3-ext-packages/<slug>`)
  is left in place and just noted as unused
