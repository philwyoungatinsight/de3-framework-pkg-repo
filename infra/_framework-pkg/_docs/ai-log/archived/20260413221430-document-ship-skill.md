# Document /ship Skill in claude-skills.md

## Summary

Added `/ship` documentation to `docs/claude-skills.md`. The skill existed as `.claude/commands/ship.md` but had no corresponding entry in the docs index, making it invisible to anyone reading the skills reference. Also noted that `/run-wave` section had section ordering swapped (Fix rules appeared after Test failure rule); linter auto-corrected the order.

## Changes

- **`docs/claude-skills.md`** — added `/ship` section with condensed algorithm matching the style of the existing `/run-wave` section; includes steps for README updates, ai-log writing, ai-log-summary prepend, staged commit, and push via `~/bin/gpa`

## Notes

The linter reordered the `/run-wave` section so that "Fix rules" appears before "Test failure rule" — the content was unchanged, just the subsection order swapped.
