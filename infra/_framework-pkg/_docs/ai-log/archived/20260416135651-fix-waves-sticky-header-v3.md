# Fix: Waves Panel Sticky Header (v3) — flex layout approach

## Summary

Third attempt at making the wave table header row sticky. Previous approaches
(`overflow="visible"` on the table root, then `height="100%"` on the table root)
failed because Radix's `.rt-TableRoot` CSS class sets `flex-shrink: 0`, preventing
the element from getting a bounded height through percentage or flex inheritance.
The correct fix: make the parent container a flex column, so the table root becomes
a flex item that gets a proper bounded height through flex layout.

## Changes

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**:
  - `waves_content` box: added `display="flex"`, `flex_direction="column"` — makes
    it a flex column container so `rt-TableRoot` becomes a genuine flex item.
  - `_wave_list_table()` and `_wave_folder_table()`: replaced `height="100%"` with
    `flex="1"` + `min_height="0"`. `flex: 1` as an inline style overrides the Radix
    class-level `flex-shrink: 0`, allowing the table to fill available space and
    shrink. `overflow_y="auto"` on a flex item with a flex-determined bounded height
    is the scroll container that `position: sticky` in `<thead>` anchors to.

## Root Cause

Radix's `.rt-TableRoot` CSS class sets both `overflow: auto` (making it a scroll
container) and `flex-shrink: 0` (preventing it from shrinking). Without a bounded
height, the scroll container is as tall as its content and never scrolls, so sticky
headers have nothing to anchor to. `height: 100%` on a block child only works when
the parent has an explicit height — a flex-determined height doesn't always propagate
to block percentage heights. The reliable fix is to make `rt-TableRoot` a flex ITEM
so that flex layout gives it a definite bounded height that `overflow: auto` can
actually scroll within.
