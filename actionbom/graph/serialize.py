from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from ..types import Graph, Node, Coordinate


def graph_to_json(graph: Graph, *, indent: int = 2, format: str = "cyclonedx") -> str:
    """Serialize graph to JSON. Default format is CycloneDX 1.4."""
    if format == "cyclonedx":
        return json.dumps(graph_to_cyclonedx(graph), indent=indent, sort_keys=False)
    else:
        # internal graph format
        return json.dumps(graph.to_dict(), indent=indent, sort_keys=False)


def graph_to_cyclonedx(graph: Graph) -> Dict[str, Any]:
    """Convert Graph to CycloneDX 1.4 BOM."""
    # Map node_id → component bom-ref (use node.id as is for stability)
    components: List[Dict[str, Any]] = []
    deps_map: Dict[str, List[str]] = {}  # node_id → list of dependsOn node_ids
    node_to_purl: Dict[str, str] = {}  # node_id → purl (for dependencies)

    for node in graph.nodes:
        comp = _node_to_cyclonedx_component(node)
        components.append(comp)
        deps_map[node.id] = []
        # Map node ID to purl (or fallback to bom-ref if no purl)
        purl = _coord_to_purl(node.coordinate)
        node_to_purl[node.id] = purl if purl else node.id

    # Build dependencies from edges
    for edge in graph.edges:
        if edge.from_id not in deps_map:
            deps_map[edge.from_id] = []
        deps_map[edge.from_id].append(edge.to_id)

    # Include all components in dependencies array (convert IDs to purls)
    dependencies = [
        {
            "ref": node_to_purl.get(ref, ref),
            "dependsOn": [node_to_purl.get(dep_id, dep_id) for dep_id in deps]
        }
        for ref, deps in deps_map.items()
    ]

    # Root component (metadata.component)
    root_node = next((n for n in graph.nodes if n.id == graph.root), None)
    root_comp = _node_to_cyclonedx_component(root_node) if root_node else None

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": None,  # Could add datetime.utcnow().isoformat() + "Z" if desired
            "tools": [{"vendor": "actionBOM", "name": "actionBOM", "version": "beta 1.0"}],
        },
        "components": components,
        "dependencies": dependencies,
    }

    if root_comp:
        bom["metadata"]["component"] = root_comp

    return bom


def _node_to_cyclonedx_component(node: Node) -> Dict[str, Any]:
    """Convert a Node to a CycloneDX component dict."""
    coord = node.coordinate
    
    # Use purl as bom-ref for clean identifier (fallback to node.id for local/non-purl components)
    purl = _coord_to_purl(coord)
    bom_ref = purl if purl else node.id
    
    comp: Dict[str, Any] = {
        "bom-ref": bom_ref,
        "type": _node_type_to_cyclonedx_type(node.type),
        "name": _coord_to_name(coord),
    }

    version = _coord_to_version(coord)
    if version:
        comp["version"] = version

    if purl:
        comp["purl"] = purl

    # Properties for action type, ref, warnings
    props: List[Dict[str, str]] = []
    if node.action_type:
        props.append({"name": "github:action:type", "value": node.action_type})
    if coord.ref and coord.source == "github":
        props.append({"name": "github:action:ref", "value": coord.ref})
    for warn in node.warnings:
        props.append({"name": "github:action:warning", "value": warn})

    if props:
        comp["properties"] = props

    return comp


def _node_type_to_cyclonedx_type(node_type: str) -> str:
    """Map internal node type to CycloneDX component type."""
    if node_type == "workflow":
        return "application"
    if node_type == "action":
        return "library"
    if node_type == "docker-image":
        return "container"
    return "library"


def _coord_to_name(coord: Coordinate) -> str:
    """Derive component name from coordinate."""
    if coord.source == "github":
        base = f"{coord.owner}/{coord.repo}"
        if coord.path:
            return f"{base}/{coord.path}"
        return base
    if coord.source == "docker":
        # docker://alpine:3.19 → alpine
        img = coord.image or ""
        if img.startswith("docker://"):
            img = img[len("docker://"):]
        # strip tag/digest
        if ":" in img:
            img = img.split(":")[0]
        if "@" in img:
            img = img.split("@")[0]
        return img
    if coord.source == "local":
        return coord.path or "local"
    return "unknown"


def _coord_to_version(coord: Coordinate) -> str:
    """Derive version from coordinate.

    Priority: resolved_version (concrete release looked up from SHA) >
    display_version (from `# v1.2.3` comment) > ref > sha. Putting resolved
    first means SCA matching gets a real semver (e.g. "3.28.5") instead of a
    floating tag (e.g. "v3"), which the OSV range matcher can compare correctly.
    """
    if coord.source == "github":
        return coord.resolved_version or coord.display_version or coord.ref or coord.sha or "unknown"
    if coord.source == "docker":
        img = coord.image or ""
        if img.startswith("docker://"):
            img = img[len("docker://"):]
        # Extract tag or digest
        if "@" in img:
            return img.split("@", 1)[1]
        if ":" in img:
            return img.split(":", 1)[1]
        return "latest"
    if coord.source == "local":
        return coord.sha or coord.ref or "local"
    return "unknown"


def _coord_to_purl(coord: Coordinate) -> str:
    """Generate purl for coordinate (simple format without qualifiers)."""
    if coord.source == "github":
        owner = coord.owner or "unknown"
        repo = coord.repo or "unknown"

        # Priority: resolved_version > display_version > ref > sha (matches _coord_to_version)
        version = coord.resolved_version or coord.display_version or coord.ref or coord.sha or "unknown"
        base = f"pkg:github/{owner}/{repo}@{version}"
        
        if coord.path:
            base += f"#{coord.path}"
        return base
    if coord.source == "docker":
        img = coord.image or ""
        if img.startswith("docker://"):
            img = img[len("docker://"):]
        # pkg:docker/image@version
        if "@" in img:
            parts = img.split("@", 1)
            return f"pkg:docker/{parts[0]}@{parts[1]}"
        if ":" in img:
            parts = img.split(":", 1)
            return f"pkg:docker/{parts[0]}@{parts[1]}"
        return f"pkg:docker/{img}@latest"
    # local sources: no standard purl; omit or use generic
    return ""
