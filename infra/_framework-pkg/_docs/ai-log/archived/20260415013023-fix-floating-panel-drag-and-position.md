# Fix Floating Panel Drag and Right-Side Positioning

## Summary

All five floating panel init functions (`init_float_file_viewer`, `init_float_terminal`,
`init_float_object_viewer`, `init_float_refactor`, `init_popup_drag`) were using
`requestAnimationFrame` to defer DOM setup after the popup appeared. RAF fires before
React commits the DOM elements, so `getElementById` returned null and the drag listeners
were never installed — panels appeared but couldn't be dragged. All five were rewritten
with a retry loop. Default positioning was also changed from viewport centre to the right
side of the infra tree, filling the empty space there.

## Changes

- **`homelab_gui/homelab_gui.py`** — `init_float_file_viewer`, `init_float_terminal`,
  `init_float_object_viewer`: replaced `requestAnimationFrame(function(){...})` wrapper
  with `(function tryInit(){...if(!win||!hdr){setTimeout(tryInit,20);return;}...})()`.
  Default position changed from viewport centre to right edge of `#left-column` + 8px,
  filling available width and height.
- **`homelab_gui/homelab_gui.py`** — `init_popup_drag`: same retry-loop fix; fallback
  branch added for when `#top-right-panel` doesn't exist (floating mode) — positions
  popup at the right-column edge instead.
- **`homelab_gui/homelab_gui.py`** — `init_float_refactor`: retry-loop fix; CSS vars
  `--refactor-x/y` now set and updated on drag (were missing before).
- **`homelab_gui/homelab_gui.py`** — `float_refactor_panel()`: removed
  `"transform": "translate(-50%, -50%)"` and `"left": "50%", "top": "50%"` from the
  style dict. React re-applies inline styles on every re-render, which was fighting the
  JS-set position. Replaced with `"left": "var(--refactor-x, 45vw)"` /
  `"top": "var(--refactor-y, 10vh)"` so React's re-renders resolve to the JS-updated
  CSS var value.

## Root Cause

`requestAnimationFrame` fires after the browser has painted, but **before React has
committed the new DOM nodes** from a state update. The floating panel elements didn't
exist yet when `getElementById` ran, so all guards returned `null` and the entire init
body was skipped. Using `setTimeout(tryInit, 20)` to retry avoids this — by the time the
20ms callback fires, React has finished the commit.

## Notes

- The `requestAnimationFrame` in the tree-node scroll (`scroll_js` at ~line 5690) was
  intentionally left unchanged — that one runs after a click event where the element
  already exists, so RAF is correct there.
- CSS vars (`--fv-x`, `--term-x`, etc.) survive React re-renders because React only
  overwrites the specific `style` attribute it knows about; `document.documentElement`
  CSS custom properties are outside React's control.
