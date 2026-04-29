# Seed Packages: _setup/seed Convention and make seed

## Summary

A new `make seed` / `./run --seed-packages` workflow was created to idempotently provision
cloud accounts and authenticate. Seed logic was extracted from a standalone script into
per-package `infra/<pkg>/_setup/seed` scripts, following the same package-per-directory
convention as `_setup/run`. Framework docs were updated to document both scripts.

## Changes

- **`run`** — added `seed_packages()` function + `--seed-packages`/`-P` flag; runs login→seed→test for every `infra/*/_setup/seed` script found; also added `os.environ.update(ENV)` so `set_env.sh` vars are visible to subprocesses
- **`Makefile`** — added `make seed` target (`./run --seed-packages`)
- **`infra/aws-pkg/_setup/run`** — rewrote to install AWS CLI only; delegates any args to `./seed`
- **`infra/aws-pkg/_setup/seed`** — new: full `--login`/`--seed`/`--test`/`--status`/`--clean`/`--clean-all` idempotent provisioner; reads config from `aws-pkg.yaml` seed: sub-key and `aws-pkg_secrets.sops.yaml`
- **`infra/gcp-pkg/_setup/run`** — delegated seed args to `./seed`
- **`infra/gcp-pkg/_setup/seed`** — new: GCP equivalent of aws seed with WIF/SA support
- **`infra/azure-pkg/_setup/run`** — delegated seed args to `./seed`
- **`infra/azure-pkg/_setup/seed`** — new: Azure equivalent using `az login` session auth
- **`infra/aws-pkg/_config/aws-pkg.yaml`** — added `seed:` sub-key (`aws_account_id`, `state_bucket`, `region`)
- **`infra/gcp-pkg/_config/gcp-pkg.yaml`** — added `seed:` sub-key
- **`infra/azure-pkg/_config/azure-pkg.yaml`** — added `seed:` sub-key
- **`infra/gcp-pkg/_config/gcp-pkg_secrets.sops.yaml`** — created with `gcp-pkg_secrets.seed.*` keys
- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui.py`** — fixed Starlette 1.0 API break (`add_route`/`add_websocket_route` removed; use `router.routes.append()`)
- **`infra/de3-gui-pkg/_application/de3-gui/run`** — fixed `_deps()` to use `install-requirements.sh` (Mac venv has no `pip` module)
- **`utilities/python/install-requirements.sh`** — detect active venv via `VIRTUAL_ENV` and omit `--system` when installing via uv
- **`docs/framework/package-system.md`** — added `_setup/run` and `_setup/seed` rows to "What a Package Owns" table; added "Package Setup Scripts" section with sub-commands and config structure; updated "Adding a New Package" skeleton
- **`README.md`** and **`docs/README.md`** — added `make seed` to quickstart and Makefile targets table

## Root Cause

`make setup` (tool install) and cloud account provisioning were two distinct operations but
had no clean separation. The seed scripts were in a one-off location and didn't follow the
per-package `_setup/` convention used by tool-install scripts.

## Notes

- sops `--encrypt --output <target> /tmp/plaintext.yaml` fails with "no matching creation_rules" because sops matches rules against the **input** path, not the output path. Fix: write plaintext to the target path first, then `sops --encrypt --in-place`.
- `uv pip install --system` fails with permission denied when a venv is active — uv ignores the active venv when `--system` is passed. Fix: omit `--system` when `VIRTUAL_ENV` env var is set.
- Starlette 1.0.0 removed `add_route`/`add_websocket_route` from the `Starlette` class; use `app._api.router.routes.append(Route(...))` instead.
