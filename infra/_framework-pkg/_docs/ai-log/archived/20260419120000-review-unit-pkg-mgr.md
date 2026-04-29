# review-unit-pkg-mgr — 2026-04-19

## What was done

Fixed four bugs and updated two READMEs in `framework/unit-mgr` and `framework/pkg-mgr`.

### Bug 1 — `sops_secrets.py` same-package move: eliminated vulnerability window

`migrate_secrets()` for a same-package move previously did two SOPS writes:
write 1 deleted old keys from the file; write 2 added renamed keys. A kill between
them would permanently lose secrets. Fixed by skipping write 1 for same-package move
and instead updating `src_data` in-memory before a single combined write.

### Bug 2 — `config_yaml.py` `_rename_keys_inplace`: dead branch removed

`_rename_keys_inplace(cfg, old_keys, new_keys)` checked `if k in new_keys` where `k`
is always an old key — the branch always evaluated False. Rewrote the function to accept
a single `old_to_new: dict[str, str]` mapping and updated the call site to build it
explicitly. Both code paths (ruamel and pyyaml) are now a clean one-liner.

### Bug 3 — `pkg-mgr/run` rename warning: `_gcs_bucket` called 3× → 1×

In the `--skip-state` warning block of `_cmd_rename`, `$(_gcs_bucket)` was called once
per `echo` line (3 subprocesses). Cached into `warn_bucket` before the echoes.

### Dead code — `main.py` `external_outbound` category

`scan_dependencies()` never produces `"external_outbound"` refs (the scanner skips
references pointing outside `src`). Removed the dead filter variable and its log line.

### README fixes

- `unit-mgr/README.md`: removed the "External outbound" row from the Phase 2 category table.
- `pkg-mgr/README.md`: collapsed 8-item rename phase list to 7 — items 2 and 3 were a
  single atomic code phase (one `git mv` + `_rename_pkg_yaml_keys`).

## Files changed

- `framework/unit-mgr/unit_mgr/sops_secrets.py`
- `framework/unit-mgr/unit_mgr/config_yaml.py`
- `framework/unit-mgr/unit_mgr/main.py`
- `framework/pkg-mgr/run`
- `framework/unit-mgr/README.md`
- `framework/pkg-mgr/README.md`
- `docs/ai-plans/archived/20260419120000-review-unit-pkg-mgr.md` (plan archived)
