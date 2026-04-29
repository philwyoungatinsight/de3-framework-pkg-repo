# Fix: Tail commands use configured terminal backend; ttyd is default when available

## Summary

`tail_current_file` and `tail_wave_log` were setting `shell_cwd` and
`shell_initial_cmd` directly, bypassing the terminal backend selection entirely.
They now route through `open_ssh_terminal` so the configured backend (ttyd, native
terminal, or embedded) is used consistently. The default terminal backend is now
`ttyd` when ttyd is available, and ttyd is auto-installed in the background at
startup if it is not yet present.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**:
  - `tail_current_file`: replaced direct `shell_cwd`/`shell_initial_cmd` assignment
    with `yield from self.open_ssh_terminal(...)` — now uses the configured backend.
  - `tail_wave_log`: same fix as `tail_current_file`.
  - `terminal_backend` state default: changed from `"embedded"` to
    `"ttyd" if _TTYD_AVAILABLE else "embedded"`.
  - `on_load` backend fallback: same ttyd-first default for users with no saved config.
  - `_try_install_ttyd_background()`: new function — runs the platform apt/brew install
    command in a daemon thread at startup when ttyd is not found. Silently ignores
    failures; logs success/failure to the GUI log. On success, re-detects backends so
    the next page reload picks up ttyd automatically.
  - `on_load`: calls `_try_install_ttyd_background()` when `_TTYD_AVAILABLE` is False.

## Root Cause

`tail_current_file` and `tail_wave_log` were written before the terminal backend
system existed, and were never updated to use it. They wrote directly to state vars
that only the embedded xterm.js path reads, so tailing always used the embedded
terminal regardless of the user's backend setting.

## Notes

- The auto-install runs `sudo apt install -y ttyd` on Linux (or `brew install ttyd`
  on macOS). It requires passwordless sudo to succeed non-interactively.  Failure is
  silent — the user can always click the "Install ttyd" button in the terminal settings
  panel to run it manually in the embedded terminal.
- After a successful background install, the user must reload the page — `_TTYD_AVAILABLE`
  is a module-level flag set at import time and is not re-evaluated live.
