# ActionBOM CLI

The core `actionbom` Python package can run standalone against a single
workflow file — useful for CI/CD gates or ad-hoc scans without the
dashboard. For org-wide scanning, use the dashboard (see the [root
README](../README.md)).

## Installation

```bash
git clone https://github.com/YOUR_ORG/actionbom.git
cd actionbom
pip install -r requirements.txt
```

Requires Python 3.10+.

## Commands

### `sbom` — generate SBOM only

```bash
python -m actionbom sbom --workflow .github/workflows/ci.yml --output sbom.json
```

Output formats:
- `--format cyclonedx` (default) — CycloneDX 1.4 JSON
- `--format internal` — internal graph format for debugging

Remote workflows work too:

```bash
python -m actionbom sbom \
  --workflow "github://owner/repo/.github/workflows/ci.yml@main" \
  --token $GITHUB_TOKEN \
  --output sbom.json
```

Limit recursion depth:

```bash
python -m actionbom sbom --workflow ci.yml --max-depth 5 --output sbom.json
```

### `scan` — generate SBOM + scan for vulnerabilities

```bash
python -m actionbom scan \
  --workflow .github/workflows/ci.yml \
  --output-dir results/ \
  --token $GITHUB_TOKEN
```

Writes `results/sbom.json` and `results/vulns.json`. Exits `1` if any
vulnerabilities are found — perfect for CI gates.

Console output:

```
📦 Generating SBOM for .github/workflows/ci.yml...
✓ SBOM generated with 12 components

🔍 Scanning 10 GitHub Actions for vulnerabilities...

✓ actions/checkout@v4 - No known vulnerabilities
⚠️  actions/upload-artifact@v3 - 2 vulnerabilities
   └─ 🔴 GHSA-xxxx-yyyy-zzzz (CRITICAL) Path traversal vulnerability...
   └─ 🟠 GHSA-aaaa-bbbb-cccc (HIGH) Arbitrary file write...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Summary: 2 vulnerabilities found
  CRITICAL: 1  HIGH: 1  MODERATE: 0  LOW: 0
```

### `vulns` — scan existing SBOM

```bash
python -m actionbom vulns --sbom sbom.json --output vulns.json
```

Useful when you've generated the SBOM once and want to re-check against
the current OSV database without re-fetching workflows from GitHub.

## GitHub authentication

Providing a token is recommended:

| Option | How |
|---|---|
| Command-line flag | `python -m actionbom scan --workflow ci.yml --token ghp_xxxxx` |
| `GITHUB_TOKEN` env | `export GITHUB_TOKEN=ghp_xxxxx` |
| `GH_TOKEN` env | `export GH_TOKEN=ghp_xxxxx` |

Rate limits:
- **Without token**: 60 requests/hour
- **With token**: 5000 requests/hour + private repo access

Creating a token: GitHub Settings → Developer settings → Personal access
tokens → Generate new token (Classic). Required scopes: `repo` for
private repos, `public_repo` for public only.

## Output examples

### CycloneDX SBOM (abbreviated)

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "serialNumber": "urn:uuid:...",
  "version": 1,
  "metadata": {
    "tools": [{"vendor": "actionBOM", "name": "actionBOM", "version": "beta 1.0"}]
  },
  "components": [
    {
      "bom-ref": "pkg:github/actions/checkout@v4",
      "type": "library",
      "name": "actions/checkout",
      "version": "v4",
      "purl": "pkg:github/actions/checkout@v4",
      "properties": [
        {"name": "github:action:type", "value": "node"},
        {"name": "github:action:ref", "value": "v4"}
      ]
    },
    {
      "bom-ref": "pkg:docker/alpine@3.19",
      "type": "container",
      "name": "alpine",
      "version": "3.19",
      "purl": "pkg:docker/alpine@3.19"
    }
  ],
  "dependencies": [...]
}
```

### Vulnerability report

```json
{
  "scan_date": "2026-02-18T09:45:00Z",
  "components_scanned": 10,
  "vulnerable_components": 2,
  "total_vulnerabilities": 3,
  "summary": {"CRITICAL": 1, "HIGH": 1, "MODERATE": 1, "LOW": 0},
  "findings": [
    {
      "component": {
        "purl": "pkg:github/actions/upload-artifact@v3",
        "name": "actions/upload-artifact",
        "version": "v3"
      },
      "vulnerabilities": [
        {
          "id": "GHSA-xxxx-yyyy-zzzz",
          "summary": "Path traversal vulnerability in upload-artifact",
          "severity": "CRITICAL"
        }
      ]
    }
  ]
}
```

## What "recursive" means

Consider this workflow:

```yaml
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
```

A flat scanner sees `actions/checkout@v4` and stops. ActionBOM:

1. Detects `actions/checkout@v4`
2. Fetches its `action.yml` from GitHub
3. If it's a composite action, extracts nested `uses:` references
4. Recursively analyzes those too
5. Detects cycles to prevent infinite loops
6. Emits the complete dependency tree

## Using in CI

Because `scan` exits `1` when vulnerabilities are found, a minimal GitHub
Actions gate looks like:

```yaml
- name: ActionBOM scan
  run: |
    pip install -r requirements.txt
    python -m actionbom scan \
      --workflow .github/workflows/ci.yml \
      --output-dir results/ \
      --token ${{ secrets.GITHUB_TOKEN }}

- name: Upload SBOM
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: results/
```

## See also

- [FEATURES.md](../FEATURES.md) — full feature list and behaviors
- [backend/ZIZMOR_INTEGRATION.md](../backend/ZIZMOR_INTEGRATION.md) — SAST integration details
- [OSV.dev](https://osv.dev/) — the vulnerability database ActionBOM queries
- [CycloneDX 1.4 spec](https://cyclonedx.org/docs/1.4/) — SBOM format
