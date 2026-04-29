"""
Shared capability validation helpers.

Used by both `run` (repo root) and `utilities/python/validate-config.py`.
"""

import sys

try:
    from packaging.version import Version, InvalidVersion
except ImportError:
    sys.exit('ERROR: "packaging" library is required — run: pip install packaging')


def norm_provides(raw) -> list[tuple[str, str]]:
    """Normalise _provides_capability / external_capabilities to [(cap, version), ...].

    Each list item may be:
      - a plain string "cap"          → (cap, "0.0.0")
      - a single-key dict {cap: ver}  → (cap, str(ver))
    """
    if not raw:
        return []
    items = raw if isinstance(raw, list) else [raw]
    result = []
    for item in items:
        if isinstance(item, str):
            result.append((item, '0.0.0'))
        elif isinstance(item, dict) and len(item) == 1:
            cap, ver = next(iter(item.items()))
            result.append((cap, str(ver or '0.0.0')))
        else:
            raise ValueError(f'invalid _provides_capability item: {item!r}')
    return result


def norm_requires(raw) -> list[tuple[str, str]]:
    """Normalise _requires_capability to [(cap, constraint), ...].

    Accepts:
      - None / omitted               → []
      - list of plain strings        → [(cap, '*'), ...]
      - list of single-key dicts     → [(cap, constraint), ...]
      - legacy bare dict             → [(cap, constraint), ...]
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        return [(cap, constraint or '*') for cap, constraint in raw.items()]
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append((item, '*'))
        elif isinstance(item, dict) and len(item) == 1:
            cap, constraint = next(iter(item.items()))
            result.append((cap, constraint or '*'))
        else:
            raise ValueError(f'invalid _requires_capability item: {item!r}')
    return result


def satisfies_version(provided: str, constraint: str) -> bool:
    """Return True if *provided* version satisfies *constraint*.

    Constraint syntax: '>=X.Y.Z', '>X.Y.Z', '<=X.Y.Z', '<X.Y.Z', '=X.Y.Z',
    '*' (any), or comma-separated combinations like '>=1.0.0,<2.0.0'.

    Uses packaging.version.Version for full PEP 440 / semver comparison.
    Raises ValueError on unparseable inputs — never silently treats a bad
    version as satisfied.
    """
    if constraint in ('*', ''):
        return True
    try:
        pv = Version(provided)
    except InvalidVersion:
        raise ValueError(f'unparseable provided version: {provided!r}')
    for part in constraint.split(','):
        part = part.strip()
        try:
            if part.startswith('>='):
                if not (pv >= Version(part[2:])): return False
            elif part.startswith('>'):
                if not (pv > Version(part[1:])): return False
            elif part.startswith('<='):
                if not (pv <= Version(part[2:])): return False
            elif part.startswith('<'):
                if not (pv < Version(part[1:])): return False
            elif part.startswith('='):
                if not (pv == Version(part[1:])): return False
            else:
                raise ValueError(f'unrecognised version constraint operator: {part!r}')
        except InvalidVersion:
            raise ValueError(f'unparseable version in constraint part: {part!r}')
    return True


def check_capability_requirements(
    packages: dict,
    external_caps: list,
) -> list[str]:
    """Validate that every package's _requires_capability is satisfied.

    Args:
        packages:      {pkg_name: pkg_meta_dict} where each meta dict may
                       contain _provides_capability and _requires_capability.
        external_caps: raw external_capabilities list from framework.yaml
                       (same format as _provides_capability).

    Returns:
        List of human-readable error strings.  Empty = all requirements satisfied.
        Duplicate-provides conflicts are included as errors.
    """
    errors: list[str] = []

    # Parse external capabilities: cap → declared version
    external: dict[str, str] = {}
    for cap, ver in norm_provides(external_caps):
        external[cap] = ver

    # Build capability registry from packages: cap → (pkg_name, version)
    cap_registry: dict[str, tuple[str, str]] = {}
    for pkg_name, meta in packages.items():
        for cap, ver in norm_provides(meta.get('_provides_capability')):
            if cap in cap_registry:
                errors.append(
                    f'capability [{cap}] provided by both'
                    f' {cap_registry[cap][0]} and {pkg_name}'
                )
            cap_registry[cap] = (pkg_name, ver)

    # Check requirements
    for pkg_name, meta in packages.items():
        for cap, constraint in norm_requires(meta.get('_requires_capability')):
            if cap in external:
                try:
                    ok = satisfies_version(external[cap], constraint)
                except ValueError as exc:
                    errors.append(f'{pkg_name} [{cap}]: {exc}')
                    continue
                if not ok:
                    errors.append(
                        f'{pkg_name} requires [{cap} {constraint}]'
                        f' but external_capabilities declares version {external[cap]}'
                    )
                continue

            if cap not in cap_registry:
                errors.append(
                    f'{pkg_name} requires [{cap}] but no package provides it'
                    f' — add a providing package or list it in'
                    f' framework.external_capabilities'
                )
                continue

            provider_pkg, provider_ver = cap_registry[cap]
            try:
                ok = satisfies_version(provider_ver, constraint)
            except ValueError as exc:
                errors.append(f'{pkg_name} [{cap}]: {exc}')
                continue
            if not ok:
                errors.append(
                    f'{pkg_name} requires [{cap} {constraint}]'
                    f' but {provider_pkg} provides {provider_ver}'
                )

    return errors
