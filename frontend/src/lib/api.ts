import type {
  RepositoriesResponse,
  FiltersResponse,
  WorkflowsResponse,
  WorkflowDetail,
  ActionsInventoryResponse,
  ActionDetailResponse,
  ImportOrgResponse,
} from "@/types/api";

const BASE = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function fetchRepositories(opts: {
  provider?: string;
  skip?: number;
  limit?: number;
  search?: string;
  pod?: string;
  subpod?: string;
} = {}): Promise<RepositoriesResponse> {
  const params = new URLSearchParams();
  params.set("provider", opts.provider ?? "github.com");
  params.set("skip", String(opts.skip ?? 0));
  params.set("limit", String(opts.limit ?? 24));
  if (opts.search) params.set("search", opts.search);
  if (opts.pod) params.set("pod", opts.pod);
  if (opts.subpod) params.set("subpod", opts.subpod);
  return fetchJson(`${BASE}/repositories?${params}`);
}

export function fetchFilters(): Promise<FiltersResponse> {
  return fetchJson(`${BASE}/repositories/filters`);
}

export function fetchWorkflows(repoId: number): Promise<WorkflowsResponse> {
  return fetchJson(`${BASE}/workflows/${repoId}`);
}

export function fetchWorkflowDetail(
  workflowId: number
): Promise<WorkflowDetail> {
  return fetchJson(`${BASE}/workflow/${workflowId}`);
}

export function fetchActionsInventory(opts: {
  search?: string;
  vulnerable_only?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<ActionsInventoryResponse> {
  const params = new URLSearchParams();
  params.set("skip", String(opts.skip ?? 0));
  params.set("limit", String(opts.limit ?? 50));
  if (opts.search) params.set("search", opts.search);
  if (opts.vulnerable_only) params.set("vulnerable_only", "true");
  return fetchJson(`${BASE}/actions?${params}`);
}

export function fetchActionDetail(
  actionName: string
): Promise<ActionDetailResponse> {
  return fetchJson(`${BASE}/actions/${encodeURIComponent(actionName)}`);
}

export async function importOrgRepos(org: string): Promise<ImportOrgResponse> {
  const res = await fetch(`${BASE}/repositories/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ org }),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — keep the statusText fallback
    }
    throw new Error(detail);
  }
  return res.json();
}
