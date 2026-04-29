---
date: 2026-04-09
title: root.hcl skip-param cleanup; wire _FORCE_DELETE to exclude block; fix clean-all docs
---

## What changed

### Remove unimplemented unit-level `_skip_on_clean` (root.hcl, docs)

Unit-level `_skip_on_clean` and `_skip_on_clean_exact` locals were read in
root.hcl but never used — they couldn't be wired up because Terragrunt v0.99+
allows only one `exclude` block, and that slot is taken by `_skip_on_build`.
The docs claimed the feature worked; the code admitted it didn't.

- Removed the two dead locals from root.hcl
- Updated comment to state clearly that `_skip_on_clean` is wave-level only
- Verified: no `config_params` entries in the repo use unit-level `_skip_on_clean`
- Updated `docs/framework/skip-parameters.md`: removed unit-level rows from all
  tables; added "not supported" section explaining the Terragrunt constraint
- Updated `docs/framework/unit_params.md`: removed `_skip_on_clean` section;
  collapsed `_skip_on_clean_without_inheritance` (also dead) into a note
- Updated `CLAUDE.md` and `docs/README.md` to reflect wave-level-only support

### Wire `_FORCE_DELETE=YES` to the HCL `exclude` block

`make clean-all` sets `_FORCE_DELETE=YES` in the environment before running
Terraform, but root.hcl wasn't reading it — `_skip_on_build` units were still
HCL-excluded from terraform destroy even during clean-all. The state bucket wipe
(stage 3) compensated, but the units were never terraform-destroyed.

Fixed by reading the env var in root.hcl and gating the exclude condition:

```hcl
_force_delete = get_env("_FORCE_DELETE", "") == "YES"

exclude {
  if      = !local._force_delete && (local._wave_skip || local._skip_on_build || local._skip_on_build_exact)
  actions = ["all"]
}
```

When `_FORCE_DELETE=YES`, the entire exclude block is disabled and every unit
(including `_skip_on_build` example trees) is terraform-destroyed before the
state bucket is wiped.

- Updated `docs/framework/skip-parameters.md`: accurate mechanism description
- Updated `docs/framework/waves.md`: added `_skip_on_build` row to the
  `make clean` vs `make clean-all` comparison table
- Updated `docs/framework/code-architecture.md`: Mermaid diagram node for the
  exclude block now shows `_skip_on_build` condition and `_FORCE_DELETE` override
- Updated `CLAUDE.md`: clean-all description now names the mechanism

### Remove `maas_server_ip` / `maas_server_cidr_prefix` special-case from root.hcl

These were re-exported as top-level locals for convenience, but all callers
already read `unit_params._maas_server_ip` directly — the aliases were unused.
Removed from root.hcl. Moved the values up to the `pwy-homelab` environment
ancestor in `pwy-home-lab-pkg` and `proxmox-pkg` config_params so all descendant
units inherit them without duplication at leaf paths.

## Why

Consistency and accuracy: the docs described behaviour that didn't exist
(`_skip_on_clean` unit-level), and a gap that should have been filled
(`_FORCE_DELETE` bypass in root.hcl). Both are now resolved. The
`maas_server_ip` removal continues the pattern of keeping provider-specific
knowledge out of root.hcl.
