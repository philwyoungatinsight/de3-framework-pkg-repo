"""Merge source and config_source config_params dicts."""

from __future__ import annotations


def merge_config_params(
    source_params: dict,
    config_source_params: dict,
    merge_method: str = "interleave",
) -> dict:
    """Merge config_params from a source package and its config_source package.

    interleave (default):
        {**source_params, **config_source_params} — config_source wins on collision.
        Both sets of keys participate in the ancestor-merge consumers perform later.

    source_only:
        Only config_source_params are used; source_params are ignored entirely.
    """
    if merge_method == "source_only":
        return dict(config_source_params)
    # interleave: config_source wins
    return {**source_params, **config_source_params}
