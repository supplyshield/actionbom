import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { fetchActionDetail } from "@/lib/api";
import {
  Package,
  ShieldAlert,
  FileCode2,
  FolderGit2,
  GitBranch,
  Calendar,
  ExternalLink,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import Breadcrumbs from "@/components/Breadcrumbs";
import StatusBadge from "@/components/StatusBadge";
import SeverityBadge from "@/components/SeverityBadge";
import { cn } from "@/lib/utils";

function advisoryUrlFor(id: string): string | null {
  if (id.startsWith("GHSA-")) return `https://github.com/advisories/${id}`;
  if (id.startsWith("CVE-")) return `https://www.cve.org/CVERecord?id=${id}`;
  return null;
}

export default function ActionDetailPage() {
  const { "*": actionName } = useParams();
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ["action-detail", actionName],
    queryFn: () => fetchActionDetail(actionName!),
    enabled: !!actionName,
  });

  useEffect(() => {
    if (error)
      toast.error("Failed to load action details", {
        description: (error as Error).message,
      });
  }, [error]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-4 w-1/3 shimmer rounded-md" />
        <div className="rounded-xl border border-border/60 bg-card p-6">
          <div className="h-6 w-1/2 shimmer rounded-md mb-4" />
          <div className="h-4 w-1/3 shimmer rounded-md" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 shimmer rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Breadcrumbs
          crumbs={[
            { label: "Actions", to: "/actions" },
            { label: actionName ?? "" },
          ]}
        />
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive font-medium">
            Failed to load action details.
          </p>
          <p className="font-mono text-xs text-muted-foreground mt-2">
            {(error as Error).message}
          </p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const totalWorkflows = data.workflows.length;
  const totalRepos = new Set(data.workflows.map((w) => w.repo_name)).size;
  const totalVulnerable = data.versions.reduce(
    (sum, v) => sum + v.vulnerable_count,
    0
  );
  const hasVulns = totalVulnerable > 0;

  // Aggregate unique vulns across all versions, tracking which versions each affects
  const aggregatedVulns = new Map<
    string,
    { id: string; summary: string; severity: string; versions: string[] }
  >();
  for (const v of data.versions) {
    if (!v.vulnerabilities) continue;
    for (const vuln of v.vulnerabilities) {
      const existing = aggregatedVulns.get(vuln.id);
      if (existing) {
        if (!existing.versions.includes(v.version)) existing.versions.push(v.version);
      } else {
        aggregatedVulns.set(vuln.id, {
          id: vuln.id,
          summary: vuln.summary,
          severity: vuln.severity,
          versions: [v.version],
        });
      }
    }
  }
  const uniqueVulns = Array.from(aggregatedVulns.values());

  // Group workflows by repo
  const workflowsByRepo = new Map<
    string,
    typeof data.workflows
  >();
  for (const wf of data.workflows) {
    const existing = workflowsByRepo.get(wf.repo_name) ?? [];
    existing.push(wf);
    workflowsByRepo.set(wf.repo_name, existing);
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <Breadcrumbs
        crumbs={[
          { label: "Actions", to: "/actions" },
          { label: data.action_name },
        ]}
      />

      {/* Header card */}
      <div
        className={cn(
          "rounded-xl border bg-card p-5 accent-border-l pl-7",
          hasVulns ? "border-destructive/30" : "border-border/60"
        )}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
                hasVulns ? "bg-destructive/10" : "bg-primary/10"
              )}
            >
              {hasVulns ? (
                <ShieldAlert size={20} className="text-destructive" />
              ) : (
                <Package size={20} className="text-primary" />
              )}
            </div>
            <div>
              <h2 className="font-mono text-lg font-semibold text-foreground tracking-tight">
                {data.action_name}
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                Used in {totalWorkflows} workflow
                {totalWorkflows !== 1 ? "s" : ""} across {totalRepos} repo
                {totalRepos !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <a
            href={`https://github.com/${data.action_name}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 bg-secondary/40 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-all duration-200"
          >
            <ExternalLink size={12} />
            GitHub
          </a>
        </div>

        {uniqueVulns.length > 0 && (
          <div className="mt-5 pt-4 border-t border-border/40 space-y-2.5">
            <div className="flex items-center gap-2">
              <ShieldAlert size={14} className="text-destructive" />
              <span className="text-[11px] font-bold text-destructive uppercase tracking-widest">
                Known Vulnerabilities ({uniqueVulns.length})
              </span>
            </div>
            {uniqueVulns.map((vuln) => {
              const advisoryUrl = advisoryUrlFor(vuln.id);
              return (
              <div
                key={vuln.id}
                className="rounded-lg border border-destructive/25 bg-destructive/[0.04] p-3"
              >
                <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5">
                      {vuln.id}
                    </span>
                    <SeverityBadge severity={vuln.severity} />
                    <span className="text-[11px] text-muted-foreground">Affects:</span>
                    {vuln.versions.map((ver) => (
                      <span
                        key={ver}
                        className="font-mono text-[11px] font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5"
                      >
                        @{ver}
                      </span>
                    ))}
                    {advisoryUrl && (
                      <a
                        href={advisoryUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline font-medium ml-auto"
                      >
                        <ExternalLink size={10} />
                        View advisory
                      </a>
                    )}
                  </div>
                </div>
                <p className="text-xs text-secondary-foreground leading-relaxed">
                  {vuln.summary}
                </p>
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          icon={<Package size={18} />}
          label="Versions in Use"
          count={data.versions.length}
          variant="neutral"
        />
        <SummaryCard
          icon={<FileCode2 size={18} />}
          label="Workflows"
          count={totalWorkflows}
          variant="neutral"
        />
        <SummaryCard
          icon={<ShieldAlert size={18} />}
          label="Vulnerable Instances"
          count={totalVulnerable}
          variant={hasVulns ? "destructive" : "success"}
        />
      </div>

      {/* Workflows grouped by repo */}
      <div>
        <div className="flex items-center gap-2.5 mb-4 pb-2 border-b border-border/60">
          <div className="w-8 h-8 rounded-lg bg-destructive/10 flex items-center justify-center">
            <ShieldAlert size={16} className="text-destructive" />
          </div>
          <h3 className="text-xl font-bold text-foreground tracking-tight">
            Affected Workflows
          </h3>
          <span className="font-mono text-xs font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5 ml-1">
            {totalWorkflows}
          </span>
        </div>
        <div className="space-y-4">
          {Array.from(workflowsByRepo.entries()).map(([repoName, wfs]) => (
            <div key={repoName}>
              {/* Repo group header */}
              <div className="flex items-center gap-2 mb-2">
                <FolderGit2 size={13} className="text-muted-foreground/70" />
                <span className="font-mono text-xs font-semibold text-muted-foreground">
                  {repoName}
                </span>
                <span className="text-[10px] text-muted-foreground/50">
                  ({wfs.length})
                </span>
              </div>

              <div className="space-y-2 pl-5 border-l-2 border-border/40">
                {wfs.map((wf) => {
                  const wfVuln =
                    wf.vulnerabilities && wf.vulnerabilities.length > 0;
                  return (
                    <button
                      key={wf.workflow_id}
                      onClick={() => navigate(`/workflow/${wf.workflow_id}`)}
                      className={cn(
                        "w-full text-left rounded-xl border bg-card p-4 card-lift card-glow-border cursor-pointer group",
                        wfVuln
                          ? "border-destructive/25 hover:glow-destructive"
                          : "border-border/60 hover:border-primary/50 hover:glow-primary"
                      )}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div
                            className={cn(
                              "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors",
                              wfVuln
                                ? "bg-destructive/10 group-hover:bg-destructive/15"
                                : "bg-primary/10 group-hover:bg-primary/15"
                            )}
                          >
                            <FileCode2
                              size={13}
                              className={
                                wfVuln ? "text-destructive" : "text-primary"
                              }
                            />
                          </div>
                          <span className="font-mono text-sm font-semibold text-foreground truncate">
                            {wf.workflow_name || wf.workflow_path}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="font-mono text-[10px] text-muted-foreground/60 bg-muted/40 rounded-md px-2 py-0.5">
                            @{wf.action_version}
                          </span>
                          <StatusBadge status={wf.status} />
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <GitBranch size={12} className="opacity-60" />
                          <span className="font-mono">{wf.branch}</span>
                        </span>

                        {wfVuln && (
                          <span className="flex items-center gap-1.5 text-destructive">
                            <ShieldAlert size={12} />
                            <span className="font-semibold">
                              {wf.vulnerabilities!.length} vuln
                              {wf.vulnerabilities!.length !== 1 ? "s" : ""}
                            </span>
                          </span>
                        )}

                        {wf.scan_date && (
                          <span className="flex items-center gap-1.5 ml-auto">
                            <Calendar size={12} className="opacity-60" />
                            {formatDistanceToNow(new Date(wf.scan_date), {
                              addSuffix: true,
                            })}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────── */

function SummaryCard({
  icon,
  label,
  count,
  variant,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
  variant: "destructive" | "warning" | "success" | "neutral";
}) {
  const styles = {
    destructive: "border-destructive/25 text-destructive",
    warning: "border-yellow-500/25 text-yellow-600 dark:text-yellow-400",
    success: "border-primary/25 text-primary",
    neutral: "border-border/60 text-muted-foreground",
  };

  const bgStyles = {
    destructive: "bg-destructive/6",
    warning: "bg-yellow-500/6",
    success: "bg-primary/6",
    neutral: "bg-muted/30",
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-4 flex items-center gap-4 accent-border-l pl-6",
        styles[variant]
      )}
    >
      <div
        className={cn(
          "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
          bgStyles[variant]
        )}
      >
        {icon}
      </div>
      <div>
        <p className="font-mono text-2xl font-bold tracking-tight">{count}</p>
        <p className="text-[11px] text-muted-foreground font-medium">{label}</p>
      </div>
    </div>
  );
}
