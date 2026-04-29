# pkg-mgr status: Rich Table Output

## Summary

Rewrote `pkg-mgr status` to display a structured, color-coded table matching the visual
style of `./run --list-waves`. Also committed `framework_package_management.yaml` which
was created in the previous session but not staged.

## Changes

- **`infra/default-pkg/_framework/_pkg-mgr/run`** — replaced the plain-text `_cmd_status`
  output with a three-section ANSI/unicode table: (1) config header showing
  `default_inclusion_method` and `external_package_dir`, (2) a repos summary table with
  Repo/Method/Source/Clone/#pkgs columns, (3) a packages table with #/Package/Repo/Method/
  Version/S columns. Version is read from `_provides_capability` in each package's config
  YAML (fault-tolerant — try/except, so a missing or malformed config yields an empty cell
  rather than crashing). The repos table now also takes a 5th arg (`PKG_REPOS_CFG`).

- **`infra/default-pkg/_config/framework_package_management.yaml`** — committed for the
  first time (was untracked after previous session).

## Notes

- `de3-gui-pkg` has no `_provides_capability` in its config YAML; the fault-tolerant read
  shows an empty Version cell — correct behaviour.
- Colors only render when stdout is a TTY; `NO_COLOR` env var suppresses them (standard).
