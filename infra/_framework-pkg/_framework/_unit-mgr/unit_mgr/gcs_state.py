"""Migrate GCS Terraform state blobs and lock files."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .unit_tree import UnitInfo


def _blob_exists(gcs_path: str) -> bool:
    """Return True if the GCS object exists."""
    result = subprocess.run(
        ["gsutil", "-q", "stat", gcs_path],
        capture_output=True,
    )
    return result.returncode == 0


def migrate_state(units: list[UnitInfo], operation: str, dry_run: bool) -> tuple[int, int]:
    """Migrate GCS state blobs for each unit.

    Returns (migrated_count, skipped_count).
    For 'move': copies then deletes src state.
    For 'copy': copies src state to dst (src left intact).
    State files that don't exist are silently skipped.
    """
    migrated = 0
    skipped = 0

    for unit in units:
        src = unit.gcs_state_src
        dst = unit.gcs_state_dst

        if not _blob_exists(src):
            skipped += 1
            continue

        if dry_run:
            print(f"  [dry-run] gsutil cp {src} {dst}")
            if operation == "move":
                print(f"  [dry-run] gsutil rm {src}")
            migrated += 1
            continue

        # Copy state to new path
        subprocess.run(["gsutil", "cp", src, dst], check=True)

        if operation == "move":
            # Verify destination was written before deleting source
            if _blob_exists(dst):
                subprocess.run(["gsutil", "rm", src], check=True)
            else:
                raise RuntimeError(
                    f"State copy verification failed: {dst} not found after copy"
                )

        # Clean up any lock file at src
        lock_src = src.replace("/default.tfstate", "/default.tflock")
        if operation == "move" and _blob_exists(lock_src):
            subprocess.run(["gsutil", "rm", lock_src], check=True)

        migrated += 1

    return migrated, skipped


def check_no_locks(units: list[UnitInfo]) -> list[str]:
    """Return a list of GCS lock paths that exist (phase 0 pre-flight check)."""
    locked: list[str] = []
    for unit in units:
        lock_path = unit.gcs_state_src.replace("/default.tfstate", "/default.tflock")
        if _blob_exists(lock_path):
            locked.append(lock_path)
    return locked
