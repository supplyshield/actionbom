from __future__ import annotations

from typing import Dict, Optional

import requests


OSV_API_BASE = "https://api.osv.dev"


def query_osv(package_name: str, ecosystem: str = "GitHub Actions") -> Dict:
    """Query OSV.dev API for vulnerabilities in a package.
    
    Args:
        package_name: Package name in format "owner/repo"
        ecosystem: Package ecosystem (default: "GitHub Actions")
    
    Returns:
        OSV API response with vulns[] array
    """
    payload = {
        "package": {
            "name": package_name,
            "ecosystem": ecosystem
        }
    }
    
    url = f"{OSV_API_BASE}/v1/query"
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"vulns": []}
    except Exception as e:
        # Return empty result on error
        return {"vulns": []}


def query_osv_batch(package_names: list[str], ecosystem: str = "GitHub Actions") -> Dict[str, Dict]:
    """Query multiple packages efficiently.
    
    Args:
        package_names: List of package names
        ecosystem: Package ecosystem
    
    Returns:
        Dict mapping package_name to OSV response
    """
    results = {}
    for name in package_names:
        results[name] = query_osv(name, ecosystem)
    return results
