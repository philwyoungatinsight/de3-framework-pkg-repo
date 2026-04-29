# GUI: Node Detail Popup Snaps to Cover File Viewer Panel on Open

## Summary

When the node detail popup opens it now automatically positions and sizes itself
to exactly cover the right-hand file viewer panel (`top-right-panel`), so the popup
is immediately visible and relevant without the user having to move it. After opening,
the popup can be freely dragged and resized as before.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — `init_popup_drag`:
  added a `_positionSet` guard block inside the `requestAnimationFrame` callback that
  reads the bounding rect of `#top-right-panel` and applies its `left`, `top`, `width`,
  and `height` to the popup element and the `--popup-x`/`--popup-y` CSS custom properties.
  Runs only once per popup lifetime (guard prevents re-snap on subsequent node clicks).

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — `hover_popup_window`:
  removed `max_width` cap (was 750px, would have clipped wide panels); raised `max_height`
  from `85vh` to `95vh`; added explicit `width: 480px` as default for the fallback case
  where `top-right-panel` is not found.

## Notes

- The `_positionSet` property is set on the DOM element (not in Reflex state), so it
  resets naturally when the popup is closed and the element is removed from the DOM.
  Re-opening the popup (checking the box again) will re-snap to the current panel position.
- The drag and resize guards (`_dragInstalled`) remain separate from `_positionSet` so
  that position re-snapping and listener deduplication are independently controlled.
