# common/generate-ansible-inventory

Generates a dynamic Ansible inventory (`hosts.yml`) by reading Terraform remote
state from the configured backend and cross-referencing with
`the per-package YAML config files`.  Called by most other tg-scripts and wave-scripts
before running Ansible playbooks.

## What It Does

### `--build` (or `make build`)

1. Sets up a local Python 3.12 virtual environment (`.venv/`) and installs
   `pyyaml` plus the appropriate cloud storage SDK (`google-cloud-storage`,
   `boto3`, or `azure-storage-blob`/`azure-identity`).
2. Fetches each unit's Terraform state from the configured backend (GCS, S3,
   Azure, or local).
3. Emits `$_DYNAMIC_DIR/ansible/inventory/hosts.yml` with host
   groups derived from `role_*` tags in the state.

### `--test` (or `make test`)

Same as `--build` but skips the SSH reachability check (`--no-ssh-check`).
Used when hosts may not yet be up (e.g. during early pipeline stages).

### `--exclude-unreachable` (`-E`)

Generates the inventory but warns about (and omits) hosts that fail the SSH
reachability check, rather than failing hard.

### `--deps` (or `make deps`)

Sets up the Python virtual environment and installs dependencies without
generating the inventory.

### `--status` (or `make status`)

Prints the path to the current inventory file and its contents.  Regenerates
it first if the file does not exist.

### `--clean` / `--clean-all`

`--clean` removes the generated inventory file.  `--clean-all` also removes
the `.venv/` directory.

## Host Discovery

A unit is included as an Ansible host if its `terragrunt.hcl` source module
matches a pattern in `ansible_inventory.modules_to_include` in the YAML config
(e.g. `proxmox_virtual_environment_vm`, `maas_machine`).  The per-unit
`_is_host` key in `config_params` overrides this heuristic.

Non-host units (ISO downloads, cloud storage buckets, null scripts, etc.) are
silently skipped without fetching state.

## Role → Group Mapping

Tags of the form `role_<name>` in a unit's `additional_tags` (or in MaaS
machine tags from Terraform state) map to Ansible host group `<name>`.

| Tag | Ansible group |
|---|---|
| `role_maas_server` | `maas_server` |
| `role_pve_host` | `pve_host` |
| `role_image_maker` | `image_maker` |
| (no role tag) | `no_role` |

## Output

`$_DYNAMIC_DIR/ansible/inventory/hosts.yml` — regenerated on each
`--build` call.  All other scripts that need this file check for its existence
and call `generate-ansible-inventory/run --build` if it is missing.

## Config

| YAML key | Purpose |
|---|---|
| `backend.type` / `backend.config` | State backend (gcs, s3, azurerm, local) |
| `ansible_inventory.modules_to_include` | Module names that identify host units |
| `ansible_inventory.pve_nodes` | Static PVE host entries (IP, SSH user) |
| `cloud_init_user` | Default SSH user for provisioned VMs |

## Environment Variables

| Variable | Effect |
|---|---|
| `_INVENTORY_WAVE` | If set, limits host discovery to units matching that wave name |

## Prerequisites

- `set_env.sh` sourced (provides `_CONFIG_DIR`, `_DYNAMIC_DIR`).
- Python 3.12 available locally.
- Cloud credentials set for the configured backend
  (e.g. `GOOGLE_APPLICATION_CREDENTIALS` for GCS).
