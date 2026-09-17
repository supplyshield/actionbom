from __future__ import annotations

import re
from dataclasses import replace
from typing import Dict, List, Optional, Set, Tuple

from ..types import Coordinate, Node, Edge, Graph, make_node_id
from ..resolver import parse_uses, coord_with_sha
from ..parser.workflow import parse_workflow
from ..parser.action import parse_action


# Full semver like "1.2.3" or "v1.2.3-rc.1" — these don't need SHA→version resolution.
_FULL_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+([-+].*)?$")


def _is_floating_ref(ref: Optional[str]) -> bool:
    """A ref is 'floating' if it isn't a full semver (e.g. v3, v3.28, main, master)."""
    if not ref:
        return False
    return _FULL_SEMVER_RE.match(ref) is None


class GraphBuilder:
    def __init__(self, *, local_loader, github_loader, token: Optional[str] = None, max_depth: Optional[int] = None, repo_context: Optional[Dict[str, str]] = None) -> None:
        self.local = local_loader
        self.gh = github_loader
        self.token = token
        self.max_depth = max_depth
        self.repo_context = repo_context

        self.graph = Graph(root="")
        self.nodes_by_id: Dict[str, Node] = {}
        self.visited: Set[str] = set()
        self.stack: List[str] = []

    # ---------------------- Public API ----------------------
    def build_from_workflow(self, *, source: str, source_name: Optional[str] = None) -> Graph:
        # Determine root coordinate (local or github)
        if source.startswith("github://"):
            coord = self._coord_from_github_uri(source)
            node_type = "workflow"
            node_id = make_node_id(node_type, coord, manifest_path=coord.path)
            root_node = Node(id=node_id, type=node_type, coordinate=coord, manifest_path=coord.path)
        else:
            # Local workflow file path — use real path for reading
            coord = Coordinate(kind="workflow", source="local", path=source)
            node_type = "workflow"
            node_id = make_node_id(node_type, coord, manifest_path=coord.path)
            root_node = Node(id=node_id, type=node_type, coordinate=coord, manifest_path=coord.path)

        self.graph.root = root_node.id
        self._ensure_node(root_node)
        self._dfs(root_node, depth=0)
        # Finalize node list in stable order
        self.graph.nodes = list(self.nodes_by_id.values())
        # Override root node path for display in SBOM (instead of temp file path)
        if source_name and not source.startswith("github://"):
            root = self.nodes_by_id.get(self.graph.root)
            if root:
                root.coordinate = replace(root.coordinate, path=source_name)
        return self.graph

    # ---------------------- DFS traversal ----------------------
    def _dfs(self, node: Node, *, depth: int) -> None:
        if self.max_depth is not None and depth > self.max_depth:
            return
        if node.id in self.stack:
            # Cycle back-edge shouldn't happen at entry
            return
        if node.id in self.visited:
            return

        self.stack.append(node.id)
        try:
            # Expand children based on node type & coordinate
            children = self._children_for(node)
            for child in children:
                # Edge
                cycle = child.id in self.stack
                self.graph.edges.append(Edge(from_id=node.id, to_id=child.id, cycle=cycle))

                if cycle:
                    # record cycle path
                    cyc_path = self.stack.copy()
                    cyc_path.append(child.id)
                    self.graph.cycles.append(cyc_path)
                    continue

                if child.id not in self.nodes_by_id:
                    self._ensure_node(child)

                if child.id not in self.visited:
                    self._dfs(child, depth=depth + 1)
        finally:
            self.visited.add(node.id)
            self.stack.pop()

    # ---------------------- Child expansion ----------------------
    def _children_for(self, node: Node) -> List[Node]:
        coord = node.coordinate
        if node.type == "docker-image":
            return []

        if node.type == "workflow":
            text = self._load_workflow_text(coord)
            if text is None:
                node.warnings.append("Failed to load workflow file")
                return []
            w = parse_workflow(text)
            # steps uses
            out: List[Node] = []
            for uses_entry in w.get("steps_uses", []):
                if isinstance(uses_entry, dict):
                    uses_str = uses_entry.get("uses", "")
                    comment_ver = uses_entry.get("comment_version")
                else:
                    uses_str = uses_entry
                    comment_ver = None
                child = self._node_from_uses(uses_str, parent=node, display_version=comment_ver)
                if child:
                    out.append(child)
            # reusable workflow uses
            for uses_entry in w.get("workflow_uses", []):
                if isinstance(uses_entry, dict):
                    uses_str = uses_entry.get("uses", "")
                    comment_ver = uses_entry.get("comment_version")
                else:
                    uses_str = uses_entry
                    comment_ver = None
                child = self._node_from_uses(uses_str, parent=node, force_kind="workflow", display_version=comment_ver)
                if child:
                    out.append(child)
            return out

        if node.type == "action":
            # Load action manifest and parse
            manifest_text, manifest_path = self._load_action_manifest(coord)
            if manifest_text is None:
                node.warnings.append("Missing action.yml/action.yaml")
                return []
            node.manifest_path = manifest_path
            parsed = parse_action(manifest_text)
            node.action_type = parsed.get("action_type")  # type: ignore
            name = parsed.get("name")
            desc = parsed.get("description")
            author = parsed.get("author")
            if name:
                node.metadata["name"] = name
            if desc:
                node.metadata["description"] = desc
            if author:
                node.metadata["author"] = author
            runs_image = parsed.get("runs_image")
            if runs_image:
                node.metadata["runsImage"] = runs_image

            if node.action_type == "composite":
                out: List[Node] = []
                for uses_str in parsed.get("nested_uses", []) or []:
                    child = self._node_from_uses(uses_str, parent=node)
                    if child:
                        out.append(child)
                return out
            else:
                return []  # leaf for node/docker/unknown

        return []

    # ---------------------- Helpers ----------------------
    def _ensure_node(self, node: Node) -> None:
        self.nodes_by_id[node.id] = node

    def _node_from_uses(self, uses_str: str, *, parent: Node, force_kind: Optional[str] = None, display_version: Optional[str] = None) -> Optional[Node]:
        coord = parse_uses(uses_str, display_version=display_version)

        # If we have repo context (cron flow), rewrite repo-root-relative
        # local refs (./...) to github coords so the GitHubLoader fetches
        # them instead of the LocalLoader hitting the container FS.
        if coord.source == "local" and self.repo_context and coord.path and coord.path.startswith("./"):
            coord = Coordinate(
                kind=coord.kind,
                source="github",
                owner=self.repo_context["owner"],
                repo=self.repo_context["repo"],
                path=coord.path[2:],
                ref=self.repo_context["branch"],
            )

        # If forced to workflow kind (for jobs.<id>.uses), ensure node type workflow
        node_type: str
        if coord.kind == "docker-image":
            node_type = "docker-image"
        elif force_kind == "workflow" or coord.kind == "reusable-workflow":
            node_type = "workflow"
        else:
            node_type = "action"

        if coord.source == "github":
            # ensure sha for stability
            if coord.ref:
                sha = self.gh.resolve_ref_to_sha(coord.owner, coord.repo, coord.ref)  # type: ignore[arg-type]
            else:
                sha = None
            coord = coord_with_sha(coord, sha)
            # Set display_version: prefer comment version, fallback to ref
            if not coord.display_version and display_version:
                coord = replace(coord, display_version=display_version)
            elif not coord.display_version and coord.ref:
                # Use ref as display version if no comment (e.g., "v4")
                coord = replace(coord, display_version=coord.ref)

            # Resolve floating refs (v3, v3.28, main, etc.) to a concrete release
            # version so SCA matching against OSV ranges is accurate.
            if coord.sha and _is_floating_ref(coord.ref):
                resolved = self.gh.resolve_sha_to_version(coord.owner, coord.repo, coord.sha)  # type: ignore[arg-type]
                if resolved:
                    coord = replace(coord, resolved_version=resolved)

        manifest_path = coord.path if node_type == "workflow" else None
        node_id = make_node_id(node_type, coord, manifest_path=manifest_path)
        node = self.nodes_by_id.get(node_id)
        if node is None:
            node = Node(id=node_id, type=node_type, coordinate=coord, manifest_path=manifest_path)
        return node

    def _coord_from_github_uri(self, uri: str) -> Coordinate:
        # Format: github://owner/repo/.github/workflows/file.yml@ref
        raw = uri[len("github://") :]
        # Split @ref
        if "@" in raw:
            path_part, ref = raw.rsplit("@", 1)
        else:
            path_part, ref = raw, "heads/main"
        # owner/repo/... path
        parts = path_part.split("/", 2)
        if len(parts) < 3:
            # default to .github/workflows/ci.yml if not provided
            owner, repo = parts[0], parts[1]
            path = ".github/workflows/ci.yml"
        else:
            owner, repo, path = parts[0], parts[1], parts[2]
        return Coordinate(kind="workflow", source="github", owner=owner, repo=repo, path=path, ref=ref)

    def _load_workflow_text(self, coord: Coordinate) -> Optional[str]:
        if coord.source == "local":
            return self.local.read_text(coord.path) if coord.path else None
        if coord.source == "github":
            ref = coord.sha or coord.ref
            return self.gh.get_file_text(coord.owner, coord.repo, coord.path or "", ref)  # type: ignore[arg-type]
        return None

    def _load_action_manifest(self, coord: Coordinate) -> Tuple[Optional[str], Optional[str]]:
        # Determine manifest candidate paths
        candidates: List[str] = []
        if coord.source == "local":
            base = coord.path or "."
            candidates = [f"{base}/action.yml", f"{base}/action.yaml"]
            for p in candidates:
                if self.local.exists(p):
                    return self.local.read_text(p), p
            return None, None
        elif coord.source == "github":
            base = coord.path or ""
            cand_paths = [
                f"{base}/action.yml" if base else "action.yml",
                f"{base}/action.yaml" if base else "action.yaml",
            ]
            ref = coord.sha or coord.ref
            for p in cand_paths:
                text = self.gh.get_file_text(coord.owner, coord.repo, p, ref)  # type: ignore[arg-type]
                if text is not None:
                    return text, p
            return None, None
        else:
            return None, None
