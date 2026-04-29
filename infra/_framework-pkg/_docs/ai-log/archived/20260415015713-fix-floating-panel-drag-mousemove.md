# Fix Floating Panel Drag — Switch to document mousemove/mouseup

## Summary

All five floating panel drag implementations used `setPointerCapture` on the header
element for drag tracking. Despite the retry-loop fix that ensures listeners are
installed, dragging still didn't work. The root cause is that `setPointerCapture`
(and the `pointermove`/`pointerup` listeners on `hdr`) isn't reliable in this Reflex/
Radix/React environment — likely because Radix's event system or React 18's event
delegation interferes with pointer capture. Switched to the classic
`mousedown` + `document.addEventListener('mousemove'/'mouseup', ...)` pattern,
which works unconditionally regardless of pointer capture support.

## Changes

- **`homelab_gui/homelab_gui.py`** — `init_float_file_viewer`, `init_float_terminal`,
  `init_float_object_viewer`, `init_popup_drag`, `init_float_refactor`: replaced all
  `pointerdown`/`pointermove`/`pointerup` + `setPointerCapture` drag logic with:
  - `hdr.addEventListener('mousedown', ...)` — starts drag, attaches document listeners
  - `document.addEventListener('mousemove', onMove)` — tracks position
  - `document.addEventListener('mouseup', onUp)` — ends drag, removes document listeners
  Document-level `mousemove`/`mouseup` fire regardless of what's under the cursor,
  making this approach reliable even when the pointer leaves the header mid-drag.

## Root Cause

`setPointerCapture` routes future pointer events to the capturing element. In standard
browsers this works, but in a Reflex 0.8.27 app using Radix Themes (which wraps React
18), Radix's internal event handling may prevent pointer capture from taking effect on
custom div elements. The classic document-level mouse event pattern avoids this
entirely — `document.mousemove` always fires for mouse events regardless of Radix's
component tree.

## Notes

- The z-ordering pool handler on `win` still uses `pointerdown` with `capture=true`
  (`addEventListener(..., true)`) — this is a capture-phase listener that fires before
  any component processing, so it works correctly.
- `e.button !== 0` check in `mousedown` prevents right-click or middle-click from
  accidentally starting a drag.
- `e.preventDefault()` in `mousedown` prevents text selection during drag.
