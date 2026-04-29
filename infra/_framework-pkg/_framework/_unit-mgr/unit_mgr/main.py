"""unit-mgr CLI — move / copy Terragrunt unit trees in the de3 framework."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parents[3] / "_utilities" / "python"))
from framework_config import fw_cfg_path  # noqa: E402

from .config_yaml import migrate_config_params
from .dependency_scanner import DepRef, patch_internal_deps, scan_dependencies
from .gcs_state import check_no_locks, migrate_state
from .report import (
    Report,
    build_external_dep_entry,
    emit_json,
    fail,
    log,
    log_dep_warning,
    log_phase,
    log_unit,
)
from .sops_secrets import migrate_secrets
from .unit_tree import UnitInfo, collect_units, copy_tree, delete_tree


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the absolute path to the git repo root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def _read_framework_backend(repo_root: Path) -> dict:
    """Load framework_backend.yaml via 3-tier resolution."""
    path = fw_cfg_path(repo_root, "framework_backend.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Framework backend config not found: {path}")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("framework_backend", {})


def _gcs_bucket(backend_cfg: dict) -> str:
    return backend_cfg.get("config", {}).get("bucket", "")


def _backend_type(backend_cfg: dict) -> str:
    return backend_cfg.get("type", "")


def _pkg_yaml_path(repo_root: Path, pkg: str) -> Path:
    return repo_root / "infra" / pkg / "_config" / f"{pkg}.yaml"


def _pkg_sops_path(repo_root: Path, pkg: str) -> Path:
    return repo_root / "infra" / pkg / "_config" / f"{pkg}_secrets.sops.yaml"


def _read_framework_packages(repo_root: Path) -> list[dict]:
    """Load framework_packages.yaml package list."""
    pkg_dir = os.environ.get("_FRAMEWORK_PKG_DIR") or str(repo_root / "infra" / "_framework-pkg")
    path = Path(pkg_dir) / "_config" / "framework_packages.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("framework_packages", [])


def _resolve_config_source(pkg_name: str, packages: list[dict]) -> str:
    """Follow config_source chain; return terminal package name. Raises on cycle."""
    pkg_map = {p["name"]: p for p in packages}
    visited: list[str] = []
    current = pkg_name
    while True:
        if current in visited:
            raise ValueError(f"config_source cycle: {' -> '.join(visited + [current])}")
        visited.append(current)
        entry = pkg_map.get(current, {})
        nxt = entry.get("config_source")
        if not nxt:
            return current
        current = nxt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="unit-mgr",
        description="Move or copy Terragrunt unit trees in the de3 framework.",
    )
    p.add_argument(
        "command",
        choices=["copy", "move"],
        help="Operation to perform.",
    )
    p.add_argument(
        "src",
        metavar="SRC_REL",
        help="Source path relative to infra/ (e.g. demo-buckets-example-pkg/_stack/gcp/examples).",
    )
    p.add_argument(
        "dst",
        metavar="DST_REL",
        help="Destination path relative to infra/.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print every action that would be taken; execute nothing.",
    )
    p.add_argument(
        "--json-report",
        action="store_true",
        help="Write a JSON report to stdout after all other output (after ---JSON--- sentinel).",
    )
    p.add_argument(
        "--skip-state",
        action="store_true",
        help="Skip GCS state migration (safe for units that have never been applied).",
    )
    p.add_argument(
        "--skip-secrets",
        action="store_true",
        help="Skip SOPS secrets migration.",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    operation = args.command
    src_rel = args.src.strip("/")
    dst_rel = args.dst.strip("/")
    dry_run = args.dry_run
    json_report = args.json_report

    report = Report(
        operation=operation,
        src=src_rel,
        dst=dst_rel,
        dry_run=dry_run,
    )

    repo_root = _repo_root()
    infra_abs = repo_root / "infra"
    src_abs = infra_abs / src_rel
    dst_abs = infra_abs / dst_rel

    # -----------------------------------------------------------------------
    # Phase 0 — Pre-flight
    # -----------------------------------------------------------------------
    log_phase("Phase 0 — Pre-flight checks")

    if not src_abs.exists():
        fail(f"Source path does not exist: {src_abs}", report, json_report)

    if dst_abs.exists():
        fail(f"Destination path already exists: {dst_abs}", report, json_report)

    try:
        framework_cfg = _read_framework_backend(repo_root)
    except FileNotFoundError as exc:
        fail(str(exc), report, json_report)

    backend = _backend_type(framework_cfg)
    if backend != "gcs":
        fail(
            f"Only GCS backend is supported; got '{backend}'. "
            "Check framework_backend.yaml (resolved via 3-tier lookup).",
            report, json_report,
        )

    bucket = _gcs_bucket(framework_cfg)
    if not bucket:
        fail("Could not read GCS bucket name from framework_backend.yaml", report, json_report)

    log(f"  Backend: gcs")
    log(f"  Bucket:  {bucket}")
    log(f"  Src:     {src_rel}")
    log(f"  Dst:     {dst_rel}")
    if dry_run:
        log("  Mode:    DRY RUN (no changes will be made)")

    # -----------------------------------------------------------------------
    # Phase 1 — Unit discovery
    # -----------------------------------------------------------------------
    log_phase("Phase 1 — Unit discovery")

    units = collect_units(src_abs, dst_abs, src_rel, dst_rel, bucket)
    if not units:
        fail(
            f"No Terragrunt units found under '{src_rel}' "
            "(no directories containing terragrunt.hcl).",
            report, json_report,
        )

    report.units_found = len(units)
    log(f"  Found {len(units)} unit(s):")
    for u in units:
        log_unit(u.src_rel, u.dst_rel)

    # Pre-flight: check for GCS locks (only when state migration will run)
    if not args.skip_state and not dry_run:
        locked = check_no_locks(units)
        if locked:
            fail(
                f"State lock file(s) exist — unit(s) may be in-flight:\n"
                + "\n".join(f"  {p}" for p in locked),
                report, json_report,
            )

    # Pre-flight: warn if --skip-state is used for move but GCS state already exists.
    # The source directory will be deleted; orphaned state can only be recovered manually.
    if args.skip_state and operation == "move" and not dry_run:
        from .gcs_state import _blob_exists
        units_with_state = [u for u in units if _blob_exists(u.gcs_state_src)]
        if units_with_state:
            paths = "\n".join(f"  {u.gcs_state_src}" for u in units_with_state)
            log(
                f"\nWARNING: --skip-state was passed but {len(units_with_state)} unit(s) "
                f"have existing GCS state.\nThe source will be deleted and this state "
                f"will be ORPHANED (no longer reachable):\n{paths}\n"
                f"Pass --skip-state only for units that have never been applied.\n"
                f"To migrate state instead, re-run without --skip-state.\n"
            )

    # -----------------------------------------------------------------------
    # Phase 2 — Dependency scan
    # -----------------------------------------------------------------------
    log_phase("Phase 2 — Dependency scan")

    dep_refs = scan_dependencies(infra_abs, src_rel, dst_rel)
    external_inbound = [r for r in dep_refs if r.category == "external_inbound"]

    log(f"  Internal refs (auto-updated):   {sum(1 for r in dep_refs if r.category == 'internal')}")
    log(f"  External inbound refs (manual): {len(external_inbound)}")

    if external_inbound:
        log("")
        log("  ⚠  The following files reference units in the src tree from OUTSIDE it.")
        log("     They will NOT be auto-updated — update them manually after this run:")
        for ref in external_inbound:
            log_dep_warning(ref)
        report.external_deps = [build_external_dep_entry(r) for r in external_inbound]

    # -----------------------------------------------------------------------
    # Phase 3 — Package detection
    # -----------------------------------------------------------------------
    log_phase("Phase 3 — Package detection")

    src_pkg = src_rel.split("/")[0]
    dst_pkg = dst_rel.split("/")[0]
    is_cross_package = src_pkg != dst_pkg

    # Resolve config_source so config_params are read from / written to the
    # correct file even when a package's config lives in a different package.
    try:
        fw_packages = _read_framework_packages(repo_root)
    except FileNotFoundError:
        fw_packages = []
    src_config_pkg = _resolve_config_source(src_pkg, fw_packages)
    dst_config_pkg = _resolve_config_source(dst_pkg, fw_packages)

    src_yaml = _pkg_yaml_path(repo_root, src_config_pkg)
    dst_yaml = _pkg_yaml_path(repo_root, dst_config_pkg)
    src_sops = _pkg_sops_path(repo_root, src_config_pkg)
    dst_sops = _pkg_sops_path(repo_root, dst_config_pkg)

    log(f"  src package: {src_pkg} (config in: {src_config_pkg})")
    log(f"  dst package: {dst_pkg} (config in: {dst_config_pkg})")
    log(f"  cross-package: {is_cross_package}")

    if not src_yaml.exists():
        fail(
            f"Source package YAML not found: {src_yaml}\n"
            "Create the package structure first.",
            report, json_report,
        )
    if is_cross_package and not dst_yaml.exists():
        fail(
            f"Destination package YAML not found: {dst_yaml}\n"
            "Create the package structure first (at minimum an empty config YAML).",
            report, json_report,
        )

    # -----------------------------------------------------------------------
    # Phase 4 — Execute
    # -----------------------------------------------------------------------
    log_phase("Phase 4 — Execute")

    # 4a — Directory copy/move
    log(f"  4a: Copying directory tree: {src_abs} -> {dst_abs}")
    if not dry_run:
        copy_tree(src_abs, dst_abs)
    else:
        log(f"  [dry-run] shutil.copytree({src_abs}, {dst_abs})")
        log(f"  [dry-run] Remove all .terragrunt-cache dirs under {dst_abs}")

    # 4b — Patch internal dependency references
    log(f"  4b: Patching internal dependency references in {dst_abs}")
    if not dry_run:
        n_patched = patch_internal_deps(dst_abs, src_rel, dst_rel)
        log(f"       Modified {n_patched} .hcl file(s)")
    else:
        log(f"  [dry-run] Replace '{src_rel}' with '{dst_rel}' in all .hcl files under dst")

    # 4c — Migrate public config_params
    log(f"  4c: Migrating public config_params ({src_yaml})")
    if not dry_run:
        n_cfg = migrate_config_params(
            src_yaml, dst_yaml, src_config_pkg, dst_config_pkg, src_rel, dst_rel, operation
        )
        log(f"       Migrated {n_cfg} config_params key(s)")
        report.config_keys_migrated = n_cfg
    else:
        log(f"  [dry-run] Rename config_params keys: {src_rel}/* -> {dst_rel}/*")

    # 4d — Migrate SOPS secrets
    if not args.skip_secrets:
        log(f"  4d: Migrating SOPS secrets ({src_sops})")
        if not dry_run:
            try:
                n_sec = migrate_secrets(
                    src_sops, dst_sops, src_pkg, dst_pkg, src_rel, dst_rel, operation
                )
                log(f"       Migrated {n_sec} secret key(s)")
                report.secret_keys_migrated = n_sec
            except FileNotFoundError:
                log("       No secrets file found — skipping")
            except subprocess.CalledProcessError as exc:
                fail(
                    f"SOPS operation failed: {exc.stderr or exc}",
                    report, json_report,
                )
        else:
            log(f"  [dry-run] Rename secrets config_params keys if {src_sops} exists")
    else:
        log("  4d: Skipping SOPS secrets migration (--skip-secrets)")

    # 4e — Migrate GCS state
    if not args.skip_state:
        log(f"  4e: Migrating GCS state blobs")
        if not dry_run:
            try:
                migrated, skipped = migrate_state(units, operation, dry_run=False)
                log(f"       Migrated: {migrated}, Skipped (no state): {skipped}")
                report.state_files_migrated = migrated
                report.state_files_skipped = skipped
            except subprocess.CalledProcessError as exc:
                fail(
                    f"GCS state migration failed: {exc}",
                    report, json_report,
                )
        else:
            migrate_state(units, operation, dry_run=True)
            log(f"  (dry-run counts not tracked for state)")
    else:
        log("  4e: Skipping GCS state migration (--skip-state)")

    # 4f — Delete source (move only)
    if operation == "move":
        log(f"  4f: Removing source tree: {src_abs}")
        if not dry_run:
            delete_tree(src_abs)
        else:
            log(f"  [dry-run] shutil.rmtree({src_abs})")

    # -----------------------------------------------------------------------
    # Phase 5 — Report
    # -----------------------------------------------------------------------
    log_phase("Phase 5 — Complete")
    if dry_run:
        log(f"  DRY RUN complete. No changes were made.")
    else:
        log(f"  {operation.upper()} complete.")
    log(f"  Units processed:         {report.units_found}")
    log(f"  Config keys migrated:    {report.config_keys_migrated}")
    log(f"  Secret keys migrated:    {report.secret_keys_migrated}")
    log(f"  State files migrated:    {report.state_files_migrated}")
    log(f"  State files skipped:     {report.state_files_skipped}")
    if report.external_deps:
        log(f"\n  ⚠  {len(report.external_deps)} external dependency ref(s) require manual update (see above).")

    if json_report:
        emit_json(report)


if __name__ == "__main__":
    main()
