from __future__ import annotations

import sys
from datetime import datetime
from typing import Dict, List, Any

from .osv_client import query_osv
from .matcher import is_component_vulnerable


def scan_vulnerabilities(sbom: Dict[str, Any]) -> Dict[str, Any]:
    """Scan SBOM components for vulnerabilities using OSV.dev.
    
    Args:
        sbom: CycloneDX SBOM dictionary
    
    Returns:
        Vulnerability report dictionary
    """
    components = sbom.get("components", [])
    
    # Extract GitHub Actions (type=library, purl starts with pkg:github/)
    github_actions = []
    for comp in components:
        if comp.get("type") == "library" and comp.get("purl", "").startswith("pkg:github/"):
            github_actions.append(comp)
    
    sys.stderr.write(f"🔍 Scanning {len(github_actions)} GitHub Actions for vulnerabilities...\n\n")
    
    findings = []
    total_vulns = 0
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0, "UNKNOWN": 0}
    
    for comp in github_actions:
        purl = comp.get("purl", "")
        name = comp.get("name", "")
        version = comp.get("version", "")
        
        # Extract owner/repo from name (format: "owner/repo" or "owner/repo/path")
        name_parts = name.split("/", 2)
        if len(name_parts) >= 2:
            package_name = f"{name_parts[0]}/{name_parts[1]}"
        else:
            continue
        
        # Query OSV
        osv_resp = query_osv(package_name)
        vulns = osv_resp.get("vulns", [])
        
        if not vulns:
            sys.stderr.write(f"✓ {name}@{version} - No known vulnerabilities\n")
            continue
        
        # Filter vulns that actually affect this version
        applicable_vulns = []
        for vuln in vulns:
            if _is_vuln_applicable(vuln, version):
                applicable_vulns.append(vuln)
                
                # Count severity
                sev = _extract_severity(vuln)
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
                total_vulns += 1
        
        if applicable_vulns:
            sys.stderr.write(f"⚠️  {name}@{version} - {len(applicable_vulns)} vulnerabilities\n")
            for vuln in applicable_vulns:
                vuln_id = vuln.get("id", "UNKNOWN")
                sev = _extract_severity(vuln)
                summary = vuln.get("summary", "")[:60]
                sys.stderr.write(f"   └─ {_severity_icon(sev)} {vuln_id} ({sev}) {summary}...\n")
            
            findings.append({
                "component": {
                    "purl": purl,
                    "name": name,
                    "version": version
                },
                "vulnerabilities": applicable_vulns
            })
        else:
            sys.stderr.write(f"✓ {name}@{version} - No applicable vulnerabilities for this version\n")
    
    sys.stderr.write("\n" + "━" * 50 + "\n")
    sys.stderr.write(f"Summary: {total_vulns} vulnerabilities found\n")
    sys.stderr.write(f"  CRITICAL: {severity_counts['CRITICAL']}  ")
    sys.stderr.write(f"HIGH: {severity_counts['HIGH']}  ")
    sys.stderr.write(f"MODERATE: {severity_counts['MODERATE']}  ")
    sys.stderr.write(f"LOW: {severity_counts['LOW']}\n")
    
    return {
        "scan_date": datetime.utcnow().isoformat() + "Z",
        "components_scanned": len(github_actions),
        "vulnerable_components": len(findings),
        "total_vulnerabilities": total_vulns,
        "summary": severity_counts,
        "findings": findings
    }


def _is_vuln_applicable(vuln: Dict, version: str) -> bool:
    """Check if vulnerability applies to this version."""
    affected = vuln.get("affected", [])
    for aff in affected:
        ranges = aff.get("ranges", [])
        if is_component_vulnerable(version, ranges):
            return True
    return False


def _extract_severity(vuln: Dict) -> str:
    """Extract severity from vuln (check multiple possible locations)."""
    # Check database_specific.severity
    db_spec = vuln.get("database_specific", {})
    if "severity" in db_spec:
        return db_spec["severity"].upper()
    
    # Check severity array
    severities = vuln.get("severity", [])
    if severities and isinstance(severities, list):
        for sev in severities:
            if isinstance(sev, dict) and "type" in sev:
                # Extract from CVSS vector
                score = sev.get("score", "")
                if "CRITICAL" in score or score.startswith("10."):
                    return "CRITICAL"
                elif score.startswith("9.") or score.startswith("8.") or score.startswith("7."):
                    return "HIGH"
                elif score.startswith("6.") or score.startswith("5.") or score.startswith("4."):
                    return "MODERATE"
                else:
                    return "LOW"
    
    return "UNKNOWN"


def _severity_icon(severity: str) -> str:
    """Return emoji/icon for severity."""
    icons = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MODERATE": "🟡",
        "LOW": "🔵",
        "UNKNOWN": "⚪"
    }
    return icons.get(severity, "⚪")
