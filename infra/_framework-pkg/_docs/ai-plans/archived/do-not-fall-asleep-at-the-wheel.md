# Plan: Do Not Fall Asleep at the Wheel

## Objective

Set up a build watchdog that actively checks every 5 minutes whether the wave run is
progressing, whether it has failed, and what MaaS machine states are. Output must be
visible to Claude at all times during a build. Claude must never run a build in the
background and then go silent or poll with broken conditions.

## Problem

Claude repeatedly starts builds in the background, then enters broken polling loops that
either exit immediately or silently fail. The user has no visibility into whether Claude
is actually watching anything. This wastes time.

## Solution

Two pieces:

### 1. `scripts/ai-only-scripts/build-watchdog/run`

A script that runs a tight loop (every 30s) and prints a one-line status of:
- Is the wave runner process alive?
- What's the tail of the latest wave log? (last error or last TASK line)
- What are the MaaS machine states?

Claude uses the `Monitor` tool to stream this in real-time when a build is running.

### 2. CronCreate job every 5 minutes

A cron job that runs `build-watchdog/check` (one-shot version) and appends to
`~/.build-watchdog.log`. Claude checks this log periodically.

## Files to Create

### `scripts/ai-only-scripts/build-watchdog/run` — create

```bash
#!/usr/bin/env bash
# Build watchdog — runs a continuous status loop while a build is in progress.
# Usage: ./run [LOG_FILE]
# Prints one-line status every 30 seconds until killed.

set -euo pipefail
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"

SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
MAAS_HOST="10.0.10.11"
INTERVAL=30

_maas_states() {
  ${SSH} ubuntu@"${MAAS_HOST}" \
    "maas admin machines read 2>/dev/null | python3 -c \"
import json,sys
machines=json.load(sys.stdin)
parts=[f\\\"{m['hostname']}={m['status_name']}({'!' if m['status_name'] not in ['New','Ready','Deployed','Commissioning','Deploying'] else ''})\\\".replace('(!)','!') for m in machines]
print(','.join(parts))
\"" 2>/dev/null || echo "maas-unreachable"
}

_build_status() {
  # Is the wave runner process running?
  if pgrep -f "run --build" >/dev/null 2>&1; then
    RUNNING="BUILD:RUNNING"
  else
    RUNNING="BUILD:STOPPED"
  fi

  # Last significant line from latest log
  LATEST_LOG=$(ls -t ~/.run-waves-logs/latest/*.log 2>/dev/null | head -1)
  if [[ -n "${LATEST_LOG}" ]]; then
    LAST_LINE=$(tail -5 "${LATEST_LOG}" 2>/dev/null | grep -E "TASK|PLAY|ERROR|FAILED|fatal|ok=|changed=" | tail -1 | sed 's/^[[:space:]]*//' | cut -c1-80)
  else
    LAST_LINE="no-log"
  fi

  MAAS="${1:-}"
  echo "[$(date '+%H:%M:%S')] ${RUNNING} | maas: ${MAAS} | log: ${LAST_LINE}"
}

echo "=== Build watchdog started (${INTERVAL}s interval) ==="
while true; do
  MAAS=$(_maas_states)
  _build_status "${MAAS}"
  sleep "${INTERVAL}"
done
```

### `scripts/ai-only-scripts/build-watchdog/check` — create

One-shot version (used by cron):

```bash
#!/usr/bin/env bash
# One-shot build status check — appends to ~/.build-watchdog.log
set -euo pipefail
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"

SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
MAAS_HOST="10.0.10.11"
LOG="$HOME/.build-watchdog.log"

MAAS=$(${SSH} ubuntu@"${MAAS_HOST}" \
  "maas admin machines read 2>/dev/null | python3 -c \"
import json,sys
machines=json.load(sys.stdin)
print(','.join(f\\\"{m['hostname']}={m['status_name']}\\\" for m in machines))
\"" 2>/dev/null || echo "maas-unreachable")

if pgrep -f "run --build" >/dev/null 2>&1; then
  RUNNING="RUNNING"
else
  RUNNING="STOPPED"
fi

LATEST_LOG=$(ls -t ~/.run-waves-logs/latest/*.log 2>/dev/null | head -1)
if [[ -n "${LATEST_LOG}" ]]; then
  LAST_ERR=$(grep -E "ERROR|FAILED|fatal" "${LATEST_LOG}" 2>/dev/null | tail -1 | cut -c1-100)
else
  LAST_ERR="no-log"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] build=${RUNNING} maas=${MAAS} last_err=${LAST_ERR:-none}" >> "${LOG}"
```

## Execution Order

1. Create `scripts/ai-only-scripts/build-watchdog/run`
2. Create `scripts/ai-only-scripts/build-watchdog/check`
3. Register cron job: `build-watchdog/check` every 5 minutes
4. Test: run `./run` and verify output, run `./check` and verify log
5. Commit scripts and cron registration

## How Claude Must Use This Going Forward

**Starting a build:**
1. Start build: `nohup ./run --build ... > /path/to/build.log 2>&1 &`
2. Immediately run: `Monitor` on the watchdog: `./scripts/ai-only-scripts/build-watchdog/run`
3. NEVER let the build run unmonitored for more than 5 minutes

**When a gate fails:**
1. Watchdog output shows `BUILD:STOPPED` or `FAILED` in log tail
2. Immediately read the failing log: `~/.run-waves-logs/latest/wave-<name>-*.log`
3. Diagnose → fix → kill any stale build → restart

**Recovery from silent failure:**
1. Check `~/.build-watchdog.log` — shows last 5-min status
2. Check `pgrep -f "run --build"` — is the build actually running?
3. Check `~/.run-waves-logs/latest/run.log` — what happened?

## Verification

```bash
# Verify watchdog script works
bash scripts/ai-only-scripts/build-watchdog/run &
# Should print status line every 30s with machine states

# Verify check script works
bash scripts/ai-only-scripts/build-watchdog/check
tail -1 ~/.build-watchdog.log
# Should show one-line status with timestamp
```
