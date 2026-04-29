# Plan: MaaS Lifecycle Walkthrough README

## Objective

Create a comprehensive step-by-step walkthrough document at
`infra/maas-pkg/_docs/walkthrough.md` that walks through the full MaaS lifecycle
from scratch, with two runs: first using the Ubuntu test VM (`pxe-test-vm-1`), then
the Rocky 9 physical machine (`ms01-02`). Each step pauses to show expected output
and verify state before proceeding.

The document is semi-manual: the user runs one wave at a time, checks the output at
each pause, and confirms before continuing. This makes it both a learning resource and
a runbook for careful prod deploys.

## Context

### MaaS architecture

Three VMs on Proxmox:
- **maas-db-1** (10.0.10.12): PostgreSQL
- **maas-region-1** (10.0.10.11): region controller + API + web UI
- **maas-rack-1** (10.0.10.13 / 10.0.12.2): rack controller + DHCP/PXE

SSH jump for provisioning VLAN (10.0.12.0/24):
```bash
ssh -J ubuntu@10.0.10.11 ubuntu@<machine-provisioning-ip>
```

### Six lifecycle waves (in order)

| Wave | What it does |
|---|---|
| `maas.lifecycle.new` | Power-cycle → PXE enlist → import to TF state → set hostname + power config |
| `maas.lifecycle.commissioning` | Trigger commissioning (PXE into ephemeral env, gather HW inventory) |
| `maas.lifecycle.ready` | Poll until Ready; set static provisioning IP |
| `maas.lifecycle.allocated` | Allocate machine; pre-set osystem for non-Ubuntu |
| `maas.lifecycle.deploying` | Trigger OS deployment |
| `maas.lifecycle.deployed` | Poll until Deployed; SSH verify; test playbook |

Pre-playbooks (`pre_ansible_playbook`) run before each wave's Terraform apply.
Test playbooks (`test_ansible_playbook`) run after Terraform apply succeeds.

### Two machines covered

**Ubuntu test VM** (`pxe-test-vm-1`): Proxmox VM, no physical hardware. Power type:
proxmox. Deploys Ubuntu 24.04 (noble). Simple baseline — no AMT, no smart plug.

**Rocky 9 physical** (`ms01-02`): MinisForum MS-01. AMT at 10.0.11.11.
Smart plug at 192.168.2.105 (`mgmt_wake_via_plug: true`). Deploys Rocky Linux 9.
Demonstrates AMT + smart plug bounce pattern.

### Key commands used throughout

```bash
# Wave runner
source set_env.sh && ./run --wave <name> --build

# Check machine state
maas $MAAS_PROFILE machine read <system_id> | jq '.status_name, .power_state'

# Check all machines
maas $MAAS_PROFILE machines list | jq '.[] | {hostname, status_name, power_state}'

# Wave logs
ls ~/.run-waves-logs/latest/
cat ~/.run-waves-logs/latest/wave-maas.lifecycle.new-apply.log

# GUI: see live status in Waves panel
```

### What "showing results" means

Each step includes:
1. The exact command to run
2. A **PAUSE** section with expected log output (trimmed)
3. A **VERIFY** section with a command to check MaaS state and expected output
4. A **CONTINUE** decision: what to do if state is correct vs. unexpected

### Known issues captured in the walkthrough

- Smart plug + AMT: plug bounce first, then AMT wakes (~120s after AC restored)
- `mgmt_wake_via_plug: true` means AMT has no standby power when off; bounce is mandatory
- Rocky 9 custom image (`osystem=custom`, `distro_series=rocky9`): `hwe_kernel` must
  be cleared before deploy (automation handles this but walkthrough shows it)
- Commissioning typically takes 10–15 min (two PXE boots); deployment 5–20 min
- `maas-00-install-lldpd` custom script runs in Phase 3 to fix LLDP socket missing error

## Open Questions

None — ready to proceed.

## Files to Create / Modify

---

### `infra/maas-pkg/_docs/walkthrough.md` — create

The main document. Structure:

```
# MaaS Lifecycle Walkthrough

## Prerequisites
  - MaaS server VMs running (maas-db-1, maas-region-1, maas-rack-1)
  - set_env.sh sourced
  - How to get MAAS_PROFILE and verify API
  
## Part 1 — Ubuntu Test VM (pxe-test-vm-1)
  ### Step 0: Pre-flight check
  ### Step 1: maas.lifecycle.new
    - What happens
    - Run command
    - PAUSE: expected log excerpt
    - VERIFY: expected MaaS state
    - CONTINUE
  ### Step 2: maas.lifecycle.commissioning
    ...
  ### Step 3: maas.lifecycle.ready
    ...
  ### Step 4: maas.lifecycle.allocated
    ...
  ### Step 5: maas.lifecycle.deploying
    ...
  ### Step 6: maas.lifecycle.deployed
    ...
  ### Cleanup (optional)
  
## Part 2 — Rocky 9 Physical Machine (ms01-02)
  ### Step 0: Pre-flight check
    - AMT reachability check
    - Smart plug state
  ### Step 1–6: same structure, with Rocky-specific notes
    - AMT bounce pattern
    - Custom image osystem note
    - hwe_kernel clear
    - OVS networking (maas.machine.config.networking wave)

## Appendix
  - How to check AMT reachability
  - How to bounce a smart plug
  - How to read wave logs
  - Common stuck states and recovery
  - MaaS web UI URL and what to look for
```

**Key content decisions:**

1. **Each step section** shows:
   - Background: what MaaS is doing internally
   - Run: exact shell command
   - Watch: what log lines to look for (from real wave log patterns)
   - PAUSE HERE block (boxed): expected outcome before proceeding
   - Verify command + expected output
   - Troubleshooting: what to do if that verify fails

2. **Log excerpts** are labeled `# example output — yours will differ slightly` and
   show the most diagnostic lines (not full logs).

3. **MaaS web UI** pointers at each step so the user can follow along visually.

4. **Rocky 9 differences** are called out explicitly in Part 2 rather than duplicating
   all steps — Part 2 references Part 1 for shared steps and only explains deltas.

5. **Timing expectations** at each step (commissioning ~10-15 min, deploy ~5-20 min).

6. **Cleanup section** shows how to release the machine back to Ready via destroy:
   ```bash
   ./run --wave maas.lifecycle.deployed --clean  # releases machine
   ```

---

## Execution Order

1. Read `infra/maas-pkg/_docs/walkthrough.md` (doesn't exist yet — skip read).
2. Check `infra/maas-pkg/_docs/` for existing docs to avoid duplication with
   `maas-lifecycle-waves.md`, `troubleshooting.md`, `maas-state-machine.md`.
3. Write `infra/maas-pkg/_docs/walkthrough.md` with full content.
4. Verify: check that all wave names, IPs, hostnames, and commands in the doc match
   the actual config (grep against `pwy-home-lab-pkg.yaml` and `maas-pkg.yaml`).

## Verification

```bash
# Confirm all wave names in doc match actual waves
grep "maas.lifecycle\." infra/maas-pkg/_docs/walkthrough.md | sort -u

# Confirm IPs referenced exist in config
grep "10.0.10.11\|10.0.10.12\|10.0.10.13\|10.0.12.2" infra/maas-pkg/_docs/walkthrough.md

# Confirm machine names referenced exist in config
grep "pxe-test-vm-1\|ms01-02" infra/maas-pkg/_docs/walkthrough.md
grep "pxe-test-vm-1\|ms01-02" infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml
```
