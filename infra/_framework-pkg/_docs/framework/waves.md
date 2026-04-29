# Wave System

Waves are optional named groups of Terragrunt units applied together in sequence.

- A unit belongs to **at most one wave** (via `_wave` in `config_params`).
- Units not in the active wave are skipped entirely — no init, no plan, no apply.
- Each wave is defined in exactly one package; it can have optional pre-check and test playbooks.
- **Terragrunt `dependencies` blocks are always respected** regardless of wave ordering.
- When no wave filter is active (`terragrunt run --all` with no `TG_WAVE`), all units run and only Terraform dependency edges manage ordering.

The authoritative wave order is in [`config/waves_ordering.yaml`](../../config/waves_ordering.yaml).

---

## Wave Config in YAML

Waves are defined as an ordered list under `<pkg>.waves:`:

```yaml
<pkg>:
  waves:
    - name: network.unifi
      description: Configure VLANs (UniFi switches, routers, firewalls)
      _skip_on_wave_run: true
      test_ansible_playbook: network/network-test
      update_inventory: false

    - name: maas.machines
      description: Physical machines deployed by MaaS
      max_retries: 3
      pre_ansible_playbook: maas/maas-machines-precheck
      test_ansible_playbook: maas/maas-machines-test
      update_inventory: true
```

### Wave Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique wave identifier. Convention: `<category>.<detail>` |
| `description` | string | Human-readable label for `run --list-waves` output |
| `_skip_on_wave_run` | bool | Skip during both `./run` (build) and `./run --clean` / `make clean`. **No effect** on `make clean-all`. Override with `-w <pattern>`. |
| `pre_ansible_playbook` | string | Path under `wave-scripts/<pkg>/test-ansible-playbooks/` — runs before apply |
| `test_ansible_playbook` | string | Path under `wave-scripts/<pkg>/test-ansible-playbooks/` — runs after apply |
| `test_action` | string | `"reapply"` — re-run apply as an idempotency check instead of a test playbook |
| `update_inventory` | bool | Regenerate Ansible inventory from GCS state after apply |
| `max_retries` | int | Additional apply+test attempts on test failure (default 0) |
| `retry_delay_seconds` | int | Seconds between retry attempts (default 0) |

Set at most one of `test_ansible_playbook` or `test_action` per wave.

---

## Assigning Units to Waves

Set `_wave` in `config_params` (typically on an ancestor path so all units below inherit it):

```yaml
"unifi-pkg/_stack/unifi/pwy-homelab":
  _wave: network.unifi
```

The `run` script sets `TG_WAVE=<name>`. `root.hcl` uses it to exclude units whose `_wave` doesn't match, so unrelated units are never initialised or planned.

Units with **no `_wave`** run on every wave — used for foundation units (e.g. the GCS backend) that must always be present.

---

## `make clean` vs `make clean-all`

| | `make clean` | `make clean-all` |
|---|---|---|
| Underlying command | `./run --clean` | `./run --clean-all` |
| Respects `_skip_on_wave_run` | **Yes** — skips marked waves (build + clean) | **No** — runs/destroys all waves |
| Respects `_skip_on_build` | **Yes** — HCL `exclude` block | **No** — sets `_FORCE_DELETE=YES` |
| Cloud resources | Terraform destroy (non-skipped waves) | Pre-purges Proxmox VMs + GKE clusters, then Terraform destroy all |
| GCS state | Left in place | Entire state bucket wiped |

---

## The `run` Script

```
./run -a|-b|-t|-c|-l [-w <pattern>] [-N <n>] [--skip-test] [--ignore] [--dry-run]
```

| Flag | Meaning |
|------|---------|
| `-a` / `--apply` | Apply all waves then test |
| `-b` / `--build` | `ensure-backend` + apply all waves + test |
| `-t` / `--test` | Run test hooks only (no apply) |
| `-c` / `--clean` | Destroy wave resources in reverse order |
| `-l` / `--list-waves` | Print wave table and exit |
| `-w <pattern>` | Glob-filter: only process matching waves |
| `-N <n>` | Apply waves 1..N; clean waves N..last |
| `--skip-test` | Apply without running test hooks |
| `--ignore` | Continue past failures |
| `--dry-run` | Print what would run; don't execute |

```bash
./run -a                       # apply all waves + test
./run -a -w 'maas.*'           # apply only maas.* waves
./run -N 6                     # apply waves 1..6
./run -t -w 'proxmox.install'  # re-run proxmox install test
./run -c -w 'vm.proxmox.*'     # destroy all proxmox VM waves
```

---

## Pre-check and Test Playbooks

**`pre_ansible_playbook`** — runs before apply. Must only verify prerequisites and fail clearly if unmet. No recovery logic, no state changes.

**`test_ansible_playbook`** — runs after apply. Validates deployed infrastructure. On failure with `max_retries > 0`, the script retries the full apply+test cycle.

**`test_action: reapply`** — alternative to a test playbook; re-applies the wave as an idempotency check.

Script location: `scripts/wave-scripts/<pkg>/test-ansible-playbooks/<role>/<name>/`
YAML value: `<role>/<name>` (e.g. `maas/maas-machines-precheck`)

---

## Log Files

```
~/.run-waves-logs/
  <YYYYMMDD-HHMMSS>/
    run.log                         — full session output
    wave-<name>-apply.log           — terragrunt apply output
    wave-<name>-precheck.log        — pre_ansible_playbook output
    wave-<name>-test-playbook.log   — test_ansible_playbook output
  latest/                           — symlink to most recent run
```

---

## Terraform DAG vs Wave Ordering

Wave ordering and Terraform `dependencies` blocks are **complementary, not alternatives**. Both must be kept correct.

| | Wave ordering | Terraform `dependencies` |
|---|---|---|
| Mechanism | `run` script applies waves in sequence | `terragrunt run --all` respects dep edges |
| Granularity | Wave-level | Unit-level |
| Works without `run` script | No | **Yes** |

`terragrunt run --all apply --non-interactive` (no wave filter) must remain operable as a secondary execution mode. This requires explicit `dependencies` blocks to reflect real ordering — wave order alone is not enough.

**Rules:**

1. **Never hardcode individual unit lists** in `dependencies { paths = [...] }`. Lists that can grow or shrink will drift.
2. **Use aggregating units.** Downstream units take a single dep on the aggregating unit; adding or removing a leaf requires no change to downstream deps.
3. **`dependency` blocks** (with `mock_outputs`) for hard deps. `dependencies { paths = [...] }` for ordering-only soft deps.
4. **Cross-wave deps must be explicit.** Don't rely on wave order alone for cross-wave dependencies — the DAG doesn't know about wave order.

---

## Adding a New Wave

1. Choose a name following `<category>.<detail>` (e.g. `monitoring.grafana`).
2. Add the entry to `waves_ordering:` in `config/waves_ordering.yaml` at the correct position.
3. Add the full wave definition (with test playbooks, fields) to `waves:` in the relevant package YAML.
4. Set `_wave: monitoring.grafana` at the appropriate ancestor path in `config_params`.
5. (Optional) Create pre-check and test playbooks under `scripts/wave-scripts/<pkg>/test-ansible-playbooks/<role>/<name>/`.
