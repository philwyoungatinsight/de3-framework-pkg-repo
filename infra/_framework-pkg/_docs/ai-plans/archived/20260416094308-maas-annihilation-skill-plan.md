# Plan: maas-annihilation-skill-plan

## Objective

Create a `/annihilate-maas-machine` skill that deterministically resets a MaaS machine
to a clean slate — deleting it from MaaS and wiping its TF state — so the next wave run
recreates it from scratch with no residual state. This is the correct answer to any
stuck/broken MaaS machine. It ends the monkey-patching loop.

## Context

### Current pain

Every time ms01-02 commissioning fails, the temptation is to `terragrunt state rm`,
`terragrunt import`, or call `maas machine abort/release` by hand. These leave the
automation in a partially-executed, untested state that diverges from what a clean wave
run would produce. The divergence compounds across retries until the state is incoherent.

The correct operation is: **delete the machine from MaaS, delete every TF state file
under that machine's path, and re-run the affected waves.** This is what `maas-recovery.md`
says. This skill makes it a one-command operation.

### What "annihilate" must do (in order)

1. **Release if needed** — MaaS refuses to delete Allocated/Deployed machines. Release first.
2. **Abort if needed** — MaaS refuses to delete Commissioning/Deploying/Testing machines. Abort first.
3. **Delete from MaaS** — `maas <profile> machine delete <system_id>`.
4. **Wipe ALL GCS TF state** under the machine's prefix — every lifecycle sub-unit
   (`commission/`, `commission/ready/`, `allocated/`, `deploying/`, `deployed/`) and the
   machine unit itself.
5. **Remove any stale `.tflock`** files on those same paths.
6. Report what was deleted so the user can re-run the correct waves.

### TF state path pattern

GCS bucket: `seed-tf-state-pwy-homelab-20260308-1700`
Machine state prefix: `pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/<machine-name>/`

All sub-paths under that prefix are safe to wipe — they are all lifecycle
sub-units (`commission/`, `commission/ready/`, etc.) that must be rebuilt by
the wave anyway.

### Skill inputs

The skill takes one required argument: the machine name as it appears in:
- The TF unit path (`machines/ms01-02`)
- The YAML config key

It looks up the MaaS system_id from TF state (or MaaS API) rather than requiring
the user to know it.

### What it does NOT do

- Does NOT change YAML config — config is source of truth and stays untouched
- Does NOT run `make` or any wave — the user decides what to re-run after
- Does NOT delete GCS state for other machines — scoped tightly to the named machine

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `.claude/commands/annihilate-maas-machine.md` — create

A new Claude skill (slash command). Invoked as `/annihilate-maas-machine <machine-name>`.

Content:

```markdown
---
name: annihilate-maas-machine
description: Deterministically wipe a MaaS machine — delete from MaaS + remove all TF state — so waves rebuild it from scratch. The correct answer to any stuck/broken machine.
---

# /annihilate-maas-machine — Delete MaaS Machine + Wipe TF State

Usage: `/annihilate-maas-machine <machine-name>`

Example: `/annihilate-maas-machine ms01-02`

The machine name is the leaf directory name under `machines/` in the stack — same as
the hostname in MaaS after enrollment.

---

## Step 1 — Confirm argument

Parse `$ARGUMENTS`. If empty, ask the user which machine to annihilate before continuing.
Machine name = `$ARGUMENTS` (e.g. `ms01-02`).

---

## Step 2 — Read current state

Run these in parallel:

```bash
# MaaS system_id and current status
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "maas maas-admin machines read 2>/dev/null | python3 -c \"
import json,sys
for m in json.load(sys.stdin):
    if m.get('hostname') == '$MACHINE':
        print('system_id=' + m['system_id'])
        print('status=' + m['status_name'])
        print('power_state=' + m.get('power_state','?'))
\""

# GCS TF state files under this machine
gsutil ls -r "gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/$MACHINE/" 2>/dev/null
```

Report what was found. If machine is not in MaaS at all, skip to Step 4 (still wipe TF state).

---

## Step 3 — Pre-delete state transitions (if machine exists in MaaS)

Based on current MaaS status:

**If Deployed or Allocated:**
```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "maas maas-admin machine release $SYSTEM_ID 2>&1"
# Wait up to 60s for Released/Ready
```

**If Commissioning, Deploying, or Testing:**
```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "maas maas-admin machine abort $SYSTEM_ID 2>&1"
# Wait up to 30s for abort to complete
```

**If New, Ready, Failed*, Broken:** — no pre-step needed, delete directly.

---

## Step 4 — Delete from MaaS

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "maas maas-admin machine delete $SYSTEM_ID 2>&1"
```

Confirm deletion by checking machine no longer appears in `maas machines read`.

If machine was not in MaaS: skip this step and note it.

---

## Step 5 — Wipe all GCS TF state under this machine

```bash
GCS_PREFIX="gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/$MACHINE"

# List what will be deleted
gsutil ls -r "$GCS_PREFIX/" 2>/dev/null

# Delete all state files and locks
gsutil -m rm -r "$GCS_PREFIX/" 2>/dev/null || echo "No GCS state found — already clean"
```

Confirm with `gsutil ls "$GCS_PREFIX/"` returning nothing.

---

## Step 6 — Report and next steps

Print a summary:

```
=== Annihilation complete: $MACHINE ===
MaaS: deleted (was $STATUS, system_id=$SYSTEM_ID)
  — OR —
MaaS: not found (already absent)

TF state wiped:
  $GCS_PREFIX/default.tfstate
  $GCS_PREFIX/commission/default.tfstate
  ... (all found paths)
  — OR —
TF state: none found (already clean)

Next steps:
  Re-run waves: maas.lifecycle.new → maas.lifecycle.commissioning → ...
  Or run: make   (if full build is appropriate)
```

---

## Notes

- This skill calls `maas machine release/abort/delete` — these are the ONLY permitted
  direct MaaS API calls (lifecycle transitions, not config overrides). They are safe here
  because annihilation is the explicit goal.
- YAML config is not touched — the machine will be recreated with the same config on the
  next wave run.
- The `auto-import` before_hook in `machines/$MACHINE/terragrunt.hcl` handles re-enrollment
  from scratch when the machine unit is re-applied.
```

---

### `docs/ai-plans/maas-annihilation-skill-plan.md` — this file

The plan itself (already being written).

## Execution Order

1. Create `.claude/commands/annihilate-maas-machine.md` with the skill content above.
2. Commit.
3. Test by running `/annihilate-maas-machine ms01-02`.

## Verification

After running `/annihilate-maas-machine ms01-02`:
- `maas maas-admin machines read` does not contain ms01-02
- `gsutil ls -r gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-02/` returns nothing
- Re-running `maas.lifecycle.new` wave recreates the machine cleanly
