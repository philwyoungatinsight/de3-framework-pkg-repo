# Plan: Ship /doit Skill and Session Cleanup

## Objective
Commit the `/doit` skill and associated CLAUDE.md/README updates created at the end of this session.

## Context
The MaaS session changes (Rocky preseed, configure-plain-hosts wave, PVE 9 docs, OVS script fixes) were already committed in `15a945b3`. The only uncommitted changes are:
- `.claude/commands/plan.md` — deleted (renamed to doit.md)
- `.claude/commands/doit.md` — new skill file
- `CLAUDE.md` — updated Planning rule to reference `/doit`
- `docs/ai-plans/README.md` — user added "/ship" step to the workflow

## Open Questions
None — ready to proceed.

## Files to Create / Modify
No code changes needed. All files exist on disk. Just stage and commit.

## Execution Order
1. Stage: `git add .claude/commands/doit.md CLAUDE.md docs/ai-plans/README.md`
2. Remove deleted: `git rm .claude/commands/plan.md`
3. Commit with appropriate message
4. Push via `~/bin/gpa`

## Verification
- `git log --oneline -3` shows the new commit
- `.claude/commands/doit.md` exists, `plan.md` does not
- `~/bin/gpa` exits 0
