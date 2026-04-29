"""Walk a directory subtree and collect all Terragrunt unit directories."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UnitInfo:
    src_abs: Path    # absolute filesystem path of the source unit
    dst_abs: Path    # where the unit will go
    src_rel: str     # relative to infra/ — used as config_params key and GCS prefix
    dst_rel: str     # the renamed version of src_rel
    gcs_state_src: str  # gs://bucket/src_rel/default.tfstate
    gcs_state_dst: str  # gs://bucket/dst_rel/default.tfstate


def collect_units(src_abs: Path, dst_abs: Path, src_rel: str, dst_rel: str,
                  bucket: str) -> list[UnitInfo]:
    """Return a list of UnitInfo for every Terragrunt unit under src_abs.

    A unit is any directory that contains a terragrunt.hcl file.
    If src_abs itself is a leaf unit, the list contains exactly one entry.
    """
    units: list[UnitInfo] = []

    # Walk the entire subtree (including src_abs itself)
    for candidate in sorted([src_abs] + list(src_abs.rglob("*"))):
        if not candidate.is_dir():
            continue
        # Skip .terragrunt-cache — they contain generated files, not source units
        if ".terragrunt-cache" in candidate.parts:
            continue
        if not (candidate / "terragrunt.hcl").exists():
            continue
        # Compute rel paths relative to infra/
        candidate_src_rel = src_rel + str(candidate)[len(str(src_abs)):]
        candidate_dst_rel = dst_rel + str(candidate)[len(str(src_abs)):]
        # Normalise trailing slash from the empty suffix
        candidate_src_rel = candidate_src_rel.rstrip("/")
        candidate_dst_rel = candidate_dst_rel.rstrip("/")

        candidate_dst_abs = dst_abs / candidate.relative_to(src_abs) if candidate != src_abs else dst_abs

        units.append(UnitInfo(
            src_abs=candidate,
            dst_abs=candidate_dst_abs,
            src_rel=candidate_src_rel,
            dst_rel=candidate_dst_rel,
            gcs_state_src=f"gs://{bucket}/{candidate_src_rel}/default.tfstate",
            gcs_state_dst=f"gs://{bucket}/{candidate_dst_rel}/default.tfstate",
        ))

    return units


def copy_tree(src_abs: Path, dst_abs: Path) -> None:
    """Copy src_abs to dst_abs, stripping all .terragrunt-cache directories."""
    shutil.copytree(src_abs, dst_abs)
    # Remove all .terragrunt-cache dirs — they contain baked-in absolute paths
    for cache_dir in dst_abs.rglob(".terragrunt-cache"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)


def delete_tree(src_abs: Path) -> None:
    """Delete src_abs and everything under it."""
    shutil.rmtree(src_abs)
