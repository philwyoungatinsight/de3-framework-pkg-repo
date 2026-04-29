# de3

A Terragrunt implicit-stack for a hybrid multi-cloud home lab.
Infrastructure is defined as code across 13 packages (AWS, Azure, GCP, Proxmox, MaaS,
UniFi, and more). The `./run` script drives the full lifecycle: setup → build → test → clean.

## Quick start

```bash
git clone <repo>
cd de3
make setup   # install all CLI tools and language deps
make seed    # provision cloud accounts and authenticate (idempotent)
make         # sync external packages, then build (apply all waves)
```

All three commands are idempotent — safe to re-run at any time.

`./run --build` automatically bootstraps `infra/_framework-pkg` (clones de3-runner and
creates the symlink) if it is missing, so a fresh clone just needs `make setup && make`.

`make` runs `./run --sync-packages` (clone/link external package repos) before
`./run --build`, so a fresh clone builds end-to-end without a separate sync step.

## Dependency installation

`make setup` runs `./run --setup-packages`, which discovers and executes every
`infra/<pkg>/_setup/run` script. `_framework-pkg` runs first; all others follow alphabetically.

### What gets installed

| Tool | Installed by |
|------|-------------|
| jq | `_framework-pkg/_setup/run` |
| uv (Python package manager) | `_framework-pkg/_setup/run` |
| python3 + pyyaml + packaging | `_framework-pkg/_setup/run` |
| yq | `_framework-pkg/_setup/run` |
| sops | `_framework-pkg/_setup/run` |
| OpenTofu | `_framework-pkg/_setup/run` |
| Terragrunt | `_framework-pkg/_setup/run` |
| kubectl | `_framework-pkg/_setup/run` |
| helm | `_framework-pkg/_setup/run` |
| AWS CLI | `aws-pkg/_setup/run` |
| Azure CLI | `azure-pkg/_setup/run` |
| gcloud + gke-gcloud-auth-plugin | `gcp-pkg/_setup/run` |
| Node.js 18+ | `de3-gui-pkg/_setup/run` |
| Python GUI deps (Reflex, etc.) | `de3-gui-pkg/_setup/run` |
| gh (GitHub CLI) | `pwy-home-lab-pkg/_setup/run` |
| glab (GitLab CLI) | `pwy-home-lab-pkg/_setup/run` |

### Platform support

Every setup script branches on the detected platform:

- **macOS** — Homebrew (`brew install …`)
- **Debian / Ubuntu** — apt (`sudo apt-get install …`)
- **Fedora / RHEL** — dnf (`sudo dnf install …`)

Python packages are installed via `infra/_framework-pkg/_framework/_utilities/python/install-requirements.sh`, which
prefers **uv** if available and falls back to pip (with `--break-system-packages` for
PEP 668 environments). uv itself is installed by `_framework-pkg/_setup/run`.

If a prerequisite is missing when a package-specific setup script runs, it automatically
delegates to `_framework-pkg/_setup/run` to install it rather than failing.

All setup scripts are **idempotent** — they check whether each tool is already present
before installing.

## Makefile targets

| Target | Effect |
|--------|--------|
| `make` / `make build` | Sync external packages then apply all waves (`./run --sync-packages && ./run --build`) |
| `make bootstrap` | Explicitly clone de3-runner and link `infra/_framework-pkg` (auto-runs inside `make build`) |
| `make setup` | Install all CLI tools and language deps (`./run --setup-packages`) |
| `make seed` | Provision cloud accounts and authenticate (`./run --seed-packages`) |
| `make test` | Run Ansible test playbooks against live infra (`./run --test`) |
| `make clean` | Destroy in reverse wave order, honouring skip flags (`./run --clean`) |
| `make clean-all` | Nuclear destroy — all resources, all state (`./run --clean-all`) |

## Configuration and secrets

`source set_env.sh` must be run before any `terragrunt` or tool invocation. It:

1. Exports all framework path env vars (`_GIT_ROOT`, tool paths, `_CONFIG_DIR`, etc.)
2. Runs `config-mgr generate`, which pre-merges all package YAML into `$_CONFIG_DIR`
   and copies each package's encrypted `*_secrets.sops.yaml` into `$_CONFIG_DIR/<pkg>.secrets.sops.yaml`

Secrets are **never decrypted to disk**. Terragrunt calls `sops_decrypt_file()` at runtime
to read credentials in-process. The `_CONFIG_DIR` holds only pre-merged public YAML and
encrypted SOPS copies.

Per-package config lives in `infra/<pkg>/_config/<pkg>.yaml` (public) and
`infra/<pkg>/_config/<pkg>_secrets.sops.yaml` (secrets). All deployment-specific
values for this lab are in `infra/pwy-home-lab-pkg/_config/`.

## Documentation

- **Framework**: `infra/_framework-pkg/_docs/framework/` — architecture, waves, config files, skip parameters
- **Package docs**: `infra/<pkg>/_docs/` — one `_docs/` directory per package
- **Full index**: `infra/_framework-pkg/_docs/README.md`
