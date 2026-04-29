# Plan: Add /doit-with-watchdog Skill

## Objective

Create a new skill `.claude/commands/doit-with-watchdog.md` that runs `/doit` to execute
an ai-plan AND registers the build watchdog cron job to monitor the build while it runs.
Accepts `<plan> [polling-interval-minutes]` — the polling interval defaults to 2 minutes.
When the plan execution completes, the watchdog is torn down with `/watchdog-off`.

## Context

- `/doit` is `.claude/commands/doit.md` — executes Steps 8–10 of the doit flow (read plan,
  execute, archive, ship).
- `/watchdog` is `.claude/commands/watchdog.md` — resolves runtime paths, registers a
  `CronCreate` job at `*/2 * * * *`, and runs one immediate check.
- The polling interval in `/watchdog` is currently hardcoded as `*/2 * * * *`. The new
  skill needs to accept a user-supplied interval and convert it to a cron expression.
- Skills cannot call other skills directly; they are markdown instruction sets that Claude
  executes inline. So `/doit-with-watchdog` must inline the relevant steps from both skills
  rather than delegating.
- The plan argument is first; polling interval is second and optional (default 2).
- Cron expressions for "every N minutes": `*/N * * * *` (valid for N = 1..59).

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `.claude/commands/doit-with-watchdog.md` — create

New skill. Structure:

```
---
name: doit-with-watchdog
description: Execute an ai-plan via /doit while the build watchdog monitors the process. Usage: /doit-with-watchdog <plan-name> [polling-minutes]
---
```

**Arguments parsed from `$ARGUMENTS`:**
- First token → `PLAN_NAME` (required; kebab-case plan stem, e.g. `add-ovs-wave`)
- Second token → `POLL_MINUTES` (optional integer; default `2`)

**Steps:**

**Step 0 — Parse arguments**
Split `$ARGUMENTS` on whitespace.
- `PLAN_NAME` = first token. If empty: error and stop ("Usage: /doit-with-watchdog <plan-name> [polling-minutes]").
- `POLL_MINUTES` = second token if present and is a positive integer 1–59; otherwise default `2`.
- Derive cron expression: `CRON_EXPR="*/${POLL_MINUTES} * * * *"`

**Step 1 — Resolve runtime paths** (inlined from `/watchdog` Step 0)
Run bash to resolve `GIT_ROOT`, `_DYNAMIC_DIR`, and derive:
- `WATCHDOG_SCRIPT`, `WATCHDOG_LOG`, `WATCHDOG_REPORT`

**Step 2 — Register watchdog** (inlined from `/watchdog` Steps 1–2)
- Call `CronList`; skip registration if `build-watchdog` job already exists (note existing ID).
- If not present: call `CronCreate` with `cron: CRON_EXPR`, `recurring: true`, `durable: true`,
  and the standard watchdog prompt (with literal resolved paths substituted in).
- Report: `Watchdog registered (every POLL_MINUTES min) — job ID: <id>. Starting plan execution.`

**Step 3 — Execute the plan** (inlined from `/doit` Step 8)
Read `docs/ai-plans/${PLAN_NAME}.md`. Execute each step in "Files to Create / Modify" in
Execution Order. Verify each change before moving on. Run the Verification steps.

**Step 4 — Archive the plan and ship** (inlined from `/doit` Steps 9–10)
Move plan to `docs/ai-plans/archived/$(date +%Y%m%d%H%M%S)-${PLAN_NAME}.md`.
Write ai-log entry. Run `/ship`.

**Step 5 — Stop the watchdog** (inlined from `/watchdog-off`)
- Call `CronList`; find all jobs whose prompt contains `build-watchdog`.
- Call `CronDelete` for each. Report: `Watchdog stopped — plan complete.`

## Execution Order

1. Create `.claude/commands/doit-with-watchdog.md`

That is the only file to create. No modifications to existing files.

## Verification

```bash
# Confirm the file exists and has the correct frontmatter name
head -5 .claude/commands/doit-with-watchdog.md
# Should show: name: doit-with-watchdog
```

Manually verify: invoke `/doit-with-watchdog` with a known plan name and confirm it
registers a cron job, executes the plan, then deletes the cron job on completion.
