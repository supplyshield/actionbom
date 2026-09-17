export interface Repository {
  id: number;
  org: string;
  name: string;
  provider: string;
  pod: string | null;
  subpod: string | null;
  is_public: boolean;
  workflow_count: number;
  last_scan: string | null;
}

export interface RepositoriesResponse {
  total: number;
  total_tracked: number;
  count: number;
  skip: number;
  limit: number;
  repositories: Repository[];
}

export interface FiltersResponse {
  pods: string[];
  subpods: string[];
}

export interface WorkflowSummary {
  workflow_id: number;
  workflow_name: string | null;
  workflow_path: string;
  branch: string;
  commit_sha: string | null;
  scan_date: string | null;
  started_at: string | null;
  ended_at: string | null;
  status: string;
  vulnerability_count: number;
  sarif_findings: number;
  error_message: string | null;
}

export interface RepositoryInfo {
  id: number;
  org: string;
  name: string;
  full_name: string;
  provider: string;
  pod: string | null;
  subpod: string | null;
}

export interface WorkflowsResponse {
  repository: RepositoryInfo;
  total_workflows: number;
  workflows: WorkflowSummary[];
}

export interface WorkflowDetail {
  workflow_id: number;
  repository: {
    id: number | null;
    org: string | null;
    name: string | null;
    full_name: string;
  };
  workflow_info: {
    name: string | null;
    path: string;
    branch: string;
    commit_sha: string | null;
    repo_name: string;
  };
  scan_info: {
    scan_date: string | null;
    started_at: string | null;
    ended_at: string | null;
    duration: string | null;
    status: string;
    error_message: string | null;
  };
  commit_info: WorkflowCommitInfo | null;
  results: {
    sbom: SbomResult | null;
    vulnerabilities: VulnResult | null;
    sarif: SarifResult | null;
  };
}

export interface SbomResult {
  bomFormat?: string;
  specVersion?: string;
  metadata?: Record<string, unknown>;
  components?: SbomComponent[];
  dependencies?: SbomDependency[];
}

export interface SbomComponent {
  "bom-ref"?: string;
  type: string;
  name: string;
  version?: string;
  purl?: string;
  properties?: Array<{ name: string; value: string }>;
}

export interface SbomDependency {
  ref: string;
  dependsOn?: string[];
}

export interface VulnResult {
  total_vulnerabilities: number;
  severity_counts: Record<string, number>;
  scanned_actions: number;
  vulnerable_actions: number;
  findings: VulnFinding[];
}

export interface VulnFinding {
  action: string;
  version: string;
  advisory_id: string;
  severity: string;
  summary: string;
  details?: string;
  aliases?: string[];
  affected_range?: string;
  fixed_version?: string;
  reference_url?: string;
}

export interface SarifResult {
  $schema?: string;
  version?: string;
  runs?: SarifRun[];
}

export interface SarifRun {
  tool: {
    driver: {
      name: string;
      rules?: SarifRule[];
    };
  };
  results: SarifFinding[];
}

export interface SarifRule {
  id: string;
  name?: string;
  shortDescription?: { text: string };
  fullDescription?: { text: string };
  help?: { text: string; markdown?: string };
  helpUri?: string;
  defaultConfiguration?: { level?: string };
  properties?: { tags?: string[] };
}

export interface SarifLocation {
  message?: { text: string };
  physicalLocation?: {
    artifactLocation?: { uri: string };
    region?: {
      startLine: number;
      endLine?: number;
      startColumn?: number;
      endColumn?: number;
      snippet?: { text: string };
      sourceLanguage?: string;
    };
  };
  logicalLocations?: Array<{
    properties?: {
      symbolic?: {
        route?: { route: Array<{ Key: string }> };
        annotation?: string;
        kind?: string;
      };
    };
  }>;
}

export interface SarifFinding {
  ruleId: string;
  kind?: string;
  message: { text: string };
  level?: string;
  locations?: SarifLocation[];
  relatedLocations?: SarifLocation[];
}

export interface ActionSummary {
  action_name: string;
  version_count: number;
  workflow_count: number;
  repo_count: number;
  vulnerable_count: number;
}

export interface ActionsInventoryResponse {
  total: number;
  count: number;
  skip: number;
  limit: number;
  actions: ActionSummary[];
}

export interface ActionVersionDetail {
  version: string;
  workflow_count: number;
  repo_count: number;
  vulnerable_count: number;
  vulnerabilities: Array<{ id: string; summary: string; severity: string }> | null;
}

export interface ActionWorkflow {
  workflow_id: number;
  repo_name: string;
  workflow_path: string;
  workflow_name: string | null;
  branch: string;
  action_version: string;
  vulnerabilities: Array<{ id: string; summary: string; severity: string }> | null;
  scan_date: string | null;
  status: string;
}

export interface ActionDetailResponse {
  action_name: string;
  versions: ActionVersionDetail[];
  workflows: ActionWorkflow[];
}

export interface WorkflowCommitInfo {
  sha: string | null;
  author: string | null;
}

export interface ImportOrgResponse {
  org: string;
  fetched: number;
  inserted: number;
}
