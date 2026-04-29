# Plan: Rename `skip_on_clean` → `_skip_on_wave_run` + Blue Wave Highlight

## Objective

Rename the wave-level `skip_on_clean` / `_skip_on_clean` parameter to `_skip_on_wave_run`
and extend its semantics so that marked waves are skipped during BOTH `make` (build) AND
`make clean`. Currently the flag only skips during `make clean`. The new name communicates
"this wave is not run by the default wave runner" rather than "this wave is not run on clean."
Also change the `is_recent` wave row highlight color from accent (currently red) to blue.

## Context

### Two separate keys for the same concept

There are currently **two parallel representations** of the skip-on-clean flag:

1. **`config/waves_ordering.yaml`** — uses `skip_on_clean: true` (no leading underscore).
   This file defines display order for the GUI. The GUI reads it and propagates
   `"skip_on_clean": True` into each wave's data dict.

2. **Per-package `<pkg>.yaml` `waves:` sections** — use `_skip_on_clean: true` (with
   underscore). The `run` orchestrator reads `w.get('_skip_on_clean')` from the merged
   wave dicts loaded from these files.

Both need renaming to `_skip_on_wave_run`.

### Waves currently marked skip-on-clean

In `config/waves_ordering.yaml` (10 entries):
- cloud.storage, cloud.k8s, network.unifi, network.unifi.validate-config,
  network.mikrotik, external.storage, external.power, external.servers,
  hw.proxmox.storage, pxe.maas.configure-plain-hosts

Per-package yamls (9 occurrences across 4 files + 1 missing):
- `gcp-pkg.yaml`: cloud.storage, cloud.k8s (line 17, 26)
- `maas-pkg.yaml`: 4 occurrences (lines 15, 22, 29, 49 — external.storage, external.power,
  external.servers, pxe.maas.configure-plain-hosts)
- `unifi-pkg.yaml`: network.unifi, network.unifi.validate-config (lines 9, 16)
- `mikrotik-pkg.yaml`: network.mikrotik (line 13)
- `proxmox-pkg.yaml`: `hw.proxmox.storage` wave (line ~44) has **NO** `_skip_on_clean` —
  it exists only in `waves_ordering.yaml`. Need to **add** `_skip_on_wave_run: true` here.

### `run` script — current logic (lines 944–946)

```python
if args.clean:
    waves = list(reversed(waves))
    # Honour _skip_on_clean unless the user targeted a specific wave with -w
    if not args.wave:
        waves = [w for w in waves if not w.get('_skip_on_clean')]
```

New logic must apply the filter for BOTH build and clean, before the `if args.clean` block.

### GUI — all `skip_on_clean` references

In `homelab_gui.py`:
- Line 1185: comment mentioning `skip_on_clean`
- Line 1188: `wave_skip_on_clean: dict[str, bool] = {}`
- Line 1197: `if entry.get("skip_on_clean"):`
- Line 1198: `wave_skip_on_clean[name] = True`
- Line 1267: `if wave_skip_on_clean.get(name):`
- Line 1268: `entry["skip_on_clean"] = True`
- Line 4365: `"skip_on_clean": "Yes" if cfg.get("skip_on_clean") else ""`
- Line 7497: `def toggle_wave_skip_on_clean(self, name: str):`
- Lines 7509–7518: toggle logic reading/writing `"skip_on_clean"` key in YAML
- Lines 13035–13036: detail row `rx.cond(item["skip_on_clean"] != "", ...)`
- Lines 13180–13187: toggle button (variant/color/tooltip/onClick)

### GUI — `is_recent` highlight color

Lines 13269–13270 and 13537–13538:
```python
background=rx.cond(item["is_recent"], "var(--accent-3)", "transparent"),
_hover={"background": rx.cond(item["is_recent"], "var(--accent-4)", "var(--gui-hover)")},
```
Change to `var(--blue-3)` / `var(--blue-4)`.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `config/waves_ordering.yaml` — modify

Rename all 10 occurrences of `skip_on_clean: true` → `_skip_on_wave_run: true`.

```yaml
# Before:
- name: cloud.storage
  skip_on_clean: true

# After:
- name: cloud.storage
  _skip_on_wave_run: true
```

Apply to all 10 waves: cloud.storage, cloud.k8s, network.unifi, network.unifi.validate-config,
network.mikrotik, external.storage, external.power, external.servers, hw.proxmox.storage,
pxe.maas.configure-plain-hosts.

### `infra/gcp-pkg/_config/gcp-pkg.yaml` — modify

Replace 2 occurrences of `_skip_on_clean: true` → `_skip_on_wave_run: true`.

### `infra/maas-pkg/_config/maas-pkg.yaml` — modify

Replace 4 occurrences of `_skip_on_clean: true` → `_skip_on_wave_run: true`.

### `infra/unifi-pkg/_config/unifi-pkg.yaml` — modify

Replace 2 occurrences of `_skip_on_clean: true` → `_skip_on_wave_run: true`.

### `infra/mikrotik-pkg/_config/mikrotik-pkg.yaml` — modify

Replace 1 occurrence of `_skip_on_clean: true` → `_skip_on_wave_run: true`.

### `infra/proxmox-pkg/_config/proxmox-pkg.yaml` — modify

Add `_skip_on_wave_run: true` to the `hw.proxmox.storage` wave definition (currently at
line ~44). It has `skip_on_clean: true` in `waves_ordering.yaml` but is missing the
corresponding per-package yaml key.

```yaml
# Before:
  - description: Upload ISOs and cloud-init snippets ...
    name: hw.proxmox.storage
    test_action: reapply
    update_inventory: false

# After:
  - description: Upload ISOs and cloud-init snippets ...
    name: hw.proxmox.storage
    _skip_on_wave_run: true
    test_action: reapply
    update_inventory: false
```

### `run` — modify

**1. Help text** (lines 18–19):
```python
# Before:
./run -c|--clean                       destroy all wave resources (reverse order, honours skip_on_clean)
./run -c|--clean -w <pattern>          destroy matching waves (reverse order, ignores skip_on_clean)

# After:
./run -c|--clean                       destroy all wave resources (reverse order, honours _skip_on_wave_run)
./run -c|--clean -w <pattern>          destroy matching waves (reverse order, ignores _skip_on_wave_run)
```

**2. Comment** (line 211): update `skip_on_clean` reference → `_skip_on_wave_run`.

**3. Wave filtering logic** (lines 944–946) — restructure so the skip filter runs before
the clean-specific reversal, covering BOTH build and clean:

```python
# Before:
    if args.clean:
        waves = list(reversed(waves))
        # Honour _skip_on_clean unless the user targeted a specific wave with -w
        if not args.wave:
            waves = [w for w in waves if not w.get('_skip_on_clean')]

# After:
    # Honour _skip_on_wave_run unless the user targeted a specific wave with -w.
    # Applies to both build and clean — these waves are never run by the default runner.
    if not args.wave:
        waves = [w for w in waves if not w.get('_skip_on_wave_run')]
    if args.clean:
        waves = list(reversed(waves))
```

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

**a) Line 1185 comment**: update mention of `skip_on_clean` → `_skip_on_wave_run`.

**b) Line 1188**: rename state var:
```python
# Before:
wave_skip_on_clean: dict[str, bool] = {}
# After:
wave_skip_on_wave_run: dict[str, bool] = {}
```

**c) Lines 1197–1198**: rename dict reads:
```python
# Before:
if entry.get("skip_on_clean"):
    wave_skip_on_clean[name] = True
# After:
if entry.get("_skip_on_wave_run"):
    wave_skip_on_wave_run[name] = True
```

**d) Lines 1267–1268**: rename dict lookup:
```python
# Before:
if wave_skip_on_clean.get(name):
    entry["skip_on_clean"] = True
# After:
if wave_skip_on_wave_run.get(name):
    entry["skip_on_wave_run"] = True
```

**e) Line 4365**: rename key in wave data dict:
```python
# Before:
"skip_on_clean": "Yes" if cfg.get("skip_on_clean") else ""
# After:
"skip_on_wave_run": "Yes" if cfg.get("skip_on_wave_run") else ""
```

**f) Line 7497** — rename method and update docstring:
```python
# Before:
def toggle_wave_skip_on_clean(self, name: str):
    """Toggle the skip_on_clean flag for the named wave in waves_ordering.yaml."""
# After:
def toggle_wave_skip_on_wave_run(self, name: str):
    """Toggle the _skip_on_wave_run flag for the named wave in waves_ordering.yaml."""
```

**g) Lines 7509–7518** — toggle logic: rename YAML key written/read:
```python
# Before:
    waves[i] = {"name": entry, "skip_on_clean": True}
    elif entry.get("skip_on_clean"):
        entry.pop("skip_on_clean", None)
    ...
    entry["skip_on_clean"] = True
# After:
    waves[i] = {"name": entry, "_skip_on_wave_run": True}
    elif entry.get("_skip_on_wave_run"):
        entry.pop("_skip_on_wave_run", None)
    ...
    entry["_skip_on_wave_run"] = True
```

**h) Lines 13035–13036** — detail display row:
```python
# Before:
rx.cond(item["skip_on_clean"] != "",
        _attr_row("skip_on_clean:", item["skip_on_clean"]), rx.box()),
# After:
rx.cond(item["skip_on_wave_run"] != "",
        _attr_row("skip on wave run:", item["skip_on_wave_run"]), rx.box()),
```

**i) Lines 13180–13187** — toggle button (rename onClick, update tooltip):
```python
# Before:
    variant=rx.cond(item["skip_on_clean"] != "", "soft", "ghost"),
    color_scheme=rx.cond(item["skip_on_clean"] != "", "orange", "gray"),
    rx.cond(
        item["skip_on_clean"] != "",
        ...  # tooltip text
    ),
    on_click=AppState.toggle_wave_skip_on_clean(item["name"]),
# After:
    variant=rx.cond(item["skip_on_wave_run"] != "", "soft", "ghost"),
    color_scheme=rx.cond(item["skip_on_wave_run"] != "", "blue", "gray"),
    rx.cond(
        item["skip_on_wave_run"] != "",
        ...  # update tooltip: "Wave is skipped by the runner (build + clean)"
    ),
    on_click=AppState.toggle_wave_skip_on_wave_run(item["name"]),
```

**j) Lines 13269–13270 and 13537–13538** — `is_recent` highlight color:
```python
# Before (both occurrences):
background=rx.cond(item["is_recent"], "var(--accent-3)", "transparent"),
_hover={"background": rx.cond(item["is_recent"], "var(--accent-4)", "var(--gui-hover)")},

# After (both occurrences):
background=rx.cond(item["is_recent"], "var(--blue-3)", "transparent"),
_hover={"background": rx.cond(item["is_recent"], "var(--blue-4)", "var(--gui-hover)")},
```

### `docs/framework/skip-parameters.md` — modify

Full rewrite to document new semantics:
- Table row: `_skip_on_wave_run: true` | Wave skipped during both `make` (build) AND
  `make clean`. Has no effect on `make clean-all`. Override with `-w <pattern>`.
- Remove all references to old `_skip_on_clean` name.
- Update summary table with new column layout.
- Update examples to use new key name.

### `CLAUDE.md` — modify

Two locations reference `_skip_on_clean`:
- Line 113 (`make clean` description): replace `_skip_on_clean` → `_skip_on_wave_run`
- Line 315 (`_skip_FOO params`): replace `_skip_on_clean` → `_skip_on_wave_run`, update description

### `docs/TODO.md` — modify

Mark item 11 ("rename skip_on_clean to _ignore_on_wave_run") as done (or remove/update it,
since the final name is `_skip_on_wave_run` not `_ignore_on_wave_run`).

## Execution Order

1. `config/waves_ordering.yaml` — rename key (source of truth for GUI)
2. Per-package yamls (gcp, maas, unifi, mikrotik, proxmox) — rename key; add missing proxmox entry
3. `run` — update filtering logic and help text
4. `homelab_gui.py` — rename all occurrences; update button color; update `is_recent` color
5. `docs/framework/skip-parameters.md` — rewrite docs
6. `CLAUDE.md` — update references
7. `docs/TODO.md` — mark done

## Verification

After execution:
```bash
# Confirm no old key name remains anywhere
grep -r "skip_on_clean" config/ infra/ run scripts/ docs/ CLAUDE.md --include="*.yaml" --include="*.py" --include="*.md" --include="run"

# Confirm new key is present in all relevant files
grep -r "_skip_on_wave_run" config/ infra/ run
```

Also: start the GUI and confirm:
- `is_recent` wave rows are highlighted in blue, not red/accent
- The toggle button for `_skip_on_wave_run` shows blue when active
- Running `./run` (without `-c`) correctly skips the 10 marked waves
- Running `./run -c` also skips the 10 marked waves
- Running `./run -w cloud.k8s` still runs that wave (override respected)
