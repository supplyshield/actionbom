# ActionBOM Features

## Core Capabilities

### 1. Recursive Dependency Resolution
- Parses GitHub Actions workflows (local and remote)
- Recursively follows all action dependencies through composite actions
- Supports reusable workflows (jobs.<job_id>.uses)
- Handles docker:// image references as leaf nodes
- Detects and prevents infinite loops with cycle detection

### 2. CycloneDX 1.4 SBOM Output (Default)
- Standard-compliant SBOM format
- Clean purl identifiers: `pkg:github/owner/repo@version`
- Human-readable versions (v4, v2, 1.2.3) instead of commit SHAs
- Complete dependency graph with all components
- Properties array for metadata (action type, warnings, original ref)

### 3. Version Comment Parsing (cdxgen-compatible)
- Extracts version from inline comments: `# v1.2.3` or `# 1.2.3`
- Uses comment version as display version in components
- Falls back to ref/tag when no comment exists
- Maintains traceability with original ref in properties

### 4. GitHub API Integration
- Resolves refs/tags to commit SHAs for deterministic versioning
- Fetches action manifests (action.yml/action.yaml) from repos
- Supports both public and private repositories
- Rate limit detection with helpful error messages

### 5. Authentication & Rate Limits
- Multiple token input methods:
  - CLI flag: `--token YOUR_TOKEN`
  - Environment: `GITHUB_TOKEN` or `GH_TOKEN`
- Clear rate limit error messages with setup instructions
- Unauthenticated: 60 req/hr
- Authenticated: 5000 req/hr

### 6. Action Type Detection
- Composite: Recurses into runs.steps[].uses
- Node (node12/16/20/24): Treated as leaf
- Docker: Treated as leaf
- Records action type in properties array

### 7. Error Handling & Resilience
- Rate limit errors: Stop with helpful message
- Missing manifests: Warning in properties, scan continues
- 404 errors: Logged, scan continues
- Invalid tokens: Clear authentication error
- Network errors: Graceful handling with warnings

## Output Formats

### CycloneDX 1.4 (Default)
```bash
python -m actionbom scan --workflow ci.yml
```
- bomFormat: "CycloneDX"
- specVersion: "1.4"
- components[]: All actions/workflows/images with purls
- dependencies[]: Complete graph with purl references
- metadata.component: Root workflow
- properties[]: Per-component metadata

### Internal Graph (Debug)
```bash
python -m actionbom scan --workflow ci.yml --format internal
```
- Nodes with full coordinates
- Edges with cycle flags
- Warnings and metadata
- Useful for debugging traversal issues

## Supported Input Types

### Local Workflows
```bash
python -m actionbom scan --workflow .github/workflows/ci.yml
```

### Remote Workflows (GitHub URI)
```bash
python -m actionbom scan --workflow "github://owner/repo/.github/workflows/ci.yml@main" --token $GH_TOKEN
```

### Action Types Resolved
1. **GitHub Actions:** `owner/repo@ref` or `owner/repo/path@ref`
2. **Reusable Workflows:** `owner/repo/.github/workflows/file.yml@ref`
3. **Local Actions:** `./path/to/action`
4. **Docker Images:** `docker://image:tag` or `docker://image@digest`

## Purl Format

### GitHub Actions
- Simple: `pkg:github/actions/checkout@v4`
- With subpath: `pkg:github/owner/repo@v1#path/to/action`
- Version priority: display_version > ref > sha

### Docker Images
- With tag: `pkg:docker/alpine@3.19`
- With digest: `pkg:docker/nginx@sha256:abc123...`

### Local Components
- No purl (uses bom-ref as internal ID)

## CLI Options

```bash
python -m actionbom scan --workflow <path|github-uri> [options]

Required:
  --workflow PATH|URI     Workflow file path or github:// URI

Optional:
  --token TOKEN          GitHub token (or use GITHUB_TOKEN env var)
  --output FILE          Write to file instead of stdout
  --max-depth N          Limit recursion depth (default: unlimited)
  --format FORMAT        Output format: cyclonedx (default) | internal
```

## Dependencies

- Python 3.10+
- PyYAML >= 6.0 (YAML parsing)
- requests >= 2.31.0 (GitHub API calls)

## Key Differentiators vs cdxgen

| Feature | cdxgen | actionbom |
|---------|--------|-----------|
| Recursion | ❌ Flat scan only | ✅ Full transitive closure |
| Composite actions | ❌ Not expanded | ✅ Recursively parsed |
| Reusable workflows | ❌ Not expanded | ✅ Recursively parsed |
| Version comments | ✅ Parsed | ✅ Parsed |
| Ref→SHA resolution | ❌ No | ✅ Yes (via GitHub API) |
| Cycle detection | N/A | ✅ Yes |
| Rate limit handling | Basic | ✅ Detailed with suggestions |
| Format | CycloneDX | ✅ CycloneDX 1.4 (default) |
