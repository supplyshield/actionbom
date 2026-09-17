from __future__ import annotations

import re
from typing import List, Optional, Tuple


def parse_semver(version: str) -> Optional[Tuple[int, ...]]:
    """Parse semantic version string to tuple of integers.
    
    Examples:
        "v4.1.0" → (4, 1, 0)
        "2.10" → (2, 10)
        "1" → (1,)
    
    Returns None if not parseable as semver.
    """
    # Strip 'v' prefix
    v = version.lstrip("v")
    
    # Extract numeric parts
    match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', v)
    if not match:
        return None
    
    parts = []
    for g in match.groups():
        if g is not None:
            parts.append(int(g))
    
    return tuple(parts) if parts else None


def version_in_range(version: str, range_events: List[Dict]) -> bool:
    """Check if version falls within OSV vulnerability range.
    
    OSV range format:
    [
        {"introduced": "0"},
        {"fixed": "2.14.2"}
    ]
    
    Returns True if version is vulnerable (>= introduced and < fixed).
    """
    if not range_events:
        return False
    
    introduced = None
    fixed = None
    
    for event in range_events:
        if "introduced" in event:
            intro_val = event["introduced"]
            if intro_val == "0":
                introduced = (0,)
            else:
                introduced = parse_semver(intro_val)
        
        if "fixed" in event:
            fixed = parse_semver(event["fixed"])
    
    # Parse component version
    comp_ver = parse_semver(version)
    if comp_ver is None:
        # Can't parse version, assume not vulnerable
        return False
    
    # Check if version >= introduced
    if introduced is not None:
        if not _version_gte(comp_ver, introduced):
            return False
    
    # Check if version < fixed (if fixed exists, component is vulnerable if below it)
    if fixed is not None:
        if _version_gte(comp_ver, fixed):
            return False
    
    # If we reach here: version >= introduced and (no fixed or version < fixed)
    return True


def _version_gte(v1: Tuple[int, ...], v2: Tuple[int, ...]) -> bool:
    """Check if v1 >= v2 (semantic version comparison)."""
    # Pad shorter version with zeros
    max_len = max(len(v1), len(v2))
    v1_padded = v1 + (0,) * (max_len - len(v1))
    v2_padded = v2 + (0,) * (max_len - len(v2))
    
    return v1_padded >= v2_padded


def is_component_vulnerable(component_version: str, ranges: List[Dict]) -> bool:
    """Check if component version is affected by any of the provided ranges.
    
    Args:
        component_version: Version string (e.g., "v2.10.0")
        ranges: List of OSV range objects
    
    Returns:
        True if component is vulnerable
    """
    for range_obj in ranges:
        if range_obj.get("type") == "ECOSYSTEM":
            events = range_obj.get("events", [])
            if version_in_range(component_version, events):
                return True
    
    return False
