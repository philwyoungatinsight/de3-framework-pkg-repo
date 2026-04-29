# Fix: tail terminals skip bash --login; watchdog check writes YAML report

## Summary

Two unrelated fixes shipped together. First: tail terminals (waves → tail, file viewer →
tail) now pass `login=False` to `_start_ttyd`, preventing `~/.bash_profile` from running
and eliminating the screen blink caused by a `clear` in the login profile. The
`wave_tail_cmd` config is simplified to a plain `tail -99f` (no restart loop). Second:
the build-watchdog `check` script now writes a structured YAML report itself, removing
the need for the Claude agent to write it.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**:
  - `_start_ttyd`: added `login: bool = True` param; when `login=False` and a cmd is
    given, uses `bash -c` instead of `bash --login -c`, skipping profile sourcing.
  - `open_ssh_terminal`: added `login: bool = True` param, threads it through to
    `_start_ttyd`.
  - `tail_current_file` and `tail_wave_log`: pass `login=False` to avoid the blink.

- **`infra/de3-gui-pkg/_config/de3-gui-pkg.yaml`**:
  - `wave_tail_cmd`: simplified from a `while true; do timeout 2s tail...; sleep 0.5; done`
    restart loop to just `tail -99f "$HOME/.run-waves-logs/latest/run.log"`. The loop
    caused a visual blink every 2 seconds when tail restarted; ttyd keeps the session
    alive so the restart loop is unnecessary.

- **`scripts/ai-only-scripts/build-watchdog/check`**:
  - Now writes the structured YAML watchdog report itself (atomic via tmp file). The
    Claude agent that reads this script's output no longer needs to write the report.

- **`.claude/commands/watchdog.md`**:
  - Updated to reflect that the check script writes the report; Step 4 now just reads
    the existing report rather than constructing and writing it.

## Root Cause

`bash --login -c "CMD; exec bash"` sources `~/.bash_profile` before running CMD. If
the profile calls `clear` (common in interactive shell setups), the terminal blinks.
The restart loop in `wave_tail_cmd` added a second blink source: `timeout 2s` kills tail
every 2 seconds and the loop restarts it, momentarily blanking the screen.
