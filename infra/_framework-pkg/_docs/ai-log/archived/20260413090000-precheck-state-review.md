# maas-machines-precheck: state table + normalization

## Summary

The `maas-machines-precheck` pre-wave playbook for `maas.lifecycle.new` now shows a
live MaaS state table for all configured machines at the start of every wave run, and
normalizes machines that are in states that would prevent the wave from making progress.

## Problem

Running `tg -a` on a `maas.lifecycle.new` machine unit blindly triggers the 300s
auto-import timeout if the machine is in a bad MaaS state (e.g. Deploying from a
previous aborted run, Allocated from a partially-completed run). There was no way to
quickly see machine states or fix them before the wave hooks fired.

## Changes

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-precheck/playbook.yaml`

**New: `_all_machines` list in Play 1**
All power types (amt, smart_plug, manual, ipmi, redfish) are now included in a single
`_all_machines` list used for the state review play. Previously only AMT and smart-plug
specific lists were built.

**New: Play 2 — "Review MaaS machine states and normalize bad states"**
Runs on `maas_server` before the AMT reachability and smart-plug cycling plays.

1. Reads all machines from MaaS (`maas <user> machines read`)
2. Prints a state table: every configured machine shows its MaaS status or "NOT IN MAAS"
3. Normalizes states that block the wave:
   - `Commissioning` → `abort` (falls to Failed commissioning; commission unit retries)
   - `Testing` → `abort` (falls to Failed testing; commission unit retries)
   - `Deploying` → `abort` (returns to Ready; deploy unit redeploys)
   - `Allocated` → `release` (returns to Ready)
   - `Failed deployment` → `release` (returns to Ready)
4. Reports which machines were aborted/released
5. Warns (but does not fail) for machines in `Broken` state

States left untouched (already usable):
- `New`, `Failed commissioning`, `Failed testing`, `Ready`, `Deployed`, `NOT IN MAAS`

### `CLAUDE.md`

Updated pre-wave playbook rule to permit idempotent state normalization as an
exception to the "only CHECK" rule. Normalization returns machines to a clean baseline;
the wave itself runs the lifecycle. Arbitrary orchestration and multi-step recovery
are still not permitted.

## State table example output

```
=== maas.lifecycle.new Machine States ===
ms01-01  | NOT IN MAAS   (power: amt)
ms01-03  | New           (power: amt)
nuc-1    | Deploying     (power: smart_plug)

Aborted nuc-1 (was Deploying)
```
