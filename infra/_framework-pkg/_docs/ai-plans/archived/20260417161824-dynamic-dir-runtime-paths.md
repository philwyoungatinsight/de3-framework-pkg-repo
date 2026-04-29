# Plan: Move all dynamic runtime paths under _DYNAMIC_DIR

## Objective

Enable two simultaneous GUI instances (from different repo checkouts) without
path conflicts.  Today four separate locations are used for runtime files — `$HOME`,
`/tmp`, the repo `state/` dir, and `_DYNAMIC_DIR`.  This plan consolidates all of
them under `_DYNAMIC_DIR` (`<repo-root>/config/tmp/dynamic/`), which is repo-local
and therefore unique per checkout.

New directory layout under `_DYNAMIC_DIR`:

```
_DYNAMIC_DIR/
├── run-wave-logs/          NEW — replaces ~/.run-waves-logs/
│   ├── YYYYMMDD-HHMMSS/
│   │   ├── run.log
│   │   ├── wave-<name>-apply.log
│   │   └── ...
│   ├── latest -> YYYYMMDD-HHMMSS/   (symlink)
│   └── unit-logs/<unit-path>/       (per-unit apply logs)
├── unit-state/             NEW — replaces ~/.run-waves-logs/unit-state.yaml
│   └── unit-state.yaml
├── gui/                    NEW — replaces /tmp/ and $HOME GUI runtime files
│   ├── apply-<safe-path>.exit
│   ├── state-check.marker
│   ├── test-applied
│   └── reflex.log
├── unit-status/            ALREADY HERE — no change
├── watchdog-report/        ALREADY HERE — no change
├── kubeconfig/             ALREADY HERE — no change
└── ansible/inventory/      ALREADY HERE — no change
```

## Context

### What exists today

| Path | Usage | Problem |
|------|-------|---------|
| `~/.run-waves-logs/` | Wave runner log tree + unit-logs | Global, shared across all repo checkouts |
| `~/.run-waves-logs/unit-state.yaml` | Per-unit build state cache | Ditto |
| `/tmp/homelab_gui_apply_*.exit` | Apply exit-code signals writer→watcher | `/tmp` is shared systemwide |
| `/tmp/homelab_gui_state_check.marker` | GCS scan rate-limit marker | Same |
| `~/.homelab-gui-test-applied` | Suppresses double on_load test state | Global |
| `/tmp/reflex-homelab-gui.log` | Reflex startup log for test mode | Fixed name — two instances overwrite |

### Key relationships

- `set_env.sh` defines `_DYNAMIC_DIR=$_GIT_ROOT/config/tmp/dynamic` and exports it.
- `homelab_gui.py` already reads `_DYNAMIC_DIR` from `os.environ` for unit-status YAMLs.
- The wave runner (`run` at repo root) does NOT read `_DYNAMIC_DIR`; it hardcodes `Path.home() / '.run-waves-logs'`.
- `homelab_gui.py` reads `wave_logs_dir` from `de3-gui-pkg.yaml` (relative to `$HOME`) at four call sites.
- `framework/clean-all/run` moves `~/.run-waves-logs/` to `config/tmp/run-waves-logs/` after clean-all — this move becomes obsolete once logs land directly under `_DYNAMIC_DIR`.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### 1. `set_env.sh` — modify

Add two new exported variables after `_DYNAMIC_DIR` is defined:

```bash
export _WAVE_LOGS_DIR="$_DYNAMIC_DIR/run-wave-logs"
export _GUI_DIR="$_DYNAMIC_DIR/gui"
mkdir -p "$_WAVE_LOGS_DIR" "$_GUI_DIR"
```

(Keep existing `mkdir -p "$_CONFIG_TMP_DIR" "$_DYNAMIC_DIR"` line; add the new mkdir on the next line.)

---

### 2. `run` (wave runner at repo root) — modify

**`setup_logging()` function (lines 144–158):**

Change:
```python
log_base = Path.home() / '.run-waves-logs'
```
To:
```python
log_base = Path(os.environ.get("_WAVE_LOGS_DIR") or (Path.home() / ".run-waves-logs"))
```

The `os` module is already imported.  The fallback keeps the old behaviour when
the script is invoked without sourcing `set_env.sh` first.

**Second call site — `scan_wave_logs()` (line 512 area):**

Same change:
```python
log_base = Path.home() / '.run-waves-logs'
```
→
```python
log_base = Path(os.environ.get("_WAVE_LOGS_DIR") or (Path.home() / ".run-waves-logs"))
```

**Docstring (lines 61, 68, 71):**

Update `~/.run-waves-logs/` references to `$_WAVE_LOGS_DIR/` in the module-level
docstring.

---

### 3. `infra/de3-gui-pkg/_config/de3-gui-pkg.yaml` — modify

**`wave_logs_dir` key (line 18 area):** Remove the key entirely — the path is now
determined by `_WAVE_LOGS_DIR` from the environment, not a YAML config.  Delete both
the comment block and the key.

**`wave_tail_cmd` (line 56):** Update the hardcoded path:
```yaml
wave_tail_cmd: tail -99f "$HOME/.run-waves-logs/latest/run.log"
```
→
```yaml
wave_tail_cmd: tail -99f "$_WAVE_LOGS_DIR/latest/run.log"
```

(`$_WAVE_LOGS_DIR` is exported by `set_env.sh`, so it expands in the shell command
that the GUI terminal widget runs.)

---

### 4. `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

**4a. Module-level: `_TEST_APPLIED_MARKER` (line 63)**

Change:
```python
_TEST_APPLIED_MARKER = Path.home() / ".homelab-gui-test-applied"
```
To:
```python
_TEST_APPLIED_MARKER = Path(os.environ.get("_GUI_DIR") or Path.home()) / "test-applied"
```

**4b. `_unit_state_path()` (lines 652–656)**

Replace the entire function body:
```python
def _unit_state_path() -> Path:
    """Return path to the persistent unit-state.yaml."""
    config = _load_config()
    log_base = Path.home() / (config.get("config", {}).get("wave_logs_dir") or ".run-waves-logs")
    return log_base / "unit-state.yaml"
```
With:
```python
def _unit_state_path() -> Path:
    """Return path to the persistent unit-state.yaml."""
    state_dir = Path(os.environ.get("_DYNAMIC_DIR") or (Path.home() / ".run-waves-logs")) / "unit-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "unit-state.yaml"
```

This puts unit-state in `_DYNAMIC_DIR/unit-state/unit-state.yaml` — a separate directory
from wave logs as requested.  The fallback keeps old behaviour when env is absent.

Note: the `p.parent.mkdir()` call in `_write_unit_state()` (line 694) is redundant
now but harmless; leave it.

**4c. Four `wave_logs_dir` reading sites (lines 655, 8362, 8704, 9338)**

Each currently does:
```python
Path.home() / (config.get("config", {}).get("wave_logs_dir") or ".run-waves-logs")
```

Replace all four with a helper.  Add this function near `_unit_state_path()` (around line 658):
```python
def _wave_logs_dir() -> Path:
    """Return the wave-logs base directory."""
    return Path(os.environ.get("_WAVE_LOGS_DIR") or (Path.home() / ".run-waves-logs"))
```

Then replace each of the four call sites:

- Line 655 (in `_unit_state_path` — now removed, see 4b above)
- Line 8362 (in `do_refresh_wave_log_statuses`):
  `log_base = Path.home() / (_load_config().get("config", {}).get("wave_logs_dir") or ".run-waves-logs")`
  → `log_base = _wave_logs_dir()`

- Line 8704 (in `local_state_watcher` Tier 1):
  `log_base = Path.home() / (config.get("config", {}).get("wave_logs_dir") or ".run-waves-logs")`
  → `log_base = _wave_logs_dir()`

- Line 9338 (in `apply_unit`):
  `log_base = Path.home() / (config.get("config", {}).get("wave_logs_dir") or ".run-waves-logs")`
  → `log_base = _wave_logs_dir()`

**4d. `local_state_watcher` — MARKER (line 8932)**

Change:
```python
MARKER = Path("/tmp/homelab_gui_state_check.marker")
```
To:
```python
MARKER = Path(os.environ.get("_GUI_DIR") or "/tmp") / "homelab_gui_state_check.marker"
```

**4e. `local_state_watcher` Tier 3 — apply exit files (lines 9205–9231)**

Three changes in this block:

Line 9205 comment: update `# File names: /tmp/homelab_gui_apply_...` → `# File names: $_GUI_DIR/apply-<safe-path>.exit`

Line 9208:
```python
exit_files = _glob.glob("/tmp/homelab_gui_apply_*.exit")
```
→
```python
_gui_dir = Path(os.environ.get("_GUI_DIR") or "/tmp")
exit_files = _glob.glob(str(_gui_dir / "homelab_gui_apply_*.exit"))
```

**4f. `apply_unit` — exit file path (lines 9326–9335)**

Line 9335:
```python
exit_file = f"/tmp/homelab_gui_apply_{safe_path}.exit"
```
→
```python
_gui_dir = Path(os.environ.get("_GUI_DIR") or "/tmp")
exit_file = str(_gui_dir / f"homelab_gui_apply_{safe_path}.exit")
```

Also update the docstring on line 9327:
```
             ~/.run-waves-logs/unit-logs/<unit-path>/latest.log (+ timestamped copy).
          2. Write the apply exit code to /tmp/homelab_gui_apply_<safe>.exit so the
```
→
```
             $WAVE_LOGS_DIR/unit-logs/<unit-path>/latest.log (+ timestamped copy).
          2. Write the apply exit code to $_GUI_DIR/apply-<safe>.exit so the
```

---

### 5. `infra/de3-gui-pkg/_application/de3-gui/run` — modify

**Line 155 — test-applied marker removal:**
```bash
rm -f "${HOME}/.homelab-gui-test-applied" 2>/dev/null || true
```
→
```bash
rm -f "${_GUI_DIR:-${HOME}}/.homelab-gui-test-applied" "${_GUI_DIR:-}/test-applied" 2>/dev/null || true
```

Wait — after the change, the marker is at `$_GUI_DIR/test-applied`. But `_stop()` is also called on old installs. Keep it safe: remove both old and new locations:
```bash
rm -f "${HOME}/.homelab-gui-test-applied" 2>/dev/null || true
rm -f "${_GUI_DIR:+${_GUI_DIR}/test-applied}" 2>/dev/null || true
```

**Lines 189, 205, 220 — reflex startup log:**
```bash
reflex run > /tmp/reflex-homelab-gui.log 2>&1 &
```
→
```bash
reflex run > "${_GUI_DIR:-/tmp}/reflex-homelab-gui.log" 2>&1 &
```

And the two error messages referencing `/tmp/reflex-homelab-gui.log`:
```
See /tmp/reflex-homelab-gui.log
```
→
```
See ${_GUI_DIR:-/tmp}/reflex-homelab-gui.log
```

---

### 6. `framework/clean-all/run` — modify

`stage_move_wave_logs()` (lines 525–544) currently moves `~/.run-waves-logs/` to
`config/tmp/run-waves-logs/`.  After this change the logs are already in
`_DYNAMIC_DIR/run-wave-logs/` — there is nothing to move.

Options:
A. **Remove the stage entirely** (simplest — logs are already in `config/tmp/` and get wiped by `clean-all`'s GCS bucket purge anyway).
B. Keep the stage but make it a no-op when `_WAVE_LOGS_DIR` is already under `_CONFIG_TMP_DIR`.

**Chosen: option A** — delete `stage_move_wave_logs()`, the `move_wave_logs` flag read,
and the `move_wave_logs` printing/calling in `main()`.  Also remove the
`move_wave_logs: true` key from `config/framework.yaml` and its comment in
`framework/clean-all/run`.

Files touched by option A:
- `framework/clean-all/run`: delete `_read_move_wave_logs()`, `stage_move_wave_logs()`, and their call sites in `main()`.
- `config/framework.yaml`: remove `move_wave_logs: true` under `clean_all:`.

---

## Execution Order

1. `set_env.sh` — add `_WAVE_LOGS_DIR` and `_GUI_DIR` (everything else depends on these).
2. `run` (wave runner) — change `setup_logging()` and `scan_wave_logs()`.
3. `homelab_gui.py` — all six changes (4a–4f) in order; add `_wave_logs_dir()` helper first (4c).
4. `infra/de3-gui-pkg/_application/de3-gui/run` — update marker cleanup and reflex log path.
5. `de3-gui-pkg.yaml` — remove `wave_logs_dir`, update `wave_tail_cmd`.
6. `framework/clean-all/run` + `config/framework.yaml` — remove the move-wave-logs stage.

## Verification

```bash
# 1. Confirm _WAVE_LOGS_DIR and _GUI_DIR are exported
source set_env.sh
echo "_WAVE_LOGS_DIR=$_WAVE_LOGS_DIR"
echo "_GUI_DIR=$_GUI_DIR"

# 2. Run a wave (or ./run --build) and confirm logs appear under _DYNAMIC_DIR
ls "$_WAVE_LOGS_DIR/"

# 3. Confirm unit-state lands in the right place (start GUI, do something)
ls "$_DYNAMIC_DIR/unit-state/unit-state.yaml"

# 4. Grep for old paths — expect zero hits in non-frozen files
grep -r "\.run-waves-logs\|homelab-gui-test-applied\|homelab_gui_apply.*\.exit\|homelab_gui_state_check" \
  --include="*.py" --include="*.sh" --include="*.yaml" --include="*.hcl" \
  $(git ls-files | grep -v "docs/ai-log" | grep -v "archived")
```
