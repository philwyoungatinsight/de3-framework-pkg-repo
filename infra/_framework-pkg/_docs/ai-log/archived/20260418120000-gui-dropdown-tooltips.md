---
date: 2026-04-18
slug: gui-dropdown-tooltips
---

# Add tooltips to all infra panel dropdown options

Added `title=` native browser tooltips to every option in the four infra panel dropdowns
(Infra/explorer root selector, Appearance, Panels, Help).

## Changes

- `_appearance_menu_item()`: added optional `tooltip: str = ""` parameter; applied as
  `title=tooltip` on the `rx.hstack` only when non-empty.
- `_explorer_root_selector()`: added descriptive `title=` to all four `rx.dropdown_menu.item()`
  calls (Infra, Modules, Packages, Ansible Inventory).
- `panels_menu()`: added `tooltip=` to all four `_appearance_menu_item()` calls.
- `help_menu()`: added `title=` to all six `rx.dropdown_menu.item()` calls.
- `appearance_menu()`: added `tooltip=` to all 16 `_appearance_menu_item()` calls across
  Show in controls bar, Infra tree, Wave panel, File viewer, Terminal, Params panel,
  Nested networks, and Layout sections.

Total: 24 `tooltip=` kwargs + 10 `title=` attributes on direct dropdown items.
`rx.tooltip()` was intentionally avoided — it closes dropdowns mid-interaction.
