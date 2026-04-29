---
date: 2026-04-09
title: Add scripts/human-only-scripts/validate-config/run
---

## What changed

Added `scripts/human-only-scripts/validate-config/run` — a Python script that
validates config and SOPS YAML file conventions across the repo.

## Rules enforced

- **RULE 1 — One top-level key**: each file must have exactly one top-level key.
  SOPS files also contain a `sops:` metadata key which is excluded from the
  count.
- **RULE 2 — Key matches filename stem**: the single key must equal the
  filename with the extension stripped (`.sops.yaml` before `.yaml`).
  E.g. `aws-pkg_secrets.sops.yaml` → expected key `aws-pkg_secrets`.
- **RULE 3 — Unique stems**: all stems must be unique across the search scope
  so that `_find_component_config` (which searches the whole repo) always
  finds exactly one match.

## Search scope

- `infra/*/_config/*.yaml` — per-package public config and secrets
- `config/*.yaml` — framework-level config (hidden/dot files excluded)

Validated 21 files on first run — all OK.
