# Zizmor SAST Integration

## Overview

This backend integrates **Zizmor** (by Trail of Bits) for Static Application Security Testing (SAST) of GitHub Actions workflows.

## What is Zizmor?

Zizmor is a specialized security auditing tool for GitHub Actions workflows written in Rust. It detects:

- 🔒 **Injection Vulnerabilities** - Command injection from untrusted inputs
- 🔑 **Permission Issues** - Overly broad or missing `permissions:` blocks
- 🎯 **Dangerous Triggers** - Risky use of `pull_request_target`, `workflow_run`, etc.
- 🔓 **Secret Exposure** - Potential secret leakage patterns
- 📦 **Supply Chain Risks** - Unpinned or risky third-party actions
- ⚠️ **Misconfigurations** - Common security anti-patterns

## Integration Architecture

```
Workflow Scan Pipeline:
┌──────────────────────────────┐
│ 1. Fetch workflow from GitHub│
└───────────┬──────────────────┘
            │
┌───────────▼──────────────────┐
│ 2. ActionBOM Scan (SCA)      │
│    • Generate SBOM            │
│    • Scan dependencies (OSV)  │
└───────────┬──────────────────┘
            │
┌───────────▼──────────────────┐
│ 3. Zizmor Scan (SAST)        │
│    • Security misconfigs      │
│    • Injection vulnerabilities│
│    • Permission issues        │
│    • Output: SARIF format     │
└───────────┬──────────────────┘
            │
┌───────────▼──────────────────┐
│ 4. Store in Database          │
│    • sbom_json (ActionBOM)    │
│    • vulns_json (OSV.dev)     │
│    • sarif_result (Zizmor)    │
└───────────────────────────────┘
```

## Installation

### Option 1: Install with Cargo (Recommended)

```bash
cargo install zizmor
```

### Option 2: Download Pre-built Binary

```bash
# macOS (Apple Silicon)
curl -L https://github.com/woodruffw/zizmor/releases/download/v0.1.0/zizmor-aarch64-apple-darwin -o zizmor
chmod +x zizmor
sudo mv zizmor /usr/local/bin/

# macOS (Intel)
curl -L https://github.com/woodruffw/zizmor/releases/download/v0.1.0/zizmor-x86_64-apple-darwin -o zizmor
chmod +x zizmor
sudo mv zizmor /usr/local/bin/

# Linux
curl -L https://github.com/woodruffw/zizmor/releases/download/v0.1.0/zizmor-x86_64-unknown-linux-gnu -o zizmor
chmod +x zizmor
sudo mv zizmor /usr/local/bin/
```

### Verify Installation

```bash
zizmor --version
```

## Usage in Backend

### Automatic Scanning (Cron Job)

The cron job automatically runs Zizmor after ActionBOM for each workflow:

```bash
python -m app.cron.workflow_scanner
```

### Manual Testing

Test Zizmor on a single workflow:

```bash
# Scan a workflow file
zizmor .github/workflows/ci.yml

# Generate SARIF output
zizmor --format sarif .github/workflows/ci.yml > results.sarif
```

## SARIF Output Format

Zizmor generates SARIF 2.1.0 format:

```json
{
  "version": "2.1.0",
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [{
    "tool": {
      "driver": {
        "name": "zizmor",
        "version": "0.1.0",
        "informationUri": "https://github.com/woodruffw/zizmor"
      }
    },
    "results": [
      {
        "ruleId": "dangerous-triggers",
        "level": "error",
        "message": {
          "text": "Workflow uses dangerous trigger: pull_request_target"
        },
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "workflow.yml"},
            "region": {"startLine": 5, "startColumn": 1}
          }
        }]
      }
    ]
  }]
}
```

## Common Security Issues Detected

### 1. Injection Vulnerabilities

```yaml
# ❌ Dangerous - Command injection risk
- run: echo ${{ github.event.issue.title }}

# ✅ Safe - Use environment variables
- env:
    TITLE: ${{ github.event.issue.title }}
  run: echo "$TITLE"
```

### 2. Overly Permissive Permissions

```yaml
# ❌ Dangerous - Full write access
permissions: write-all

# ✅ Safe - Minimal permissions
permissions:
  contents: read
  issues: write
```

### 3. Dangerous Triggers

```yaml
# ❌ Dangerous - Can execute code from forks
on: pull_request_target

# ✅ Safe - Use pull_request with appropriate checks
on: pull_request
```

### 4. Unpinned Actions

```yaml
# ❌ Risky - Mutable reference
uses: actions/checkout@v4

# ✅ Better - Pinned to commit SHA
uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608  # v4
```

## Database Schema

Results are stored in `actionbom.workflows` table:

```sql
CREATE TABLE actionbom.workflows (
    workflow_id SERIAL PRIMARY KEY,
    repo_id INTEGER NOT NULL,
    repo_name VARCHAR(512) NOT NULL,
    workflow_path VARCHAR(512) NOT NULL,
    
    -- Scan results
    sbom_json JSONB,        -- ActionBOM: SBOM
    vulns_json JSONB,       -- OSV.dev: Vulnerabilities
    sarif_result JSONB,     -- Zizmor: SAST findings (SARIF format)
    
    -- Timing
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    
    ...
);
```

## Error Handling

The integration handles Zizmor errors gracefully:

```python
# If Zizmor is not installed
⚠️  Zizmor not installed. Install with: cargo install zizmor

# If scan times out (>30 seconds)
⚠️  Zizmor scan timed out (>30s)

# If scan fails
⚠️  Zizmor scan failed: <error message>
```

**Important:** If Zizmor fails, the scan continues with ActionBOM results. SAST scanning is optional but recommended.

## Performance

- **Average scan time**: 100-500ms per workflow
- **Timeout**: 30 seconds
- **Impact**: Minimal (Zizmor is written in Rust, very fast)

## GitHub Security Integration

SARIF results can be uploaded to GitHub Security tab:

```bash
# Upload SARIF to GitHub (from CI/CD)
gh api repos/{owner}/{repo}/code-scanning/sarifs \
  -X POST \
  -F sarif=@results.sarif \
  -F commit_sha=$GITHUB_SHA \
  -F ref=$GITHUB_REF
```

## Resources

- **Zizmor Repository**: https://github.com/woodruffw/zizmor
- **SARIF Specification**: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
- **GitHub Actions Security**: https://docs.github.com/en/actions/security-guides

## Troubleshooting

### Zizmor not found

```bash
# Check if zizmor is in PATH
which zizmor

# Add to PATH if needed (macOS/Linux)
export PATH="/path/to/zizmor:$PATH"
```

### Permission denied

```bash
# Make zizmor executable
chmod +x /usr/local/bin/zizmor
```

### Old version

```bash
# Update zizmor
cargo install zizmor --force
```
