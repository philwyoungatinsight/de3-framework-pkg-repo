# Rename /plan Command to /doit

## Summary

The `/plan` skill command was renamed to `/doit` to avoid collision with the built-in
`/plan` name used by the Claude Code Plan agent. CLAUDE.md updated to reference `/doit`.
`docs/ai-plans/README.md` got a minor addition noting that `/ship` is called at the end
of execution.

## Changes

- **`.claude/commands/plan.md`** — deleted (was the `/plan` skill definition)
- **`.claude/commands/doit.md`** — new file with identical content (renamed to `/doit`)
- **`CLAUDE.md`** — updated Planning convention line to reference `/doit` and describe
  the full workflow (plan → surface questions → clear context → execute)
- **`docs/ai-plans/README.md`** — added `- Comment and Commit the code (/ship)` to
  the Goal section's skill workflow list
