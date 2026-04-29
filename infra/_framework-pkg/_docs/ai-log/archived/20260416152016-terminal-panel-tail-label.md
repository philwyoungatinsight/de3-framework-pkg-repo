# Terminal panel shows filename when tailing

## Summary

When tailing a file (`tail_current_file` or `tail_wave_log`), the terminal panel header
now shows a short label ("tail: filename") instead of the directory path. Adds
`shell_label` as a new AppState var; the `tail_*` handlers set it after opening the
terminal; all other terminal-open paths clear it so the CWD display remains the default.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**:
  - `shell_label: str = ""` — new state var (near `shell_cwd`/`shell_initial_cmd`).
  - `tail_current_file`: sets `self.shell_label = f"tail: {p.name}"` after opening.
  - `tail_wave_log`: sets `self.shell_label = "tail: run.log"` after opening.
  - `open_shell`: clears `shell_label` on open and on close (`cwd=""`).
  - `open_ssh_terminal`: clears `shell_label` at each code path (close flush, ttyd open,
    native open, embedded open) so non-tail SSH terminal opens never show a stale label.
  - `bottom_right_panel`: terminal panel header now shows `shell_label` when non-empty,
    falling back to `shell_cwd_display` when empty.
