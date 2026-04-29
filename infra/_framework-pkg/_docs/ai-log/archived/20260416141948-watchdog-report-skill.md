# Watchdog Report File — Add Step 4 to /watchdog Skill

## Summary

Updated the `/watchdog` skill to write a structured YAML report to
`$_DYNAMIC_DIR/watchdog-report/watchdog_report.yaml` after each run. The report captures
build status, assessment, description, and a `user_input_needed` flag so that stuck builds
surface directly to the user rather than silently accumulating in log files. Also bumped
the cron schedule from every 1 minute to every 2 minutes.

## Changes

- **`.claude/commands/watchdog.md`** — Added Step 4 (Write watchdog report): archives any
  existing report, reads last 10 lines of `~/.build-watchdog.log` plus latest wave log,
  writes YAML report via Write tool (atomic), evaluates `user_input_needed` heuristic, and
  either continues silently or prompts the user. Updated cron prompt to include the same
  report-writing instructions so periodic agents also produce reports. Changed schedule
  from `*/1 * * * *` to `*/2 * * * *`.

- **`docs/ai-plans/archived/20260416141938-watchdog-report.md`** — Plan archived after
  successful execution.

## Notes

- Report path is hardcoded to the resolved `$_DYNAMIC_DIR` value
  (`/home/pyoung/git/pwy-home-lab/config/tmp/dynamic/watchdog-report/watchdog_report.yaml`)
  so the cron agent doesn't need to source `set_env.sh`.
- `user_input_needed: true` is set on three heuristics: unexpected STOPPED build, repeated
  same ERROR in last 10 log lines (stuck wave), or `maas-unreachable` in last line.
- The Write tool is used (not bash redirect) for the same atomicity reason as the SOPS rule.
