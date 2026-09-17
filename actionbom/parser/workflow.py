from __future__ import annotations

import re
from typing import Dict, List, Optional

import yaml


def _ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def parse_workflow(text: str) -> Dict[str, List]:
    """Parse a workflow YAML and collect uses from steps and reusable workflows.

    Returns a dict:
      {
        "steps_uses": [{"uses": "owner/repo@ref", "comment_version": "1.2.3" or None}, ...],
        "workflow_uses": [{"uses": "...", "comment_version": None}, ...],
        "name": str | None
      }
    """
    data = yaml.safe_load(text) or {}
    jobs = data.get("jobs", {}) or {}
    steps_uses: List[Dict[str, Optional[str]]] = []
    workflow_uses: List[Dict[str, Optional[str]]] = []
    lines = text.split("\n")

    for job_id, job in (jobs or {}).items():
        if not isinstance(job, dict):
            continue
        # Reusable workflow
        job_uses = job.get("uses")
        if isinstance(job_uses, str):
            comment_ver = _extract_comment_version(text, job_uses, lines)
            workflow_uses.append({"uses": job_uses, "comment_version": comment_ver})

        # Steps
        for step in _ensure_list(job.get("steps")):
            if not isinstance(step, dict):
                continue
            val = step.get("uses")
            if isinstance(val, str):
                comment_ver = _extract_comment_version(text, val, lines)
                steps_uses.append({"uses": val, "comment_version": comment_ver})

    return {
        "steps_uses": steps_uses,
        "workflow_uses": workflow_uses,
        "name": data.get("name"),
    }


def _extract_comment_version(text: str, uses_value: str, lines: List[str]) -> Optional[str]:
    """Extract version from inline comment like '# v1.2.3' or '# 1.2.3'."""
    # Find the line containing this uses value
    match_idx = text.find(uses_value)
    if match_idx < 0:
        return None
    
    line_num = text[:match_idx].count("\n")
    if line_num >= len(lines):
        return None
    
    line = lines[line_num]
    # Look for comment pattern: # v?1.2.3 or # 1.2.3
    comment_match = re.search(r'#\s*v?([0-9]+(?:\.[0-9]+)*)', line)
    if comment_match:
        return comment_match.group(1)
    
    return None
