import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { fetchWorkflows } from "@/lib/api";
import {
  FileCode2,
  GitBranch,
  ShieldAlert,
  AlertTriangle,
  Calendar,
  Hash,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import Breadcrumbs from "@/components/Breadcrumbs";
import StatusBadge from "@/components/StatusBadge";

export default function WorkflowsPage() {
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ["workflows", repoId],
    queryFn: () => fetchWorkflows(Number(repoId)),
    enabled: !!repoId,
  });

  useEffect(() => {
    if (error) toast.error("Failed to load workflows", { description: (error as Error).message });
  }, [error]);

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <div>
        <Breadcrumbs
          crumbs={[
            { label: "Repositories", to: "/" },
            {
              label: data?.repository
                ? `${data.repository.org}/${data.repository.name}`
                : `Repository #${repoId}`,
            },
          ]}
        />
      </div>

      {/* Repository info header */}
      {data?.repository && (
        <div className="rounded-xl border border-border/60 bg-card p-5 accent-border-l pl-7">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-foreground tracking-tight">
                Workflows
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                {data.total_workflows} workflow
                {data.total_workflows !== 1 ? "s" : ""} scanned
              </p>
            </div>
            <div className="flex items-center gap-2">
              {data.repository.pod && (
                <span className="inline-flex items-center rounded-md bg-primary/8 text-primary px-2.5 py-0.5 text-[10px] font-mono font-medium tracking-wide">
                  {data.repository.pod}
                </span>
              )}
              {data.repository.subpod && (
                <span className="inline-flex items-center rounded-md bg-secondary text-secondary-foreground px-2.5 py-0.5 text-[10px] font-mono font-medium tracking-wide">
                  {data.repository.subpod}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Loading — shimmer */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border/60 bg-card p-5"
            >
              <div className="h-5 w-1/2 shimmer rounded-md mb-3" />
              <div className="h-4 w-1/3 shimmer rounded-md" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive font-medium">
            Failed to load workflows.
          </p>
          <p className="font-mono text-xs text-muted-foreground mt-2">
            {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {data && data.workflows.length === 0 && (
        <div className="rounded-xl border border-dashed border-border/40 bg-gradient-to-b from-primary/[0.03] to-transparent p-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto mb-4 animate-breathe">
            <FileCode2 size={28} className="text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground">
            No workflows found for this repository.
          </p>
        </div>
      )}

      {/* Workflow list */}
      {data && data.workflows.length > 0 && (
        <div className="space-y-3">
          {data.workflows.map((wf, i) => {
            const hasVulns = wf.vulnerability_count > 0;
            const hasSarif = wf.sarif_findings > 0;

            return (
              <button
                key={wf.workflow_id}
                onClick={() => navigate(`/workflow/${wf.workflow_id}`)}
                className={`w-full text-left rounded-xl border bg-card p-5 card-lift card-glow-border cursor-pointer group animate-fade-in-up ${
                  hasVulns
                    ? "border-destructive/30 hover:glow-destructive"
                    : "border-border/60 hover:border-primary/50 hover:glow-primary"
                }`}
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                      hasVulns
                        ? "bg-destructive/10 group-hover:bg-destructive/15"
                        : "bg-primary/10 group-hover:bg-primary/15"
                    }`}>
                      <FileCode2 size={15} className={hasVulns ? "text-destructive" : "text-primary"} />
                    </div>
                    <span className="font-mono text-sm font-semibold text-foreground truncate">
                      {wf.workflow_name || wf.workflow_path}
                    </span>
                  </div>
                  <StatusBadge status={wf.status} />
                </div>

                <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                  {wf.branch && (
                    <span className="flex items-center gap-1.5">
                      <GitBranch size={12} className="opacity-60" />
                      <span className="font-mono">{wf.branch}</span>
                    </span>
                  )}

                  {wf.commit_sha && (
                    <span className="flex items-center gap-1.5">
                      <Hash size={12} className="opacity-60" />
                      <span className="font-mono">{wf.commit_sha}</span>
                    </span>
                  )}

                  {hasVulns && (
                    <span className="flex items-center gap-1.5 text-destructive">
                      <ShieldAlert size={12} />
                      <span className="font-semibold">
                        {wf.vulnerability_count} vuln
                        {wf.vulnerability_count !== 1 ? "s" : ""}
                      </span>
                    </span>
                  )}

                  {hasSarif && (
                    <span className="flex items-center gap-1.5 text-yellow-600 dark:text-yellow-400">
                      <AlertTriangle size={12} />
                      <span className="font-semibold">
                        {wf.sarif_findings} finding
                        {wf.sarif_findings !== 1 ? "s" : ""}
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

                {wf.error_message && (
                  <p className="mt-2 text-xs text-destructive font-mono truncate opacity-80">
                    {wf.error_message}
                  </p>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
