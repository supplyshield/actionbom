"""Daily batch cron job for scanning org workflows."""
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import SessionLocal
from app.models import ScaAlertSent, Workflow
from app.repositories.repository_repo import RepositoryRepository
from app.repositories.workflow_repo import WorkflowRepository
from app.repositories.org_action_repo import OrgActionRepository
from app.services.github_service import github_service
from app.services.scanner_service import scanner_service
from app.services.slack_service import slack_service


def _banner():
    print("=" * 80)
    print(f"CRON JOB STARTED: Daily Batch Scan")
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"Batch size: {settings.BATCH_SIZE}  |  Rate limit threshold: {settings.RATE_LIMIT_THRESHOLD}")
    print("=" * 80 + "\n")


def _print_summary(stats: dict):
    print("\n" + "=" * 80)
    print("BATCH SCAN COMPLETED")
    print("=" * 80)
    print(f"Summary:")
    print(f"  Repos scanned:              {stats['repos_scanned']}")
    print(f"  Repos skipped (rate limit): {stats['repos_skipped_rate_limit']}")
    print(f"  Workflows found:            {stats['workflows_found']}")
    print(f"  Workflows scanned (full):   {stats['workflows_scanned_full']}")
    print(f"  Workflows scanned (SCA):    {stats['workflows_scanned_sca_only']}")
    print(f"  Workflows failed:           {stats['workflows_failed']}")
    print(f"  Vulnerabilities found:      {stats['vulnerabilities_found']}")
    if stats['rate_limit_remaining'] is not None:
        print(f"  Rate limit remaining:       {stats['rate_limit_remaining']}")
    print(f"  Completed at: {datetime.utcnow().isoformat()}")
    print("=" * 80 + "\n")





def _commit_author(commit_info):
    """Pick author login (preferred) or fall back to git author name."""
    if not commit_info:
        return None
    return commit_info.get("author_login") or commit_info.get("author_name")


def _qualifying_template_injection_results(sarif):
    """SARIF results with ruleId=template-injection and level=error."""
    if not sarif:
        return []
    runs = sarif.get("runs") or []
    if not runs:
        return []
    out = []
    for r in runs[0].get("results") or []:
        if r.get("ruleId") != "template-injection":
            continue
        if r.get("level") != "error":
            continue
        out.append(r)
    return out


def _finding_fingerprint(result):
    """(ruleId, message text, primary startLine) — None-safe."""
    rule = result.get("ruleId")
    msg = (result.get("message") or {}).get("text")
    line = None
    locs = result.get("locations") or []
    if locs:
        region = (locs[0].get("physicalLocation") or {}).get("region") or {}
        line = region.get("startLine")
    return (rule, msg, line)


def _new_template_injection_alerts(prev_sarif, new_sarif):
    """Qualifying findings present in new_sarif but not prev_sarif.

    prev_sarif=None → all qualifying findings in new_sarif are "new".
    """
    new_qualifying = _qualifying_template_injection_results(new_sarif)
    if not new_qualifying:
        return []
    prev_keys = {
        _finding_fingerprint(r)
        for r in _qualifying_template_injection_results(prev_sarif)
    }

    alerts = []
    for r in new_qualifying:
        if _finding_fingerprint(r) in prev_keys:
            continue
        line = None
        locs = r.get("locations") or []
        if locs:
            region = (locs[0].get("physicalLocation") or {}).get("region") or {}
            line = region.get("startLine")
        alerts.append({
            "rule_id": r.get("ruleId"),
            "level": r.get("level"),
            "message": (r.get("message") or {}).get("text", ""),
            "line": line,
        })
    return alerts


def _extract_actions_from_scan(sbom_json, vulns_json):
    """
    Extract actions and their matched vulnerabilities from SBOM + vulns.

    Returns:
        List of dicts: [{action_name, action_version, vulnerabilities}, ...]
    """
    if not sbom_json:
        return []

    # Build a lookup: component name -> list of vulns
    vuln_lookup = {}
    if vulns_json and vulns_json.get("findings"):
        for finding in vulns_json["findings"]:
            comp = finding.get("component", {})
            comp_name = comp.get("name")
            if comp_name:
                vuln_lookup[comp_name] = finding.get("vulnerabilities", [])

    target_org = (settings.TARGET_ORG or "").lower()
    actions = []
    for component in sbom_json.get("components", []):
        action_name = component.get("name")
        action_version = component.get("version")
        purl = (component.get("purl") or "").lower()
        if not action_name:
            continue

        # Third-party supply-chain dependencies only:
        # - Drop components without a purl (workflow root + local actions)
        # - Drop first-party GitHub actions owned by TARGET_ORG
        # Keeps third-party github actions, third-party reusable workflows,
        # and docker images (pkg:docker/...).
        if not purl:
            continue
        if target_org and purl.startswith(f"pkg:github/{target_org}/"):
            continue

        # Match vulns for this component
        matched_vulns = vuln_lookup.get(action_name, [])
        vuln_data = None
        if matched_vulns:
            vuln_data = []
            for v in matched_vulns:
                fixed_version = None
                for affected in v.get("affected", []):
                    for rng in affected.get("ranges", []):
                        for event in rng.get("events", []):
                            if "fixed" in event:
                                fixed_version = event["fixed"]
                                break
                        if fixed_version:
                            break
                    if fixed_version:
                        break
                vuln_data.append({
                    "id": v.get("id"),
                    "summary": v.get("summary"),
                    "severity": v.get("database_specific", {}).get("severity", "UNKNOWN"),
                    "fixed_version": fixed_version,
                })

        actions.append({
            "action_name": action_name,
            "action_version": action_version,
            "vulnerabilities": vuln_data,
        })

    return actions


def _dispatch_sca_alerts(db, actions_list):
    """Send Slack alerts for new CRITICAL advisories. One alert per (action, advisory) ever."""
    for action in actions_list:
        action_name = action.get("action_name")
        for vuln in action.get("vulnerabilities") or []:
            if (vuln.get("severity") or "").upper() != "CRITICAL":
                continue
            advisory_id = vuln.get("id")
            if not advisory_id or not action_name:
                continue

            # Check dedup table — skip if we've alerted on this pair before
            already_sent = db.query(ScaAlertSent).filter_by(
                action_name=action_name,
                advisory_id=advisory_id,
            ).first()
            if already_sent:
                continue

            # Count all workflows/repos that use this action (dashboard-consistent)
            usage = OrgActionRepository.get_action_usage_count(db, action_name)

            sent = slack_service.send_sca_alert(
                action_name=action_name,
                advisory_id=advisory_id,
                summary=vuln.get("summary") or "",
                fixed_version=vuln.get("fixed_version"),
                workflow_count=usage["workflow_count"],
                repo_count=usage["repo_count"],
            )

            if sent:
                stmt = pg_insert(ScaAlertSent).values(
                    action_name=action_name,
                    advisory_id=advisory_id,
                ).on_conflict_do_nothing()
                db.execute(stmt)
                db.commit()
                print(f"    [sca-alert] sent + recorded: {action_name} / {advisory_id}")


def daily_batch_scan_job():
    """Daily cron job: scan a batch of repos, rotating by staleness."""
    _banner()
    db = SessionLocal()
    try:
        # 1. Pre-flight: check rate limit
        remaining = github_service.check_rate_limit()
        if remaining is not None and remaining < settings.RATE_LIMIT_THRESHOLD:
            print(f"ABORT: Rate limit too low ({remaining} remaining, "
                  f"threshold: {settings.RATE_LIMIT_THRESHOLD}). Skipping this run.\n")
            return

        # 2. Get batch of repos ordered by staleness (never-scanned first)
        batch = RepositoryRepository.get_batch_for_scanning(
            db,
            batch_size=settings.BATCH_SIZE
        )

        if not batch:
            print("No GitHub repositories found to scan.\n")
            return

        print(f"Batch: {len(batch)} repos selected for scanning\n")

        stats = {
            "repos_scanned": 0,
            "repos_skipped_rate_limit": 0,
            "workflows_found": 0,
            "workflows_scanned_full": 0,
            "workflows_scanned_sca_only": 0,
            "workflows_failed": 0,
            "vulnerabilities_found": 0,
            "rate_limit_remaining": remaining,
        }

        # 3. Process each repo
        for idx, (repo, last_attempted) in enumerate(batch, 1):
            repo_full_name = f"{repo.org}/{repo.name}"
            last_attempted_str = last_attempted.isoformat() if last_attempted else "never"
            print(f"[{idx}/{len(batch)}] {repo_full_name} (last visited: {last_attempted_str})")

            # 3a. Rate limit check before each repo
            current_remaining = github_service.last_rate_limit_remaining
            if current_remaining is not None and current_remaining < settings.RATE_LIMIT_THRESHOLD:
                print(f"  STOPPING: Rate limit low ({current_remaining} remaining). "
                      f"Will resume from here on next run.\n")
                stats["repos_skipped_rate_limit"] = len(batch) - idx + 1
                stats["rate_limit_remaining"] = current_remaining
                break

            # 3b. Get default branch and list workflow files
            default_branch = github_service.get_default_branch(
                owner=repo.org,
                repo=repo.name
            )
            print(f"  Branch: {default_branch}")

            workflow_files = github_service.get_workflow_files(
                owner=repo.org,
                repo=repo.name,
                branch=default_branch
            )

            if not workflow_files:
                print(f"  No workflows found")
                RepositoryRepository.touch_scan_log(db, repo.id)
                db.commit()
                stats["repos_scanned"] += 1
                continue

            print(f"  Found {len(workflow_files)} workflows")
            stats["workflows_found"] += len(workflow_files)

            # 3c. Process each workflow
            for wf_file in workflow_files:
                workflow_path = wf_file["path"]
                workflow_name = wf_file["name"]

                print(f"  >> {workflow_name}")

                # Fetch content to get SHA
                workflow_data = github_service.fetch_workflow_content(
                    owner=repo.org,
                    repo=repo.name,
                    path=workflow_path,
                    branch=default_branch
                )

                if not workflow_data:
                    print(f"    FAIL: Could not fetch content")
                    stats["workflows_failed"] += 1
                    continue

                commit_sha = workflow_data["sha"]
                content = workflow_data["content"]

                # 3d. Check for previous scan of this workflow
                prev_scan = WorkflowRepository.get_latest_scan_for_workflow(
                    db, repo_full_name, workflow_path
                )

                if prev_scan and prev_scan.commit_sha == commit_sha and prev_scan.sbom_json:
                    # SHA unchanged — reuse SBOM + SARIF, only re-run SCA
                    print(f"    SHA unchanged ({commit_sha[:8]}) — SCA-only re-scan")
                    vulns = scanner_service.sca_from_cached_sbom(
                        sbom_json=prev_scan.sbom_json,
                        repo_name=repo_full_name,
                        workflow_path=workflow_path
                    )

                    # Update existing row with fresh vulns and scan_date
                    prev_scan.vulns_json = vulns
                    prev_scan.scan_date = datetime.utcnow()

                    # Backfill commit info on rows that pre-date this feature
                    if prev_scan.last_commit_sha is None:
                        commit_info = github_service.get_latest_commit_for_file(
                            owner=repo.org,
                            repo=repo.name,
                            path=workflow_path,
                            branch=default_branch,
                        )
                        if commit_info:
                            prev_scan.last_commit_sha = commit_info.get("sha")
                            prev_scan.last_commit_author = _commit_author(commit_info)

                    # Update org_actions with fresh vuln data
                    actions_list = _extract_actions_from_scan(prev_scan.sbom_json, vulns)
                    OrgActionRepository.replace_actions_for_workflow(
                        db,
                        workflow_id=prev_scan.workflow_id,
                        repo_name=repo_full_name,
                        workflow_path=workflow_path,
                        actions=actions_list,
                    )
                    db.commit()
                    _dispatch_sca_alerts(db, actions_list)

                    total_vulns = vulns.get("total_vulnerabilities", 0) if vulns else 0
                    stats["vulnerabilities_found"] += total_vulns
                    stats["workflows_scanned_sca_only"] += 1

                else:
                    # SHA changed or never scanned — full scan
                    if prev_scan:
                        print(f"    SHA changed ({prev_scan.commit_sha[:8] if prev_scan.commit_sha else '?'} -> {commit_sha[:8]}) — full scan")
                    else:
                        print(f"    First scan — full scan")

                    started_at = datetime.utcnow()

                    # SCA: SBOM generation + vulnerability scan
                    scan_result = scanner_service.sca_workflow(
                        workflow_content=content,
                        repo_name=repo_full_name,
                        workflow_path=workflow_path,
                        repo_context={
                            "owner": repo.org,
                            "repo": repo.name,
                            "branch": default_branch,
                        },
                    )

                    # SAST: Zizmor
                    sarif_result = scanner_service.scan_workflow_with_zizmor(
                        workflow_content=content,
                        workflow_path=workflow_path
                    )

                    ended_at = datetime.utcnow()

                    # Fetch latest commit that touched this file (author + git SHA)
                    commit_info = github_service.get_latest_commit_for_file(
                        owner=repo.org,
                        repo=repo.name,
                        path=workflow_path,
                        branch=default_branch,
                    )

                    # Store results
                    new_workflow = Workflow(
                        repo_id=repo.id,
                        repo_name=repo_full_name,
                        workflow_path=workflow_path,
                        workflow_name=scan_result.get("workflow_name"),
                        commit_sha=commit_sha,
                        branch=default_branch,
                        started_at=started_at,
                        ended_at=ended_at,
                        sbom_json=scan_result.get("sbom_json"),
                        vulns_json=scan_result.get("vulns_json"),
                        sarif_result=sarif_result,
                        status=scan_result.get("status"),
                        error_message=scan_result.get("error_message"),
                        last_commit_sha=commit_info.get("sha") if commit_info else None,
                        last_commit_author=_commit_author(commit_info),
                    )

                    db.add(new_workflow)
                    db.flush()  # get new_workflow.workflow_id before commit

                    # Populate org_actions
                    actions_list = []
                    if scan_result["status"] == "completed":
                        actions_list = _extract_actions_from_scan(
                            scan_result.get("sbom_json"),
                            scan_result.get("vulns_json"),
                        )
                        # Delete old rows from previous scan (if any)
                        OrgActionRepository.replace_actions_for_workflow(
                            db,
                            workflow_id=new_workflow.workflow_id,
                            repo_name=repo_full_name,
                            workflow_path=workflow_path,
                            actions=actions_list,
                        )

                    db.commit()
                    _dispatch_sca_alerts(db, actions_list)

                    prev_sarif = prev_scan.sarif_result if prev_scan else None
                    new_alerts = _new_template_injection_alerts(prev_sarif, sarif_result)
                    if new_alerts:
                        slack_service.send_template_injection_alert(
                            repo_full_name=repo_full_name,
                            workflow_path=workflow_path,
                            branch=default_branch,
                            commit_sha=commit_sha,
                            findings=new_alerts,
                        )

                    if scan_result["status"] == "completed":
                        stats["workflows_scanned_full"] += 1
                        vulns = scan_result.get("vulns_json", {})
                        total_vulns = vulns.get("total_vulnerabilities", 0) if vulns else 0
                        stats["vulnerabilities_found"] += total_vulns
                    else:
                        stats["workflows_failed"] += 1

            RepositoryRepository.touch_scan_log(db, repo.id)
            db.commit()
            stats["repos_scanned"] += 1
            print()  # blank line between repos

        # Update final rate limit
        if github_service.last_rate_limit_remaining is not None:
            stats["rate_limit_remaining"] = github_service.last_rate_limit_remaining

        _print_summary(stats)

    except Exception as e:
        print(f"\nCRON JOB FAILED: {e}\n")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Running batch scan manually for testing...\n")
    daily_batch_scan_job()
