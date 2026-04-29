# Rename `_skip_on_clean` → `_skip_on_wave_run` + Blue Wave Highlight

## What changed

Renamed the wave-level skip flag from `skip_on_clean` / `_skip_on_clean` to
`_skip_on_wave_run` and extended its semantics so that marked waves are skipped
during BOTH `make` (build) AND `make clean`. Previously the flag only skipped
during `make clean`.

Also changed the `is_recent` wave row highlight color from accent (red) to blue,
and updated the skip toggle button color from orange to blue.

## Files modified

- **`config/waves_ordering.yaml`** — 10 occurrences of `skip_on_clean: true` → `_skip_on_wave_run: true`
- **`infra/gcp-pkg/_config/gcp-pkg.yaml`** — 2 occurrences renamed
- **`infra/maas-pkg/_config/maas-pkg.yaml`** — 4 occurrences renamed
- **`infra/unifi-pkg/_config/unifi-pkg.yaml`** — 2 occurrences renamed
- **`infra/mikrotik-pkg/_config/mikrotik-pkg.yaml`** — 1 occurrence renamed
- **`infra/proxmox-pkg/_config/proxmox-pkg.yaml`** — added missing `_skip_on_wave_run: true` to `hw.proxmox.storage` wave
- **`run`** — updated help text, comment, and wave filtering logic; filter now runs before the `if args.clean` block so it applies to both build and clean
- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — renamed all GUI references: state var, dict keys, toggle method, button color (orange→blue), tooltip text
- **`docs/framework/skip-parameters.md`** — full rewrite for new semantics
- **`docs/framework/waves.md`** — updated field table and `make clean` vs `make clean-all` table
- **`docs/framework/unit_params.md`** — updated note about unit-level skip
- **`docs/README.md`** — updated skip-parameters.md description
- **`docs/idempotence-and-tech-debt.md`** — renamed references
- **`CLAUDE.md`** — updated `make clean` description and `_skip_FOO` convention
- **`docs/TODO.md`** — marked TODO item as done

## Semantic change

Old: `_skip_on_clean` — wave skipped only during `make clean` (destroy)
New: `_skip_on_wave_run` — wave skipped during both `make` (build) AND `make clean`

`make clean-all` continues to ignore the flag unconditionally.
