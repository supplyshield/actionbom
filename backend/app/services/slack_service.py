"""Slack notification service for security alerts."""
import sys
from typing import Optional, List, Dict, Any

import requests

from app.config import settings


class SlackService:
    """Posts alerts to Slack via incoming webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL

    def send_template_injection_alert(
        self,
        *,
        repo_full_name: str,
        workflow_path: str,
        branch: str,
        commit_sha: Optional[str],
        findings: List[Dict[str, Any]],
    ) -> bool:
        if not self.webhook_url:
            print("    [slack] webhook URL not configured — skipping alert", file=sys.stderr)
            return False
        if not findings:
            return False

        count = len(findings)
        sha_short = commit_sha[:8] if commit_sha else "?"
        base_url = f"https://github.com/{repo_full_name}/blob/{branch}/{workflow_path}"

        instance_lines = []
        for f in findings[:10]:
            line = f.get("line")
            msg = (f.get("message") or "").strip()
            if line:
                url = f"{base_url}#L{line}"
                instance_lines.append(f"• <{url}|Line {line}> — {msg}")
            else:
                instance_lines.append(f"• {msg}")
        if count > 10:
            instance_lines.append(f"_…and {count - 10} more_")

        text = (
            f"> :alert2: *Template Injection Detected in Workflow*\n"
            f"> \n"
            f"> Repository: `{repo_full_name}`\n"
            f"> \n"
            f"> Workflow File: `{workflow_path}`\n"
            f"> \n"
            f"> Branch: `{branch}`\n"
            f"> \n"
            f"> *Instances:*\n"
            f"> "
            + "\n> ".join(instance_lines)
        )
        if settings.SLACK_CC_USER_ID:
            text += f"\n> \n> _cc: <@{settings.SLACK_CC_USER_ID}>_"

        try:
            resp = requests.post(self.webhook_url, json={"text": text}, timeout=10)
            if resp.status_code >= 300:
                print(
                    f"    [slack] webhook returned {resp.status_code}: {resp.text[:200]}",
                    file=sys.stderr,
                )
                return False
            return True
        except Exception as e:
            print(f"    [slack] post failed: {e}", file=sys.stderr)
            return False


    def send_sca_alert(
        self,
        *,
        action_name: str,
        advisory_id: str,
        summary: str,
        fixed_version: Optional[str],
        workflow_count: int,
        repo_count: int,
    ) -> bool:
        if not self.webhook_url:
            print("    [slack] webhook URL not configured — skipping SCA alert", file=sys.stderr)
            return False

        advisory_url = _advisory_url(advisory_id)
        dashboard_url = f"{settings.DASHBOARD_BASE_URL.rstrip('/')}/actions/{action_name}"
        fix_line = f"Fix available: upgrade to `{fixed_version}`" if fixed_version else "No fix version available yet"

        text = (
            f"> :rotating_light: *Critical SCA Vulnerability Detected*\n"
            f"> \n"
            f"> Action: `{action_name}`\n"
            f"> \n"
            f"> Advisory: <{advisory_url}|{advisory_id}>\n"
            f"> \n"
            f"> Summary: {summary}\n"
            f"> \n"
            f"> {fix_line}\n"
            f"> \n"
            f"> This action is used in *{workflow_count} workflow{'s' if workflow_count != 1 else ''} "
            f"across {repo_count} repo{'s' if repo_count != 1 else ''}*.\n"
            f"> \n"
            f"> <{dashboard_url}|View all affected workflows :arrow_upper_right:>"
        )

        try:
            resp = requests.post(self.webhook_url, json={"text": text}, timeout=10)
            if resp.status_code >= 300:
                print(
                    f"    [slack] SCA webhook returned {resp.status_code}: {resp.text[:200]}",
                    file=sys.stderr,
                )
                return False
            return True
        except Exception as e:
            print(f"    [slack] SCA post failed: {e}", file=sys.stderr)
            return False


def _advisory_url(advisory_id: str) -> str:
    if advisory_id.startswith("GHSA-"):
        return f"https://github.com/advisories/{advisory_id}"
    if advisory_id.startswith("CVE-"):
        return f"https://www.cve.org/CVERecord?id={advisory_id}"
    return f"https://osv.dev/vulnerability/{advisory_id}"


slack_service = SlackService()
