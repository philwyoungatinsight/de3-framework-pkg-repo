# Add /annihilate-maas-machine Skill

## Summary

Created the `/annihilate-maas-machine` slash command skill — a one-command operation that
deterministically deletes a stuck/broken MaaS machine and wipes all its GCS TF state so
the next wave run recreates it from scratch. This ends the monkey-patching loop (terragrunt
import/state-rm, manual maas abort, ad-hoc TF var overrides) that had been accumulating
during ms01-02 commissioning failures.

## Changes

- **`.claude/commands/annihilate-maas-machine.md`** — new skill; 6-step operation: confirm
  arg → read MaaS + GCS state → pre-delete transitions (release/abort) → delete from MaaS →
  wipe all GCS TF state under `machines/<name>/` prefix → report summary and next steps
- **`docs/ai-plans/archived/20260416094308-maas-annihilation-skill-plan.md`** — plan
  archived after execution

## Root Cause (context)

Every commissioning failure tempted direct state manipulation instead of the correct
delete-automate-recreate flow. The annihilation skill makes the correct path the easy path:
one command, deterministic, auditable.

## Notes

- The skill uses `sudo /usr/bin/snap run maas` (not bare `maas`) to match how the MaaS
  snap is invoked on the server.
- YAML config is never touched — machine is rebuilt from the same config on next wave run.
- The GCS wipe targets `machines/<name>/` and all sub-paths (commission/, commission/ready/,
  allocated/, deploying/, deployed/) — every lifecycle unit under that machine.
