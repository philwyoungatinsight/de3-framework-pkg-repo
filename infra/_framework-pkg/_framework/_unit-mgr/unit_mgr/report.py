"""Build human-readable log lines and JSON report structure."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from .dependency_scanner import DepRef

_SENTINEL = "---JSON---"


@dataclass
class Report:
    operation: str
    src: str
    dst: str
    dry_run: bool
    units_found: int = 0
    config_keys_migrated: int = 0
    secret_keys_migrated: int = 0
    state_files_migrated: int = 0
    state_files_skipped: int = 0
    external_deps: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def log(msg: str) -> None:
    print(msg, flush=True)


def log_phase(phase: str) -> None:
    print(f"\n=== {phase} ===", flush=True)


def log_unit(unit_src_rel: str, unit_dst_rel: str) -> None:
    print(f"  {unit_src_rel} -> {unit_dst_rel}", flush=True)


def log_dep_warning(ref: DepRef) -> None:
    print(
        f"  ⚠  EXTERNAL DEP: {ref.hcl_file}:{ref.line}\n"
        f"     refs: {ref.old_ref}\n"
        f"     should become: {ref.new_ref}\n"
        f"     action: manual update required",
        flush=True,
    )


def build_external_dep_entry(ref: DepRef) -> dict:
    return {
        "hcl_file": ref.hcl_file,
        "line": ref.line,
        "old_ref": ref.old_ref,
        "new_ref": ref.new_ref,
        "action": ref.action,
    }


def emit_json(report: Report) -> None:
    """Print the JSON report to stdout after the sentinel line."""
    print(_SENTINEL, flush=True)
    print(json.dumps(asdict(report), indent=2), flush=True)


def fail(msg: str, report: Report | None = None, emit_json_report: bool = False) -> None:
    """Print an error and exit non-zero."""
    print(f"\nERROR: {msg}", file=sys.stderr, flush=True)
    if report is not None:
        report.errors.append(msg)
        if emit_json_report:
            emit_json(report)
    sys.exit(1)
