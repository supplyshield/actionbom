"""ActionBOM integration service for scanning workflows."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Optional, Any
import yaml

# Import ActionBOM from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from actionbom.api import full_scan
from actionbom.vulns.scanner import scan_vulnerabilities

from app.config import settings


class ScannerService:
    """Service for scanning workflows using ActionBOM."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
    
    def extract_workflow_name(self, workflow_content: str) -> Optional[str]:
        """Extract workflow name from YAML content."""
        try:
            workflow_data = yaml.safe_load(workflow_content)
            return workflow_data.get("name")
        except Exception:
            return None
    
    def sca_workflow(self, workflow_content: str, repo_name: str, workflow_path: str, repo_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Scan a workflow using ActionBOM.

        Args:
            workflow_content: YAML content of the workflow
            repo_name: Repository name (owner/repo)
            workflow_path: Path to workflow file
            repo_context: Optional dict with owner/repo/branch — when set, local
                (./) refs in the workflow are resolved against the GitHub repo
                instead of the local FS.

        Returns:
            Dictionary with scan results including SBOM and vulnerabilities
        """
        result = {
            "repo_name": repo_name,
            "workflow_path": workflow_path,
            "workflow_name": None,
            "sbom_json": None,
            "vulns_json": None,
            "status": "completed",
            "error_message": None
        }
        
        try:
            # Extract workflow name
            result["workflow_name"] = self.extract_workflow_name(workflow_content)
            
            # Create temporary file for workflow
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.yml',
                delete=False,
                encoding='utf-8'
            ) as tmp_file:
                tmp_file.write(workflow_content)
                tmp_file_path = tmp_file.name
            
            try:
                # Run ActionBOM scan
                print(f"    🔍 Scanning with ActionBOM...")
                sbom, vulns = full_scan(
                    source=tmp_file_path,
                    token=self.token,
                    max_depth=10,
                    source_name=f"{repo_name}/{workflow_path}",
                    repo_context=repo_context,
                )
                
                result["sbom_json"] = sbom
                result["vulns_json"] = vulns
                
                # Log vulnerability summary
                total_vulns = vulns.get("total_vulnerabilities", 0)
                if total_vulns > 0:
                    summary = vulns.get("summary", {})
                    print(f"    ⚠️  Found {total_vulns} vulnerabilities: "
                          f"Critical={summary.get('CRITICAL', 0)}, "
                          f"High={summary.get('HIGH', 0)}, "
                          f"Moderate={summary.get('MODERATE', 0)}, "
                          f"Low={summary.get('LOW', 0)}")
                else:
                    print(f"    ✓ No vulnerabilities found")
                
            finally:
                # Clean up temp file
                Path(tmp_file_path).unlink(missing_ok=True)
        
        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            print(f"    ❌ Scan failed: {e}")
        
        return result
    
    def scan_workflow_with_zizmor(self, workflow_content: str, workflow_path: str) -> Optional[Dict[str, Any]]:
        """
        Scan workflow with Zizmor for security issues (SAST).

        Args:
            workflow_content: YAML content of the workflow
            workflow_path: Path to workflow file (for reporting)

        Returns:
            SARIF-formatted security scan results or None if scan fails
        """
        zizmor_bin = shutil.which("zizmor")
        if not zizmor_bin:
            print(f"    ⚠️  [zizmor] binary not found on PATH ({os.environ.get('PATH', '')}) for {workflow_path}")
            return None

        try:
            # Create temporary file for workflow
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.yml',
                delete=False,
                encoding='utf-8'
            ) as tmp_file:
                tmp_file.write(workflow_content)
                tmp_file_path = tmp_file.name

            try:
                file_size = os.path.getsize(tmp_file_path)
                cmd = [zizmor_bin, '--format', 'sarif', tmp_file_path]
                print(f"    🔒 [zizmor] {workflow_path} → cmd={cmd} tmp_size={file_size}B")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                rc = result.returncode
                stdout = result.stdout or ""
                stderr = result.stderr or ""
                print(
                    f"    [zizmor] rc={rc} stdout_len={len(stdout)} stderr_len={len(stderr)}"
                )
                if stderr:
                    # Log full stderr (zizmor surfaces real errors here, not in stdout)
                    print(f"    [zizmor stderr] {stderr.rstrip()}")

                # Try to parse stdout regardless of return code — zizmor exits non-zero
                # when findings exist, but still emits valid SARIF.
                sarif_output = None
                if stdout:
                    try:
                        sarif_output = json.loads(stdout)
                    except json.JSONDecodeError as e:
                        snippet = stdout[:1000]
                        print(
                            f"    ❌ [zizmor] stdout is not valid JSON for {workflow_path}: {e} "
                            f"| first 1000 chars: {snippet!r}"
                        )

                if sarif_output is None:
                    print(f"    ❌ [zizmor] no usable SARIF for {workflow_path} (rc={rc})")
                    return None

                # Count findings for logging
                total_findings = 0
                if 'runs' in sarif_output and sarif_output['runs']:
                    results = sarif_output['runs'][0].get('results', [])
                    total_findings = len(results)
                    if total_findings > 0:
                        severity_counts = {'error': 0, 'warning': 0, 'note': 0}
                        for finding in results:
                            level = finding.get('level', 'warning')
                            severity_counts[level] = severity_counts.get(level, 0) + 1
                        print(
                            f"    ⚠️  [zizmor] {total_findings} findings for {workflow_path}: "
                            f"errors={severity_counts.get('error', 0)} "
                            f"warnings={severity_counts.get('warning', 0)} "
                            f"notes={severity_counts.get('note', 0)}"
                        )
                    else:
                        print(f"    ✓ [zizmor] no findings for {workflow_path}")

                return sarif_output

            finally:
                Path(tmp_file_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            print(f"    ⚠️  [zizmor] timed out (>30s) for {workflow_path}")
            return None
        except Exception as e:
            print(f"    ❌ [zizmor] unexpected exception for {workflow_path}: {e}")
            print(f"    [zizmor traceback] {traceback.format_exc()}")
            return None

    def sca_from_cached_sbom(self, sbom_json: dict, repo_name: str, workflow_path: str) -> dict:
        """
        Run SCA vulnerability scan using a cached SBOM from the database.
        No GitHub API calls — only queries OSV.dev.

        Args:
            sbom_json: CycloneDX SBOM dict from previous scan
            repo_name: Repository name (for logging)
            workflow_path: Workflow path (for logging)

        Returns:
            Fresh vulnerability scan results dict
        """
        try:
            print(f"    Re-scanning vulnerabilities from cached SBOM...")
            vulns = scan_vulnerabilities(sbom_json)

            total_vulns = vulns.get("total_vulnerabilities", 0)
            if total_vulns > 0:
                summary = vulns.get("summary", {})
                print(f"Found {total_vulns} vulnerabilities: "
                      f"Critical={summary.get('CRITICAL', 0)}, "
                      f"High={summary.get('HIGH', 0)}, "
                      f"Moderate={summary.get('MODERATE', 0)}, "
                      f"Low={summary.get('LOW', 0)}")
            else:
                print(f"No vulnerabilities found")

            return vulns

        except Exception as e:
            print(f"    SCA re-scan failed: {e}")
            return {}


# Singleton instance
scanner_service = ScannerService()
