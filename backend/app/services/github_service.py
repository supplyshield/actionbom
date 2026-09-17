"""GitHub API interaction service."""
import base64
import sys
from typing import List, Dict, Optional
import requests

from app.config import settings


class GitHubService:
    """Service for interacting with GitHub API."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.api_base = settings.GITHUB_API_BASE
        self.session = requests.Session()
        self.last_rate_limit_remaining: Optional[int] = None
    
    def _headers(self) -> dict:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "actionbom-backend/1.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def _check_rate_limit(self, resp: requests.Response) -> Optional[int]:
        """Check rate limit, store remaining count, and log warnings."""
        remaining_str = resp.headers.get("X-RateLimit-Remaining")
        limit = resp.headers.get("X-RateLimit-Limit", "unknown")

        if remaining_str is None:
            return None

        remaining = int(remaining_str)
        self.last_rate_limit_remaining = remaining

        if remaining < 100:
            print(f"WARNING: Rate limit low: {remaining}/{limit} remaining", file=sys.stderr)

        return remaining

    def check_rate_limit(self) -> Optional[int]:
        """Pre-flight rate limit check via GET /rate_limit (free, doesn't count against quota)."""
        url = f"{self.api_base}/rate_limit"
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                remaining = data.get("resources", {}).get("core", {}).get("remaining")
                if remaining is not None:
                    self.last_rate_limit_remaining = remaining
                return remaining
        except Exception as e:
            print(f"WARNING: Failed to check rate limit: {e}", file=sys.stderr)
        return None
    
    def list_org_repos(self, org: str) -> List[Dict]:
        """
        Get all repositories in an organization.
        
        API: GET /orgs/{org}/repos
        """
        repos = []
        page = 1
        
        print(f"📋 Fetching repositories for org: {org}")
        
        while True:
            url = f"{self.api_base}/orgs/{org}/repos"
            params = {
                "per_page": 100,
                "page": page,
                "type": "all"
            }
            
            try:
                resp = self.session.get(url, headers=self._headers(), params=params, timeout=30)
                self._check_rate_limit(resp)
                
                if resp.status_code != 200:
                    print(f"❌ Error fetching repos (page {page}): {resp.status_code}")
                    break
                
                data = resp.json()
                if not data:
                    break
                
                repos.extend(data)
                print(f"  ✓ Fetched page {page}: {len(data)} repos")
                page += 1
                
            except Exception as e:
                print(f"❌ Exception fetching repos: {e}")
                break
        
        print(f"✓ Total repos found: {len(repos)}\n")
        return repos
    
    def get_default_branch(self, owner: str, repo: str) -> str:
        """
        Get the default branch for a repository.

        API: GET /repos/{owner}/{repo}

        Returns:
            Default branch name (e.g. "main", "master"), falls back to "main".
        """
        url = f"{self.api_base}/repos/{owner}/{repo}"
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=30)
            self._check_rate_limit(resp)
            if resp.status_code == 200:
                return resp.json().get("default_branch", "main")
            print(f"  ⚠️  Could not fetch repo metadata: {resp.status_code}, defaulting to 'main'")
        except Exception as e:
            print(f"  ⚠️  Exception fetching repo metadata: {e}, defaulting to 'main'")
        return "main"

    def get_workflow_files(self, owner: str, repo: str, branch: str = "main") -> List[Dict]:
        """
        Get list of workflow files from .github/workflows directory.
        
        API: GET /repos/{owner}/{repo}/contents/.github/workflows
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/contents/.github/workflows"
        params = {"ref": branch}

        try:
            resp = self.session.get(url, headers=self._headers(), params=params, timeout=30)
            self._check_rate_limit(resp)
            
            if resp.status_code == 404:
                # No workflows directory
                return []
            
            if resp.status_code != 200:
                print(f"  ⚠️  Error fetching workflows: {resp.status_code}")
                return []
            
            files = resp.json()
            
            # Filter for .yml and .yaml files only
            workflow_files = [
                f for f in files
                if f.get("type") == "file" and (
                    f.get("name", "").endswith(".yml") or 
                    f.get("name", "").endswith(".yaml")
                )
            ]
            
            return workflow_files
            
        except Exception as e:
            print(f"  ⚠️  Exception fetching workflows: {e}")
            return []
    
    def get_latest_commit_for_file(
        self, owner: str, repo: str, path: str, branch: str
    ) -> Optional[Dict]:
        """
        Fetch the most recent commit that touched a specific file.

        API: GET /repos/{owner}/{repo}/commits?path={path}&sha={branch}&per_page=1

        Returns dict with sha, message, author_login, author_name, author_avatar_url,
        date, html_url — or None if no commit found / API error.
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/commits"
        params = {"path": path, "sha": branch, "per_page": 1}

        try:
            resp = self.session.get(url, headers=self._headers(), params=params, timeout=30)
            self._check_rate_limit(resp)

            if resp.status_code != 200:
                return None

            commits = resp.json()
            if not commits:
                return None

            c = commits[0]
            commit = c.get("commit", {}) or {}
            commit_author = commit.get("author", {}) or {}
            user_author = c.get("author") or {}

            return {
                "sha": c.get("sha"),
                "message": commit.get("message"),
                "author_login": user_author.get("login"),
                "author_name": commit_author.get("name"),
                "author_avatar_url": user_author.get("avatar_url"),
                "date": commit_author.get("date"),
                "html_url": c.get("html_url"),
            }
        except Exception as e:
            print(f"    ⚠️  Exception fetching latest commit: {e}")
            return None

    def fetch_workflow_content(self, owner: str, repo: str, path: str, branch: str = "main") -> Optional[Dict]:
        """
        Fetch workflow file content.
        
        API: GET /repos/{owner}/{repo}/contents/{path}
        
        Returns dict with:
            - content: decoded YAML text
            - sha: file commit SHA
            - name: filename
            - path: full path
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": branch}
        
        try:
            resp = self.session.get(url, headers=self._headers(), params=params, timeout=30)
            self._check_rate_limit(resp)
            
            if resp.status_code != 200:
                print(f"    ⚠️  Error fetching {path}: {resp.status_code}")
                return None
            
            data = resp.json()
            
            # Decode base64 content
            content_b64 = data.get("content", "")
            content_bytes = base64.b64decode(content_b64)
            content_text = content_bytes.decode("utf-8", errors="replace")
            
            return {
                "content": content_text,
                "sha": data.get("sha"),
                "name": data.get("name"),
                "path": data.get("path")
            }
            
        except Exception as e:
            print(f"    ⚠️  Exception fetching workflow: {e}")
            return None


# Singleton instance
github_service = GitHubService()
