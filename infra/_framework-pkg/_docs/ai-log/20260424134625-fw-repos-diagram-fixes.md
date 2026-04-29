# Fix fw-repos Mermaid Diagram Repo Names and Package Deduplication

## Summary

Fixed three issues in the fw-repos visualization pipeline that caused incorrect repo names
(`<current-repo>`, `my-homelab`, `my-homelab-pkg`) and duplicate package entries in the
Mermaid class diagram.

## Changes

- **`fw_repos_visualizer/scanner.py`** — use `root.name` (e.g. `pwy-home-lab-pkg`) instead
  of the hardcoded placeholder `"<current-repo>"` when naming the current repo in the scan
  result. The git root directory name is the correct and unambiguous repo identifier.

- **`infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml`** —
  replaced the stale `my-homelab` example entry with the actual `pwy-home-lab-pkg` repo.
  The `my-homelab` entry was a leftover template from initial setup; the user's real home
  lab repo is `pwy-home-lab-pkg`. The stale entry was causing `my-homelab` and
  `my-homelab-pkg` to appear in the diagram as declared repos.

- **`infra/de3-gui-pkg/_application/de3-gui/assets/fw_repos_mermaid_viewer.html`** —
  deduplicate packages by name across `settings_dirs` before building the Mermaid class
  body. The current repo has two `_framework_settings` dirs (`infra/_framework-pkg/...`
  and `infra/pwy-home-lab-pkg/...`) that both list the same packages, causing each package
  to appear twice in the diagram.

## Root Cause

- `<current-repo>` placeholder was intentional initially but the actual repo name is
  available from `repo_root().name`.
- `my-homelab` was never updated when the user named their homelab repo `pwy-home-lab-pkg`.
- Package duplication from multiple `_framework_settings` dirs is by design (config package
  mirrors framework settings); deduplication is the right fix at the display layer.
