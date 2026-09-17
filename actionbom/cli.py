from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from .graph import GraphBuilder, graph_to_json
from .loader import LocalLoader, GitHubLoader
from .loader.github import RateLimitError
from .vulns import scan_vulnerabilities


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="actionbom", description="Actions Bill of Materials (ABOM) generator")
    sub = p.add_subparsers(dest="command", required=True)

    # SBOM command - generate SBOM only
    sbom = sub.add_parser("sbom", help="Generate SBOM for a workflow")
    sbom.add_argument(
        "--workflow",
        required=True,
        help="Path to a local workflow YAML or github://owner/repo/.github/workflows/file.yml@ref",
    )
    sbom.add_argument("--token", help="GitHub token (or use GITHUB_TOKEN / GH_TOKEN env var)")
    sbom.add_argument("--output", help="Write SBOM to file (default: stdout)")
    sbom.add_argument("--max-depth", type=int, default=None, help="Maximum recursion depth")
    sbom.add_argument(
        "--format",
        choices=["cyclonedx", "internal"],
        default="cyclonedx",
        help="Output format (default: cyclonedx)",
    )

    # SCAN command - generate SBOM + scan vulnerabilities
    scan = sub.add_parser("scan", help="Generate SBOM and scan for vulnerabilities")
    scan.add_argument(
        "--workflow",
        required=True,
        help="Path to a local workflow YAML or github://owner/repo/.github/workflows/file.yml@ref",
    )
    scan.add_argument("--token", help="GitHub token (or use GITHUB_TOKEN / GH_TOKEN env var)")
    scan.add_argument(
        "--output-dir",
        help="Directory to save sbom.json and vulns.json (if not provided, only prints summary)",
    )
    scan.add_argument("--max-depth", type=int, default=None, help="Maximum recursion depth")

    # VULNS command - scan existing SBOM for vulnerabilities
    vulns = sub.add_parser("vulns", help="Scan existing SBOM for vulnerabilities")
    vulns.add_argument("--sbom", required=True, help="Path to CycloneDX SBOM JSON file")
    vulns.add_argument("--output", help="Write vulnerability report to file (default: stdout)")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Get token from args or environment
    token = getattr(args, "token", None) or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    
    if args.command == "sbom":
        return _cmd_sbom(args, token)
    elif args.command == "scan":
        return _cmd_scan(args, token)
    elif args.command == "vulns":
        return _cmd_vulns(args)
    
    parser.error("unknown command")
    return 2


def _cmd_sbom(args, token: Optional[str]) -> int:
    """Handle 'sbom' command - generate SBOM only."""
    if not token:
        sys.stderr.write("Info: No GitHub token provided. Using unauthenticated API (60 requests/hr).\n\n")
    
    try:
        local = LocalLoader()
        gh = GitHubLoader(token=token)
        builder = GraphBuilder(local_loader=local, github_loader=gh, token=token, max_depth=args.max_depth)
        graph = builder.build_from_workflow(source=args.workflow)
        out_json = graph_to_json(graph, indent=2, format=args.format)
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_json)
            sys.stderr.write(f"✓ SBOM written to {args.output}\n")
        else:
            sys.stdout.write(out_json + "\n")
        return 0
        
    except RateLimitError as e:
        sys.stderr.write(f"\n❌ ERROR: {e}\n\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"\n❌ ERROR: {e}\n\n")
        return 1


def _cmd_scan(args, token: Optional[str]) -> int:
    """Handle 'scan' command - generate SBOM + scan vulnerabilities."""
    if not token:
        sys.stderr.write("Info: No GitHub token provided. Using unauthenticated API (60 requests/hr).\n\n")
    
    try:
        # Generate SBOM
        sys.stderr.write(f"📦 Generating SBOM for {args.workflow}...\n")
        local = LocalLoader()
        gh = GitHubLoader(token=token)
        builder = GraphBuilder(local_loader=local, github_loader=gh, token=token, max_depth=args.max_depth)
        graph = builder.build_from_workflow(source=args.workflow)
        sbom_json = graph_to_json(graph, indent=2, format="cyclonedx")
        sbom = json.loads(sbom_json)
        sys.stderr.write(f"✓ SBOM generated with {len(sbom.get('components', []))} components\n\n")
        
        # Scan vulnerabilities
        vulns = scan_vulnerabilities(sbom)
        vulns_json = json.dumps(vulns, indent=2)
        
        # Save to files if --output-dir provided
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            sbom_path = output_dir / "sbom.json"
            vulns_path = output_dir / "vulns.json"
            
            with open(sbom_path, "w", encoding="utf-8") as f:
                f.write(sbom_json)
            sys.stderr.write(f"\n✓ SBOM saved to {sbom_path}\n")
            
            with open(vulns_path, "w", encoding="utf-8") as f:
                f.write(vulns_json)
            sys.stderr.write(f"✓ Vulnerability report saved to {vulns_path}\n")
        
        # Exit with code 1 if vulnerabilities found (for CI/CD)
        if vulns.get("total_vulnerabilities", 0) > 0:
            return 1
        return 0
        
    except RateLimitError as e:
        sys.stderr.write(f"\n❌ ERROR: {e}\n\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"\n❌ ERROR: {e}\n\n")
        return 1


def _cmd_vulns(args) -> int:
    """Handle 'vulns' command - scan existing SBOM."""
    try:
        # Load SBOM
        with open(args.sbom, "r", encoding="utf-8") as f:
            sbom = json.load(f)
        
        sys.stderr.write(f"📖 Loaded SBOM from {args.sbom}\n\n")
        
        # Scan vulnerabilities
        vulns = scan_vulnerabilities(sbom)
        vulns_json = json.dumps(vulns, indent=2)
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(vulns_json)
            sys.stderr.write(f"\n✓ Vulnerability report saved to {args.output}\n")
        else:
            sys.stdout.write(vulns_json + "\n")
        
        # Exit with code 1 if vulnerabilities found
        if vulns.get("total_vulnerabilities", 0) > 0:
            return 1
        return 0
        
    except FileNotFoundError:
        sys.stderr.write(f"❌ ERROR: SBOM file not found: {args.sbom}\n")
        return 1
    except json.JSONDecodeError:
        sys.stderr.write(f"❌ ERROR: Invalid JSON in SBOM file: {args.sbom}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"❌ ERROR: {e}\n")
        return 1
