from __future__ import annotations

import base64
import json
import sys
from typing import Optional

import requests


class RateLimitError(Exception):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class GitHubLoader:
    def __init__(self, token: Optional[str] = None, api_base: str = "https://api.github.com") -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")

    def _headers(self) -> dict:
        h = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "actionbom/0.1",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _check_rate_limit(self, resp: requests.Response) -> None:
        """Check if rate limit was hit and raise informative error."""
        if resp.status_code == 403:
            # Check if it's rate limit specific
            remaining = resp.headers.get("X-RateLimit-Remaining", "")
            if remaining == "0":
                reset_time = resp.headers.get("X-RateLimit-Reset", "unknown")
                msg = "GitHub API rate limit exceeded."
                if not self.token:
                    msg += "\n\n💡 TIP: Provide a GitHub token to increase rate limits from 60/hr to 5000/hr:"
                    msg += "\n  Option 1: --token YOUR_TOKEN"
                    msg += "\n  Option 2: export GITHUB_TOKEN=YOUR_TOKEN"
                    msg += "\n  Option 3: export GH_TOKEN=YOUR_TOKEN"
                    msg += f"\n\nRate limit resets at Unix timestamp: {reset_time}"
                else:
                    msg += f"\n\nRate limit resets at Unix timestamp: {reset_time}"
                    msg += "\nYour authenticated rate limit (5000/hr) has been exhausted."
                raise RateLimitError(msg)
            # Other 403 errors (permissions, etc.)
            try:
                err_data = resp.json()
                err_msg = err_data.get("message", "Access forbidden")
            except:
                err_msg = "Access forbidden"
            raise Exception(f"GitHub API error (403): {err_msg}")
        
        if resp.status_code == 401:
            raise Exception("GitHub API authentication failed. Check your token is valid.")

    def resolve_ref_to_sha(self, owner: str, repo: str, ref: str) -> Optional[str]:
        # Use the commits API to resolve arbitrary ref (branch, tag) to a commit SHA
        # GET /repos/{owner}/{repo}/commits/{ref}
        url = f"{self.api_base}/repos/{owner}/{repo}/commits/{ref}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            self._check_rate_limit(resp)
            
            if resp.status_code == 200:
                data = resp.json()
                sha = data.get("sha")
                if isinstance(sha, str):
                    return sha
            elif resp.status_code == 404:
                sys.stderr.write(f"Warning: Ref '{ref}' not found in {owner}/{repo}\n")
        except RateLimitError:
            raise  # Re-raise to stop execution
        except Exception as e:
            sys.stderr.write(f"Warning: Error resolving ref {ref} in {owner}/{repo}: {e}\n")
        return None

    def resolve_sha_to_version(self, owner: str, repo: str, sha: str) -> Optional[str]:
        """Best-effort: map a commit SHA to a concrete release version (e.g., "3.28.5").

        Fallback chain:
          1. Read package.json at the SHA → use its `version` field.
          2. List the repo's tags and find one whose target SHA equals ours
             (handles annotated tags by also checking the dereferenced commit).
          3. Return None — caller falls back to whatever it had.
        """
        # 1) package.json at this SHA (covers most popular Node-based actions)
        pkg_text = self.get_file_text(owner, repo, "package.json", sha)
        if pkg_text:
            try:
                pkg = json.loads(pkg_text)
                version = pkg.get("version")
                if isinstance(version, str) and version.strip():
                    return version.strip()
            except (json.JSONDecodeError, ValueError):
                pass

        # 2) Match the SHA against release tags via /git/matching-refs/tags/
        url = f"{self.api_base}/repos/{owner}/{repo}/git/matching-refs/tags/"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            self._check_rate_limit(resp)
            if resp.status_code == 200:
                refs = resp.json() or []
                # Pass 1: lightweight tags (object.type == 'commit') whose SHA matches directly
                for ref in refs:
                    obj = ref.get("object") or {}
                    if obj.get("type") == "commit" and obj.get("sha") == sha:
                        tag_name = (ref.get("ref") or "").split("/")[-1]
                        if tag_name:
                            return tag_name.lstrip("v")
                # Pass 2: annotated tags — peel each tag object to its commit
                for ref in refs:
                    obj = ref.get("object") or {}
                    if obj.get("type") == "tag":
                        tag_obj_sha = obj.get("sha")
                        if not tag_obj_sha:
                            continue
                        peel_url = f"{self.api_base}/repos/{owner}/{repo}/git/tags/{tag_obj_sha}"
                        try:
                            peel_resp = requests.get(peel_url, headers=self._headers(), timeout=30)
                            self._check_rate_limit(peel_resp)
                            if peel_resp.status_code == 200:
                                peel = peel_resp.json() or {}
                                if (peel.get("object") or {}).get("sha") == sha:
                                    tag_name = (ref.get("ref") or "").split("/")[-1]
                                    if tag_name:
                                        return tag_name.lstrip("v")
                        except RateLimitError:
                            raise
                        except Exception:
                            continue
        except RateLimitError:
            raise
        except Exception as e:
            sys.stderr.write(f"Warning: Error matching tags for {owner}/{repo}@{sha[:8]}: {e}\n")

        return None

    def get_file_text(self, owner: str, repo: str, path: str, ref_or_sha: Optional[str]) -> Optional[str]:
        # GET /repos/{owner}/{repo}/contents/{path}?ref=ref_or_sha
        url = f"{self.api_base}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref_or_sha} if ref_or_sha else None
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            self._check_rate_limit(resp)
            
            if resp.status_code == 200:
                data = resp.json()
                # For files, data is an object with 'content' base64-encoded
                if isinstance(data, dict) and data.get("type") == "file" and "content" in data:
                    b64 = data["content"].encode()
                    # content may contain newlines
                    decoded = base64.b64decode(b"".join(b64.splitlines()))
                    return decoded.decode("utf-8", errors="replace")
            elif resp.status_code == 404:
                # File not found - this is expected for some manifests, don't warn
                pass
        except RateLimitError:
            raise  # Re-raise to stop execution
        except Exception as e:
            sys.stderr.write(f"Warning: Error fetching {path} from {owner}/{repo}: {e}\n")
        return None
