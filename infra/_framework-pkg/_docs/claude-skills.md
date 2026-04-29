# Claude Code Skills

Project-specific slash commands for Claude Code, defined in `.claude/commands/`. Invoked as `/command-name` in any Claude Code session opened in this repo.

---

## `/doit <task-description-or-plan-name>`

Separates the research/planning phase from the coding phase to avoid mid-coding context compaction. Explores the codebase, writes a detailed plan to `docs/ai-plans/`, surfaces decisions for the user, then clears context and executes.

**Two modes:**
- `/doit add OVS wave after maas.lifecycle.deployed` — new task: explore → plan → confirm → execute
- `/doit add-ovs-wave` — resume existing plan (kebab-case stem): skip straight to execution

### Algorithm

```
1. Read docs/ai-screw-ups/README.md           — mandatory session start check

2. Parse $ARGUMENTS
   - If kebab-case stem and docs/ai-plans/<stem>.md exists → jump to step 8 (resume)
   - Otherwise → treat as task description and continue

3. Explore codebase — read all relevant code, configs, and docs in infra/<pkg>/_docs/
   Identify what exists vs. what needs to change; understand conventions and dependencies

4. Write plan to docs/ai-plans/<kebab-name>.md with sections:
     Objective | Context | Open Questions | Files to Create/Modify |
     Execution Order | Verification
   Commit the plan file immediately

5. Review plan for correctness against actual code:
     - File paths exist (for modifications)
     - Naming conventions match codebase
     - No hardcoded values, no CLAUDE.md rule violations

6. Surface open questions:
     - If questions exist: STOP and wait for user answers
     - If none: announce "No open questions. Ready to clear context and execute."

   ← user runs /clear here to reset the context window ←

8. Read the plan file, execute each file change in Execution Order,
   verify each change, then run Verification steps.

9. Archive plan: mv docs/ai-plans/<name>.md docs/ai-plans/archived/<timestamp>-<name>.md

10. Write ai-log entry, then /ship to commit and push.
```

### Why the context clear matters

Claude compacts long conversations mid-coding when the context fills up. Compaction during a multi-file edit causes Claude to lose track of the plan. Clearing context after planning (but before coding) gives the coding phase a clean window with the written plan as its sole guide.

### Plan file format

```markdown
# Plan: <Task Title>

## Objective
## Context
## Open Questions
## Files to Create / Modify
### `path/to/file` — <create|modify>
## Execution Order
## Verification
```

---

## `/doit-with-watchdog <plan-name> [polling-minutes]`

Executes an existing ai-plan (like `/doit <plan-name>`) while running the build watchdog cron job for the duration. Registers the watchdog before execution and stops it after `/ship` completes.

**Usage:**
```
/doit-with-watchdog add-ovs-wave        # 2-minute polling (default)
/doit-with-watchdog add-ovs-wave 5      # 5-minute polling
```

The plan file (`docs/ai-plans/<plan-name>.md`) must already exist — create it first with `/doit`.

### Algorithm

```
0. Parse $ARGUMENTS → PLAN_NAME (required), POLL_MINUTES (default 2, range 1–59)
   Derive CRON_EXPR="*/POLL_MINUTES * * * *"
   Confirm docs/ai-plans/${PLAN_NAME}.md exists

1. Resolve runtime paths via git rev-parse + set_env.sh:
     WATCHDOG_SCRIPT, WATCHDOG_LOG, WATCHDOG_REPORT

2. CronList → register watchdog if absent (CronCreate, durable=true, recurring=true)
   Skip if already running — never create a duplicate

3. Execute the plan (Steps 8–10 of /doit):
     Read plan file → execute each change in Execution Order → verify → Verification steps

4. Archive plan: mv docs/ai-plans/<name>.md docs/ai-plans/archived/<timestamp>-<name>.md

5. Write ai-log entry, run /ship

6. CronList → CronDelete all jobs whose prompt contains "build-watchdog"
   Report: "Watchdog stopped — plan complete."
```

---

## `/run-wave <N>`

Runs wave N, verifies every phase passed, fixes automation on failure, and retries until the wave succeeds. Never advances past a failing wave.

### Algorithm

```
1. /clear                          — reset conversation context before starting
2. read docs/ai-screw-ups/README.md  — mandatory session start check
3. ./run --list-waves               — confirm wave name for number N
4. source set_env.sh && ./run -n N  — run the wave

5. VERIFY all phase logs in ~/.run-waves-logs/latest/:
     wave-<name>-precheck.log       — pre-wave Ansible playbook
     wave-<name>-apply.log          — OpenTofu apply
     wave-<name>-inventory.log      — inventory update
     wave-<name>-test-playbook.log  — post-wave Ansible test

   For each present log, scan for failure indicators:
     ERROR: | FAILED! | failed=[^0] in PLAY RECAP | fatal: | command failed | rc=1

6. Produce verdict table (precheck / apply / inventory / test-playbook):
     PASS   = log present, no failure indicators
     FAIL   = log present, failure indicator found  → quote exact error line
     N/A    = log absent (phase not configured for this wave)

7. If all phases PASS  → "WAVE VERDICT: PASS — safe to advance to wave N+1." STOP.

8. If any phase FAILS  → "WAVE VERDICT: FAIL" then:
     a. Read the full failing log to identify root cause
     b. Fix the automation (see rules below)
     c. Rerun: source set_env.sh && ./run -n N
     d. Go back to step 5
     Repeat until verdict is PASS.
```

### Test failure rule

A failing `test-playbook` means the **infrastructure** is in the wrong state — not the test. The test is the signal.

- Do not change the test to make the wave pass.
- If the test appears to be checking the wrong condition for this wave, stop and explain the discrepancy to the user. Wait for explicit confirmation before touching the test configuration.

### Fix rules — enforced on every failure, no exceptions

| Forbidden (monkey-patching) | Correct fix |
|-----------------------------|-------------|
| Edit DB directly (`psql`, `UPDATE maasserver_*`) | Use MaaS CLI API (`maas machine release`, `maas machine delete`) |
| Force MaaS status by writing to DB | Delete machine + `tofu state rm` + re-run wave |
| Patch Terraform state by hand | `tofu state rm` the broken resource; let automation recreate |
| Change `test_ansible_playbook` → `test_action: reapply` to silence a failing test | Fix the infrastructure the test is checking |
| Remove or weaken an Ansible test assertion | Fix the root cause; only change test with explicit user confirmation |
| Run one-off scripts to push config that automation manages | Fix the playbook or Terraform module |
| Hardcode values in scripts or playbooks | Read from YAML config via `config_base` |

---

## `/watchdog [session-name]`

Ensures the build watchdog cron job is registered. Idempotent — safe to run any number of times without creating duplicates. Run this at the start of any session where a long-running build will happen.

Optional argument: `session-name` — the Claude Code session the watchdog should run in (informational; cron always fires in the current session).

### Algorithm

```
0. Resolve runtime paths via git rev-parse + set_env.sh:
     WATCHDOG_SCRIPT = <GIT_ROOT>/scripts/ai-only-scripts/build-watchdog/check
     WATCHDOG_LOG    = <_DYNAMIC_DIR>/watchdog/build-watchdog.log
     WATCHDOG_REPORT = <_DYNAMIC_DIR>/watchdog-report/watchdog_report.yaml

1. CronList → scan for any job whose prompt contains "build-watchdog"

2a. If found  → report job ID and schedule; do nothing else
2b. If absent → CronCreate with schedule "*/2 * * * *", durable=true, recurring=true
    Prompt embeds literal resolved paths (shell vars don't expand at cron fire time)

3. Run one immediate check:
     bash <WATCHDOG_SCRIPT>
   Show last 3 lines of <WATCHDOG_LOG>

4. Read <WATCHDOG_REPORT>:
   - user_input_needed=false → show last 5 log lines + MaaS machine states; fix if broken
   - user_input_needed=true  → surface user_input_message and wait for response
```

### What the watchdog does

Every 2 minutes the cron job fires and:
- Runs `scripts/ai-only-scripts/build-watchdog/check` (one-shot status check)
- Appends a status line to `<_DYNAMIC_DIR>/watchdog/build-watchdog.log`
- Writes `<_DYNAMIC_DIR>/watchdog-report/watchdog_report.yaml` with current state
- If `build=STOPPED` when it shouldn't be: reads failure logs, diagnoses, and reports

---

## `/watchdog-off`

Stops all registered build watchdog cron jobs so no further periodic checks fire. Safe to run when no watchdog is active. Run `/watchdog` to re-enable.

### Algorithm

```
1. CronList → find all jobs whose prompt contains "build-watchdog"
2. CronDelete each one
3. Report: "Watchdog stopped — deleted N job(s): <ids>"
   If none found: "Watchdog is not running — nothing to stop."
```

---

## `/work-on-maas`

Kills any running full build, starts a MaaS-only build (`./run -b -w "*maas*"`), registers the watchdog, and actively monitors until all MaaS waves succeed or one fails.

### Algorithm

```
1. Kill any running full build (pkill -f "run -b")
   Skip restart if a *maas*-only build is already running

2. Start MaaS-only build in background:
     nohup ... ./run -b -w "*maas*" > ~/.run-waves-logs/run.log 2>&1 &

3. Register watchdog — run /watchdog (idempotent)

4. Monitor every ~2 minutes:
     - ls -lt ~/.run-waves-logs/latest/*.log
     - tail -20 ~/.run-waves-logs/run.log
     - Query MaaS machine states via SSH to 10.0.10.11

   Gate checkpoints (read log when each wave starts):
     maas.servers.all            → apply log: MaaS API up
     maas.lifecycle.new          → precheck: machine enrolled; apply: auto-import runs
     maas.lifecycle.commissioning → precheck: plug bounce + AMT PXE; test: all Ready
     maas.lifecycle.deploying    → precheck: allocate + AMT deploy boot
     maas.lifecycle.deployed     → test-playbook: all Deployed

5. On failure:
     Read full failing log → diagnose root cause → fix automation → commit → restart skill
     If machine stuck: check AMT standby; bounce smart plug if AMT unreachable

6. On success (maas.lifecycle.deployed test-playbook passes):
     Report final MaaS machine states → run /ship
```

---

## `/annihilate-maas-machine <machine-name>`

Deterministically wipes a MaaS machine — deletes it from MaaS and removes all TF state — so waves rebuild it from scratch. The correct response to any stuck or broken machine.

**Usage**: `/annihilate-maas-machine ms01-02`

The machine name is the leaf directory name under `machines/` in the stack (same as the MaaS hostname after enrollment).

### Algorithm

```
1. Parse $ARGUMENTS → MACHINE name (ask user if empty)

2. Read current state (in parallel):
     - SSH to MaaS: get system_id, status_name, power_state for this machine
     - gsutil ls: find all GCS TF state files under machines/<MACHINE>/

3. Pre-delete state transitions (if machine exists in MaaS):
     Deployed / Allocated   → maas machine release; wait up to 60s for Ready
     Commissioning / Deploying / Testing → maas machine abort; wait 30s
     New / Ready / Failed* / Broken → no pre-step needed

4. Delete from MaaS:
     maas machine delete $SYSTEM_ID
   Confirm machine no longer appears in maas machines read

5. Wipe all GCS TF state under this machine:
     gsutil -m rm -r gs://.../machines/<MACHINE>/
   Confirm gsutil ls returns nothing

6. Report annihilation summary + next steps (re-run waves or make)
```

### Notes

- YAML config is not touched — the machine will be recreated with the same config on the next wave run.
- The `auto-import` before_hook handles re-enrollment from scratch when the machine unit is re-applied.
- `maas machine release/abort/delete` are the only permitted direct MaaS API calls here (lifecycle transitions, not config overrides).

---

## `/readme-review`

Works through `infra/_framework-pkg/_docs/readme-maintenance/README-tracker.md` one README at a time. Each invocation handles exactly one `pending` row — reads the surrounding code, updates the README if stale, marks the tracker row `updated` or `ok`, and commits. Run repeatedly until all rows are reviewed.

### Algorithm

```
1. Read tracker → find first row where Status = pending (Priority 1 first)
   If none remain → "All READMEs reviewed — tracker complete." STOP.

2. Read the README file + surrounding directory (source files, run scripts,
   playbook.yaml, main.tf, Makefile) to understand current state

3. Assess: compare README against current code
   - Update if: describes removed/renamed things, omits key behaviour,
     references stale hardcoded values, too brief to be useful
   - Leave as-is (ok) if: accurate and complete

4. Edit tracker row: set Status → updated or ok, set Last Reviewed → YYYY-MM-DD

5. Stage and commit only the touched files:
     git add README-tracker.md [+ readme path if changed]
     commit: "docs: review README for <short directory name>"

6. Report: reviewed path, status + one-sentence reason, next pending path
```

### README writing rules

- Bullet lists for procedural steps; non-obvious details in appendix sections
- Describe how the code works — do not narrate changes
- No hardcoded IPs/names — reference config keys instead

---

## `/ship`

Ships a work session: updates READMEs, writes an ai-log entry + ai-log-summary entry, stages and commits, then pushes.

### Algorithm

```
1. git diff HEAD + git status + git log --oneline -10  — understand what changed

2. Update README.md for each modified directory that contains a Makefile.
   Also check infra/<pkg>/_docs/README.md for modified packages.
   Describe current working state — do NOT narrate changes.

3. Write ai-log entry:
     docs/ai-log/$(date +%Y%m%d%H%M%S)-<short-kebab-description>.md
   Sections: Summary | Changes (file-by-file) | Root Cause (if fix) | Notes

4. Prepend entry to docs/ai-log-summary/ai-log-summary.md
   Format: ## YYYY-MM-DD — <Title> + 3–6 bullet points, reverse-chronological

5. Archive ai-log files older than 3 days into docs/ai-log/archived/ (git mv)

6. Stage specific files (not git add -A); commit with HEREDOC message:
     <type>(<scope>): <description>
     Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

7. Push:  ~/bin/gpa
```

### Report on completion

- File count and commit hash
- Which READMEs were updated (or "none needed")
- ai-log filename created
- Push result
