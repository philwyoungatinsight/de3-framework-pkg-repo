# AI Log — maas-lifecycle-gate: comprehensive pre/post gate checks for all MaaS lifecycle waves

**Date**: 2026-04-15  
**Plan**: `docs/ai-plans/maas-snafu-10.md`

## What was done

Implemented comprehensive pre AND post gate checks for every `maas.lifecycle.*` wave, replacing
the single `maas-lifecycle-sanity` playbook with a unified parameterized gate system.

### Files created

- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml`
  — The shared gate playbook, parameterized by `_MAAS_GATE_WAVE` and `_MAAS_GATE_MODE` env vars.
  Two plays: localhost (load config, build machine list, read TF state from GCS), then maas_region
  (read live MaaS state, PRE-mode BMC queries + annihilation, gate evaluation, fail on any failure).

- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/run`
  — Shared runner (same boilerplate as other wave scripts).

- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/amt-query.py`
  — Copied verbatim from maas-lifecycle-sanity (wsman BMC power state query).

- 11 wrapper run scripts (one per wave:mode):
  `maas-lifecycle-gate-new-post`, `maas-lifecycle-gate-commissioning-pre/post`,
  `maas-lifecycle-gate-ready-pre/post`, `maas-lifecycle-gate-allocated-pre/post`,
  `maas-lifecycle-gate-deploying-pre/post`, `maas-lifecycle-gate-deployed-pre/post`
  Each sets `_MAAS_GATE_WAVE` and `_MAAS_GATE_MODE` and execs the shared gate runner.

### Files modified

- `infra/maas-pkg/_config/maas-pkg.yaml`
  — Updated all 6 `maas.lifecycle.*` wave definitions:
  - Added `test_ansible_playbook` to all 6 waves (previously 0 had POST gates)
  - Replaced `pre_ansible_playbook: maas/maas-lifecycle-sanity` with wave-specific gate wrappers
  - `maas.lifecycle.new`: kept `maas-machines-precheck` as PRE; added `maas-lifecycle-gate-new-post`
  - All other waves: gate-pre replaces sanity; gate-post is new

### Gate check matrix

Each gate check is per (wave, mode) combination:

| Check | What | Waves checked |
|-------|------|--------------|
| TF-1  | system_id ≠ placeholder | all (new:post onward) |
| TF-2  | TF system_id matches MaaS | all |
| MAAS-1 | machine enrolled in MaaS | all |
| MAAS-2 | power_type matches config | all |
| MAAS-3 | hardware inventory > 0 NICs | ready:post, allocated:*, deploying:pre, deployed:* |
| MAAS-4 | status in allowed set | varies by wave |
| MAAS-5 | not in failed/broken states | all |
| MAAS-6 | exact status match | ready:post=Ready, allocated:post=Allocated, deploying:pre=Allocated, deployed:post=Deployed |
| BMC-on | BMC power on (PRE only) | commissioning:post, deploying:pre, deploying:post |
| NET-1  | SSH port 22 open | deployed:post only |

### Annihilation

Preserved exactly from `maas-lifecycle-sanity`: machines in `Commissioning/Testing/Deploying`
with BMC off/unreachable, OR power_type mismatch → annihilate (delete from MaaS + wipe GCS state)
→ FAIL so wave stops. All PRE-mode gates carry the full annihilation logic.

### Key design decisions

1. **BMC queries are PRE-mode only**: POST mode leaves `_bmc_state = {}`. BMC-on gate check only
   fires when `_bmc_state` actually has data (`if bmc and ...`), avoiding false failures in POST.
2. **PRE mode queries ALL AMT/smart_plug machines** (not just transitional-state ones) so that
   `deploying:pre` can verify Allocated machines are powered on before deployment starts.
3. **Standby restoration** (bounce smart plug before AMT query) retained from sanity check, but
   only runs for machines in transitional MaaS states to avoid unnecessary plug bounces.

## Why

The incident (maas-snafu-10) showed that annihilating machines and exiting success allows the
commissioning apply to run against `placeholder-system-id` TF state. `trigger-commission.sh`
silently skips placeholders, writing the placeholder back to state. Downstream waves then poll
a non-existent machine forever. Four gate checks would have stopped this immediately:
- POST on new: TF-1 fails (placeholder still in state)
- PRE on commissioning: TF-1 fails before apply
- POST on commissioning: MAAS-4 fails (machine still in New, not Commissioning)
- PRE on ready: TF-1 fails before apply

The fix is defense-in-depth: every wave transition is now verified, not assumed.
