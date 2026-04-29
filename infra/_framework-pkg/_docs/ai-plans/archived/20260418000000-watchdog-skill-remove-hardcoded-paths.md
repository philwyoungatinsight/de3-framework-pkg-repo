# Plan: Remove Hardcoded Paths from /watchdog Skill

## Goal

Replace all hardcoded absolute paths in `.claude/commands/watchdog.md` with paths
derived at runtime using `git rev-parse --show-toplevel` + `set_env.sh`.

## Problem

The skill currently has four hardcoded references to the old repo path
`/home/pyoung/git/pwy-home-lab/...`:

1. The cron prompt `bash` call (wrong repo name — cron job silently fails)
2. The cron prompt `cat` call for the report file
3. Step 3 `bash` call
4. Step 4 `cat` call

Additionally, the log path is referenced throughout as `~/.build-watchdog.log` but
the actual log lives at `$_DYNAMIC_DIR/watchdog/build-watchdog.log`.

## No Changes Needed

- `watchdog-off.md` — contains no paths
- `scripts/ai-only-scripts/build-watchdog/check` — already uses `git rev-parse --show-toplevel` correctly

## Changes: `.claude/commands/watchdog.md`

### 1. Add path-resolution step (before the session-argument step)

Insert a new **Step 0** that Claude executes via Bash:

```bash
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"
echo "GIT_ROOT=${GIT_ROOT}"
echo "DYNAMIC_DIR=${_DYNAMIC_DIR}"
echo "WAVE_LOGS_DIR=${_WAVE_LOGS_DIR}"
```

Store results as `GIT_ROOT`, `DYNAMIC_DIR`, `WAVE_LOGS_DIR`.

Derive and store:
- `WATCHDOG_SCRIPT="${GIT_ROOT}/scripts/ai-only-scripts/build-watchdog/check"`
- `WATCHDOG_LOG="${DYNAMIC_DIR}/watchdog/build-watchdog.log"`
- `WATCHDOG_REPORT="${DYNAMIC_DIR}/watchdog-report/watchdog_report.yaml"`

Renumber the old Step 0 (session argument parsing) to **Step 0.5**.

### 2. Fix Step 3 bash call

Replace:
```
bash /home/pyoung/git/pwy-home-lab/scripts/ai-only-scripts/build-watchdog/check
```
With:
```
bash "${WATCHDOG_SCRIPT}"
```

Replace `~/.build-watchdog.log` log tail with `${WATCHDOG_LOG}`.

### 3. Fix Step 4 cat call

Replace:
```
cat /home/pyoung/git/pwy-home-lab/config/tmp/dynamic/watchdog-report/watchdog_report.yaml
```
With:
```
cat "${WATCHDOG_REPORT}"
```

### 4. Fix cron prompt (critical)

The cron prompt is stored text that fires later — shell variables won't expand at fire
time. Instruct Claude to **substitute the resolved value of `GIT_ROOT`** into the prompt
string before passing it to `CronCreate`. The stored prompt must contain the literal
resolved path, not a variable reference.

Replace both occurrences of the old hardcoded path in the prompt block:
- `bash /home/pyoung/git/pwy-home-lab/scripts/ai-only-scripts/build-watchdog/check`
  → resolved path, e.g. `bash /home/pyoung/git/de3/scripts/ai-only-scripts/build-watchdog/check`
- `/home/pyoung/git/pwy-home-lab/config/tmp/dynamic/watchdog-report/watchdog_report.yaml`
  → resolved path, e.g. `/home/pyoung/git/de3/config/tmp/dynamic/watchdog-report/watchdog_report.yaml`

Also fix `~/.build-watchdog.log` in the cron prompt to the resolved `WATCHDOG_LOG` path.

### 5. Fix all remaining `~/.build-watchdog.log` references

Anywhere the skill text says `~/.build-watchdog.log` (report output, status messages),
replace with `${WATCHDOG_LOG}` (or the resolved path in the cron prompt).

## Open Questions

None — plan is fully specified.
