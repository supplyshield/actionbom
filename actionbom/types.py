from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class Coordinate:
    kind: str  # action | reusable-workflow | docker-image | local-action | workflow
    source: str  # github | local | docker
    owner: Optional[str] = None
    repo: Optional[str] = None
    path: Optional[str] = None  # path within repo or local fs
    ref: Optional[str] = None  # tag/branch
    sha: Optional[str] = None  # resolved commit
    image: Optional[str] = None  # docker://...
    display_version: Optional[str] = None  # version from comment or tag (e.g., "1.2.3")
    resolved_version: Optional[str] = None  # concrete release version resolved from SHA (e.g., "3.28.5" when ref is floating "v3")


@dataclass
class Node:
    id: str
    type: str  # action | workflow | docker-image
    coordinate: Coordinate
    action_type: Optional[str] = None  # composite | node | docker | reusable-workflow | None
    manifest_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_location: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class Edge:
    from_id: str
    to_id: str
    relation: str = "depends-on"
    cycle: bool = False


@dataclass
class Graph:
    root: str
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    cycles: List[List[str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "nodes": [
                {
                    **{"id": n.id, "type": n.type},
                    "coordinate": asdict(n.coordinate),
                    **({"actionType": n.action_type} if n.action_type else {}),
                    **({"manifestPath": n.manifest_path} if n.manifest_path else {}),
                    **({"metadata": n.metadata} if n.metadata else {}),
                    **({"sourceLocation": n.source_location} if n.source_location else {}),
                    **({"warnings": n.warnings} if n.warnings else {}),
                }
                for n in self.nodes
            ],
            "edges": [asdict(e) for e in self.edges],
            "cycles": self.cycles,
        }


def make_node_id(node_type: str, coord: Coordinate, manifest_path: Optional[str] = None) -> str:
    # Build deterministic id components
    parts = [node_type, coord.source]
    if coord.source == "github":
        repo_part = f"{coord.owner}/{coord.repo}" if coord.owner and coord.repo else ""
        ref_part = coord.sha or coord.ref or ""
        path_part = manifest_path or coord.path or ""
        parts.append(f"{repo_part}@{ref_part}:{path_part}")
    elif coord.source == "local":
        parts.append(coord.path or manifest_path or "")
    elif coord.source == "docker":
        parts.append(coord.image or "")
    return ":".join(filter(lambda p: p is not None, parts))
