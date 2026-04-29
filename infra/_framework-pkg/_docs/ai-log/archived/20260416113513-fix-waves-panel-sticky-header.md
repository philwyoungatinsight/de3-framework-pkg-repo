# Fix: Waves Panel Header Not Sticky When Scrolling

## Summary

The wave table header row (Wave, Actions, Pre, Run, Test, etc.) was not staying
frozen when scrolling down the waves panel. The header cells had `position: sticky; top: 0`
but this had no effect because Radix UI's `Table.Root` renders a `div.rt-TableRoot` wrapper
with `overflow: auto` in its CSS, making it the CSS scroll container — but without a height
constraint it never actually scrolls, so sticky never activates.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — added
  `overflow="visible"` to both `rx.table.root` calls in `_wave_list_table()` and
  `_wave_folder_table()`, overriding the Radix default so the `waves_content` box
  (which has `overflow_y: auto` and is the real scroll container) is used as the sticky
  reference frame.

## Root Cause

CSS `position: sticky` anchors to the nearest ancestor that is a scroll container
(any element with `overflow` other than `visible`). Radix UI sets `overflow: auto` on
`div.rt-TableRoot` via its theme CSS, making it intercept sticky before the real scroll
container (`waves_content`) can. Since `rt-TableRoot` has no height constraint it never
scrolls itself, so the sticky header had nothing to stick to.

## Notes

The fix is a single `overflow="visible"` prop on each `rx.table.root`. Radix inline
styles take precedence over the theme CSS, so this reliably overrides the problematic
default without touching any global CSS.
