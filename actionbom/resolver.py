from __future__ import annotations

import re
from dataclasses import replace
from typing import Optional

from .types import Coordinate


_DOCKER_PREFIX = "docker://"
_LOCAL_PREFIXES = ("./", "../")


def parse_uses(value: str, *, base_local_dir: Optional[str] = None, display_version: Optional[str] = None) -> Coordinate:
    """Parse a GitHub Actions `uses:` string into a normalized Coordinate.

    Handles forms:
    - docker://alpine:3.19
    - ./path/to/action
    - owner/repo@ref
    - owner/repo/path@ref
    - owner/repo/.github/workflows/file.yml@ref (reusable workflow)
    
    display_version: Optional version from comment (e.g., "1.2.3" from "# v1.2.3")
    """
    value = value.strip()
    # docker image
    if value.startswith(_DOCKER_PREFIX):
        return Coordinate(kind="docker-image", source="docker", image=value)

    # local path
    if value.startswith(_LOCAL_PREFIXES):
        # Reusable workflow if points under .github/workflows/
        kind = "reusable-workflow" if ".github/workflows/" in value else "local-action"
        return Coordinate(kind=kind, source="local", path=value)

    # github ref
    # Pattern: owner/repo(/path)?@ref
    m = re.match(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)(?P<subpath>/[^@]+)?@(?P<ref>.+)$", value)
    if m:
        owner = m.group("owner")
        repo = m.group("repo")
        subpath = m.group("subpath") or ""
        ref = m.group("ref")

        if subpath.startswith("/.github/workflows/") or "/.github/workflows/" in subpath:
            # Reusable workflow
            return Coordinate(
                kind="reusable-workflow",
                source="github",
                owner=owner,
                repo=repo,
                path=subpath.lstrip("/"),
                ref=ref,
            )
        else:
            # Action (possibly nested path specifying action directory)
            path = subpath.lstrip("/") if subpath else None
            return Coordinate(
                kind="action",
                source="github",
                owner=owner,
                repo=repo,
                path=path,
                ref=ref,
            )

    # Bare owner/repo without @ref is invalid per spec, but be lenient: treat as latest on default branch
    m2 = re.match(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)$", value)
    if m2:
        return Coordinate(
            kind="action",
            source="github",
            owner=m2.group("owner"),
            repo=m2.group("repo"),
            ref="heads/main",
        )

    # Unknown format -> local action as fallback to avoid crash
    return Coordinate(kind="local-action", source="local", path=value)


def coord_with_sha(coord: Coordinate, sha: Optional[str]) -> Coordinate:
    if not sha:
        return coord
    return replace(coord, sha=sha)
