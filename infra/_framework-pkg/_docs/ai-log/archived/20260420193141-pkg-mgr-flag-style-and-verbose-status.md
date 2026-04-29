# pkg-mgr: Flag-style CLI and Verbose Status

## Summary

Changed `pkg-mgr` from a subcommand-style CLI (`pkg-mgr sync`) to a flag-style CLI
(`pkg-mgr --sync`) matching the top-level `./run` script convention. Added
`-V|--status-verbose` which shows the same table as `--status` but with an additional
"Path" column showing the resolved absolute path of each package. Updated the GUI to use
the new flag names.

## Changes

- **`infra/default-pkg/_framework/_pkg-mgr/run`** — replaced positional subcommand dispatch
  with `--flag` parsing loop; added `_usage` function; `_cmd_status` now accepts optional
  `--verbose` arg that adds a "Path" column (resolved `os.path.realpath`) to the packages
  table; `-V|--status-verbose` invokes this mode

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — updated 3 call
  sites: `"sync"` → `"--sync"`, `"remove-repo"` → `"--remove-repo"`,
  `[mode, src, dst]` → `[f"--{mode}", src, dst]` for rename/copy operations

## Notes

- Short flags: `-S` status, `-V` verbose status, `-s` sync, `-c` clean, `-C` clean-all,
  `-A` add-repo, `-i` import, `-r` remove, `-l` list-remote
- All extra args (positional and `--dry-run` / `--skip-state` / `--with-state`) are
  collected into PASS array and forwarded unchanged to command functions
