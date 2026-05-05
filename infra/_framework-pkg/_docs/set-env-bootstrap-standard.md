# set_env.sh Bootstrap Standard

Every script that needs framework env vars must source `set_env.sh`. This document
defines the correct pattern for each script category. Use the category that matches
where your script lives and how it is called.

## Category A — Framework bash entry-points

**Where**: scripts in `_FRAMEWORK_PKG_DIR/_framework/<tool>/` that are run directly
or added to `$PATH` via set_env.sh.

**Rule**: set `SCRIPT_DIR` and `_FRAMEWORK_PKG_DIR` from `BASH_SOURCE[0]`, then source
`set_env.sh` immediately — BEFORE argument parsing.

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# Compute depth from SCRIPT_DIR to _FRAMEWORK_PKG_DIR for this tool's location.
# Tools at _framework/<tool>/<tool>: SCRIPT_DIR/../.. = _FRAMEWORK_PKG_DIR
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
```

**Why not git rev-parse**: these scripts exec Python after `cd SCRIPT_DIR`. Any
git call inside Python would resolve to the framework repo, not the consumer repo.

## Category B — Framework bash hooks (always called by framework)

**Where**: tg-hooks, utilities called exclusively from within the framework context
(terragrunt hooks, wave-mgr, etc.). `_FRAMEWORK_PKG_DIR` is always in the environment.

**Rule**: require `_FRAMEWORK_PKG_DIR` to be set; fail loudly if not.

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
. "${_FRAMEWORK_PKG_DIR:?_FRAMEWORK_PKG_DIR must be set}/../../set_env.sh"
```

**Why not git rev-parse**: these scripts are never called standalone; git rev-parse
is unnecessary overhead, and failing loudly makes misconfiguration obvious.

## Category C — Consumer bash scripts (standalone-callable)

**Where**: `infra/<pkg>/_setup/`, `infra/<pkg>/_wave_scripts/`,
`infra/<pkg>/_tg_scripts/`. May be called by hand from the consumer repo root.

**Rule**: use `git rev-parse --show-toplevel` as the root — it is always correct here
because these scripts never cd to the framework directory.

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
GIT_ROOT="$(git rev-parse --show-toplevel)"
. "$GIT_ROOT/set_env.sh"
```

## Category D — Python framework entry-points

**Where**: Python scripts that are the entry-point of a framework tool and need the
consumer repo root.

**Rule**: check `_FRAMEWORK_PKG_DIR` first (set by the bash wrapper that launched
this Python process); fall back to git only if missing.

```python
_fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
if _fw_pkg:
    git_root = str(Path(_fw_pkg).parent.parent)
else:
    git_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
```

## Quick Reference

| Script location | Call context | Category |
|----------------|-------------|----------|
| `_framework/<tool>/<tool>` (bash) | Direct / $PATH | A |
| `_framework/_utilities/tg-scripts/` | Terragrunt hook | B |
| `infra/<pkg>/_tg_scripts/` | Terragrunt hook / standalone | C |
| `infra/<pkg>/_wave_scripts/` | wave-mgr / standalone | C |
| `infra/<pkg>/_setup/` | Standalone | C |
| `_framework/<tool>/` (Python, after bash cd) | Via bash wrapper | D |
