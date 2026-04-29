"""Scan all .hcl files for dependency path references pointing into the moved tree."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DepRef:
    hcl_file: str    # path relative to repo root
    line: int
    old_ref: str     # src_rel path fragment found in the file
    new_ref: str     # what it should become (dst_rel)
    category: str    # "internal", "external_inbound", "external_outbound"
    action: str      # "auto_updated", "manual_update_required", "no_action"


# Matches string literals containing a path fragment inside dependencies { paths = [...] }
# We use a broad scan: any string literal whose value contains "/" and looks like a path.
_DEP_PATH_RE = re.compile(
    r'"([^"]*get_repo_root\(\)[^"]*infra/([^"]+?))"'
)


def scan_dependencies(infra_abs: Path, src_rel: str, dst_rel: str) -> list[DepRef]:
    """Scan every terragrunt.hcl under infra_abs for dependency references.

    Returns a list of DepRef objects, categorised as:
      - internal: reference from inside src tree to inside src tree (auto-updated in Phase 4b)
      - external_inbound: from outside src to inside src (manual update required)
      - external_outbound: from inside src to outside src (noted, no action)
    """
    refs: list[DepRef] = []

    for hcl_path in sorted(infra_abs.rglob("*.hcl")):
        # Skip .terragrunt-cache files
        if ".terragrunt-cache" in str(hcl_path):
            continue

        try:
            content = hcl_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        hcl_rel = str(hcl_path.relative_to(infra_abs.parent))

        for lineno, line in enumerate(content.splitlines(), start=1):
            for match in _DEP_PATH_RE.finditer(line):
                path_fragment = match.group(2).rstrip("/")

                # Does this reference point into the src tree?
                is_pointing_into_src = (
                    path_fragment == src_rel or
                    path_fragment.startswith(src_rel + "/")
                )
                if not is_pointing_into_src:
                    continue

                # Is the referencing file inside the src tree?
                hcl_abs = str(hcl_path)
                src_abs_str = str(infra_abs / src_rel)
                is_from_src = hcl_abs.startswith(src_abs_str)

                new_ref = dst_rel + path_fragment[len(src_rel):]

                if is_from_src:
                    category = "internal"
                    action = "auto_updated"
                else:
                    category = "external_inbound"
                    action = "manual_update_required"

                refs.append(DepRef(
                    hcl_file=hcl_rel,
                    line=lineno,
                    old_ref=path_fragment,
                    new_ref=new_ref,
                    category=category,
                    action=action,
                ))

    return refs


def patch_internal_deps(dst_abs: Path, src_rel: str, dst_rel: str) -> int:
    """In all terragrunt.hcl files under dst_abs, replace src_rel with dst_rel.

    Returns the number of files modified.
    """
    modified = 0
    for hcl_path in sorted(dst_abs.rglob("*.hcl")):
        if ".terragrunt-cache" in str(hcl_path):
            continue
        try:
            content = hcl_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new_content = content.replace(src_rel, dst_rel)
        if new_content != content:
            hcl_path.write_text(new_content, encoding="utf-8")
            modified += 1
    return modified
