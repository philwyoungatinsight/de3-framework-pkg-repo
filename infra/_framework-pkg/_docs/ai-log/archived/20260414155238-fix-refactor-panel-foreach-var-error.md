# Fix: Refactor Panel ForeachVarError at GUI Startup

## Summary

The GUI failed to start after the manage-unit / Refactor panel was introduced in
the previous session. `rx.foreach` was called over `AppState.refactor_preview_result.get("units_found_list", [])` and `.get("external_deps", [])`, which Reflex cannot type at compile time — it resolves `dict.get()` on a `dict = {}` state var to `Union[Any, Sequence[NoReturn]]` and refuses to generate foreach iteration code.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — added
  `refactor_preview_external_deps: list[dict] = []` typed state var; populated it in
  `run_refactor_preview` from `parsed.get("external_deps") or []`; cleared it in
  `begin_refactor` and `clear_refactor_result`; replaced the two broken `rx.foreach`
  calls with (a) a plain count display for `units_found` (the JSON never had a
  `units_found_list` key — only the integer count), and (b) `rx.foreach` over
  `AppState.refactor_preview_external_deps` which Reflex can type correctly.

## Root Cause

`rx.foreach` requires a `Var[Sequence[T]]` where `T` is statically knowable. Calling
`.get(key, [])` on a `dict = {}` state var returns a Reflex var typed as
`Union[Any, Sequence[NoReturn]]` — Reflex cannot determine the element type and raises
`ForeachVarError` at startup. Additionally, `units_found_list` was never emitted by
the `manage-unit` JSON report (the report only emits `units_found: int`), so the key
would always return the default `[]` anyway.

## Notes

- The fix pattern for dict-state foreach: always extract the list into a dedicated
  typed `list[T]` state var and sync it when the dict is set. Never call `rx.foreach`
  over a `.get()` result from a `dict` state var.
