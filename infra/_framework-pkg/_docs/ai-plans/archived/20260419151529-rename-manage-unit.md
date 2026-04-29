# Plan: Rename framework/manage-unit to framework/unit-mgr

## Objective

Rename `framework/manage-unit` to `framework/unit-mgr` to match the naming pattern of the
sibling tool `framework/pkg-mgr`. Also rename the internal Python package from `manage_unit`
to `unit_mgr` for consistency. Update all callers and references.

## Context

- All Python imports within `manage_unit/` use relative imports (`from .module import …`) so
  renaming the package directory does not require touching any import strings inside those
  files.
- The `run` script references the Python package by path (`manage_unit/main.py`), not by
  module name, so only that one path string needs updating.
- `homelab_gui.py` has two module-level helper functions named `_find_manage_unit_run` and
  `_parse_manage_unit_json` — both referenced from event handlers. These need renaming and
  all call sites updated.
- Archived ai-log files are historical records and should be left unchanged.
- Active summary docs (`docs/ai-log-summary/ai-log-summary.md` and
  `infra/de3-gui-pkg/_application/de3-gui/docs/ai-log-summary/README.ai-log-summary.md`)
  mention `manage-unit` in historical entries — leave those historical lines alone; they are
  accurate records of what the tool was called at the time.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `framework/manage-unit/` → `framework/unit-mgr/` — **git mv (directory)**

```bash
git mv framework/manage-unit framework/unit-mgr
```

### `framework/unit-mgr/manage_unit/` → `framework/unit-mgr/unit_mgr/` — **git mv (directory)**

```bash
git mv framework/unit-mgr/manage_unit framework/unit-mgr/unit_mgr
```

### `framework/unit-mgr/run` — **modify**

Line 42 currently reads:
```bash
exec python3 "${SCRIPT_DIR}/manage_unit/main.py" "$@"
```
Change to:
```bash
exec python3 "${SCRIPT_DIR}/unit_mgr/main.py" "$@"
```

### `framework/unit-mgr/unit_mgr/main.py` — **modify**

Two changes:

1. Line 1 docstring:
   - Old: `"""manage-unit CLI — move / copy Terragrunt unit trees in the de3 framework."""`
   - New: `"""unit-mgr CLI — move / copy Terragrunt unit trees in the de3 framework."""`

2. `argparse` prog name (line ~85):
   - Old: `prog="manage-unit"`
   - New: `prog="unit-mgr"`

### `framework/unit-mgr/README.md` — **modify**

Replace all occurrences of `manage-unit` with `unit-mgr` and `manage_unit` with `unit_mgr`.
This file has ~20 occurrences spread throughout title, CLI usage examples, file layout
section, and the implementation order section.

Use `replace_all=true` for the two substitutions:
- `manage-unit` → `unit-mgr`
- `manage_unit` → `unit_mgr`

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — **modify**

Six targeted changes (all can use `replace_all=true`):

1. Function definition + docstring (line 10475):
   - Old: `def _find_manage_unit_run() -> str | None:`
   - New: `def _find_unit_mgr_run() -> str | None:`

2. Docstring inside that function (line 10476):
   - Old: `"""Return the absolute path to framework/manage-unit/run, or None if not found."""`
   - New: `"""Return the absolute path to framework/unit-mgr/run, or None if not found."""`

3. Path construction (line 10485):
   - Old: `candidate = Path(repo_root) / "framework" / "manage-unit" / "run"`
   - New: `candidate = Path(repo_root) / "framework" / "unit-mgr" / "run"`

4. Function definition + docstring (line 10489):
   - Old: `def _parse_manage_unit_json(stdout: str) -> dict:`
   - New: `def _parse_unit_mgr_json(stdout: str) -> dict:`

5. Docstring inside that function (line 10490):
   - Old: `"""Extract and parse the JSON report from manage-unit stdout (after ---JSON--- sentinel)."""`
   - New: `"""Extract and parse the JSON report from unit-mgr stdout (after ---JSON--- sentinel)."""`

6. All call sites and remaining string/comment references — use `replace_all=true`:
   - `_find_manage_unit_run` → `_find_unit_mgr_run` (appears at lines 8001, 8048, 10475)
   - `_parse_manage_unit_json` → `_parse_unit_mgr_json` (appears at lines 8013, 8060, 10489)
   - `"manage-unit run script not found."` → `"unit-mgr run script not found."` (lines 8004, 8051)
   - `manage-unit CLI` in comments (lines 3911, 7895, 14834) → `unit-mgr CLI`

## Execution Order

1. `git mv framework/manage-unit framework/unit-mgr` — rename the outer directory first
2. `git mv framework/unit-mgr/manage_unit framework/unit-mgr/unit_mgr` — rename Python package
3. Edit `framework/unit-mgr/run` — update the path string
4. Edit `framework/unit-mgr/unit_mgr/main.py` — update docstring and prog name
5. Edit `framework/unit-mgr/README.md` — bulk replace all occurrences
6. Edit `homelab_gui.py` — rename helper functions and update all call sites

## Verification

```bash
# 1. Framework directory has the new name
ls framework/unit-mgr/

# 2. Python package has the new name
ls framework/unit-mgr/unit_mgr/

# 3. run script points to the right path
grep "unit_mgr/main.py" framework/unit-mgr/run

# 4. No remaining manage-unit/manage_unit references in live code
# (excluding archived logs and historical ai-log-summary entries)
grep -r "manage.unit\|manage_unit" \
  framework/ \
  infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py \
  && echo "FAIL: references remain" || echo "OK"

# 5. GUI syntax check
python3 -m py_compile \
  infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py && echo "OK"

# 6. unit-mgr runs
framework/unit-mgr/run 2>&1 | tail -5
```
