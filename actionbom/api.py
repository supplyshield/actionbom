"""Library API for programmatic use of actionbom."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from .graph import GraphBuilder
from .loader import LocalLoader, GitHubLoader
from .vulns import scan_vulnerabilities


def generate_sbom(source: str, token: Optional[str] = None, max_depth: Optional[int] = None, source_name: Optional[str] = None, repo_context: Optional[Dict[str, str]] = None) -> Dict:
    """Generate CycloneDX SBOM for a workflow.

    Args:
        source: Workflow file path or github:// URI
        token: Optional GitHub token
        max_depth: Optional max recursion depth
        source_name: Optional display name for the root node (e.g. org/repo/path)
        repo_context: Optional dict with owner/repo/branch — when set, local
            (./) refs are resolved against the GitHub repo instead of the local FS.

    Returns:
        CycloneDX SBOM as dictionary
    """
    local = LocalLoader()
    gh = GitHubLoader(token=token)
    builder = GraphBuilder(local_loader=local, github_loader=gh, token=token, max_depth=max_depth, repo_context=repo_context)
    graph = builder.build_from_workflow(source=source, source_name=source_name)
    return graph.to_dict()  # Returns internal format, will be converted by serialize


def full_scan(source: str, token: Optional[str] = None, max_depth: Optional[int] = None, source_name: Optional[str] = None, repo_context: Optional[Dict[str, str]] = None) -> Tuple[Dict, Dict]:
    """Generate SBOM and scan for vulnerabilities in one call.

    Args:
        source: Workflow file path or github:// URI
        token: Optional GitHub token
        max_depth: Optional max recursion depth
        source_name: Optional display name for the root node (e.g. org/repo/path)
        repo_context: Optional dict with owner/repo/branch — when set, local
            (./) refs are resolved against the GitHub repo instead of the local FS.

    Returns:
        Tuple of (sbom_dict, vulnerabilities_dict)
    """
    # Generate SBOM
    local = LocalLoader()
    gh = GitHubLoader(token=token)
    builder = GraphBuilder(local_loader=local, github_loader=gh, token=token, max_depth=max_depth, repo_context=repo_context)
    graph = builder.build_from_workflow(source=source, source_name=source_name)
    
    # Convert to CycloneDX format for vuln scanning
    from .graph import graph_to_json
    import json
    sbom_json = graph_to_json(graph, format="cyclonedx")
    sbom = json.loads(sbom_json)
    
    # Scan vulnerabilities
    vulns = scan_vulnerabilities(sbom)
    
    return sbom, vulns
