# Fix: Auto button TypeError — datetime vs str comparison in max()

## Summary

Clicking "Auto" in the waves panel raised `TypeError: '>' not supported between
instances of 'datetime.datetime' and 'str'`. PyYAML parses bare ISO-8601 timestamps
as `datetime.datetime` objects, so `last_apply_at` values in `unit-state.yaml` were
inconsistently typed depending on whether the value was quoted in YAML or not.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** —
  `_read_unit_state()`: after loading YAML, normalise `last_apply_at` and
  `last_validated_at` to ISO-8601 strings if PyYAML parsed them as `datetime`.
  This fixes the type mismatch at the source so all callers see consistent strings.
  Also added `str()` wrapping to the two `max(..., key=lambda p: ...)` calls on
  `last_apply_at` (lines 5728 and 8889) as a belt-and-suspenders guard.

## Root Cause

`yaml.safe_load` silently converts values like `2026-04-16T12:20:08Z` to
`datetime.datetime(2026, 4, 16, 12, 20, 8)`. If any entry in `unit-state.yaml`
has an unquoted ISO timestamp while another has a plain string timestamp, `max()`
raises a TypeError when it tries to order them with `>`.
