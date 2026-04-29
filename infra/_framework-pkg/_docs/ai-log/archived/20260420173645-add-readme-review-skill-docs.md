# Add `/readme-review` Skill Documentation

## Summary

Added `/readme-review` to the Claude Code skills command file and documented it in `claude-skills.md`. The skill processes one pending README per invocation using a tracker file, updating stale docs and marking rows complete.

## Changes

- **`.claude/commands/readme-review.md`** — new skill definition: reads tracker, assesses README against current code, updates if stale, marks tracker row, commits
- **`infra/default-pkg/_docs/claude-skills.md`** — added `/readme-review` section documenting the algorithm and README writing rules

## Notes

Skill inserted alphabetically before `/ship` in the doc.
