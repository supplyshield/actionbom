import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { fetchWorkflowDetail } from "@/lib/api";
import {
  ShieldAlert,
  Shield,
  AlertTriangle,
  Package,
  GitBranch,
  FileCode2,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Code2,
  ArrowRight,
  Info,
  Copy,
  Check,
  GitCommit,
} from "lucide-react";
import { toast } from "sonner";
import Breadcrumbs from "@/components/Breadcrumbs";
import StatusBadge from "@/components/StatusBadge";
import SeverityBadge from "@/components/SeverityBadge";
import type {
  VulnFinding,
  SarifFinding,
  SarifRule,
  SbomComponent,
  SbomDependency,
} from "@/types/api";
import SbomGraphView from "@/components/SbomGraphView";
import { cn } from "@/lib/utils";

type Tab = "vulnerabilities" | "sarif" | "sbom";

export default function WorkflowDetailPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("sbom");

  // Sliding tab indicator
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ vulnerabilities: null, sarif: null, sbom: null });
  const [indicatorStyle, setIndicatorStyle] = useState<{ left: number; width: number }>({ left: 0, width: 0 });

  useEffect(() => {
    const el = tabRefs.current[activeTab];
    if (el) {
      const parent = el.parentElement;
      if (parent) {
        const parentRect = parent.getBoundingClientRect();
        const elRect = el.getBoundingClientRect();
        setIndicatorStyle({ left: elRect.left - parentRect.left, width: elRect.width });
      }
    }
  }, [activeTab]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => fetchWorkflowDetail(Number(workflowId)),
    enabled: !!workflowId,
  });

  useEffect(() => {
    if (error) toast.error("Failed to load workflow details", { description: (error as Error).message });
  }, [error]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-4 w-1/3 shimmer rounded-md" />
        <div className="rounded-xl border border-border/60 bg-card p-6">
          <div className="h-6 w-1/2 shimmer rounded-md mb-4" />
          <div className="h-4 w-1/3 shimmer rounded-md mb-2" />
          <div className="h-4 w-1/4 shimmer rounded-md" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 shimmer rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive font-medium">Failed to load workflow details.</p>
        <p className="font-mono text-xs text-muted-foreground mt-2">
          {(error as Error).message}
        </p>
      </div>
    );
  }

  if (!data) return null;

  const { workflow_info, scan_info, results, repository, commit_info } = data;

  const vulns = results.vulnerabilities;
  const vulnFindings: VulnFinding[] = vulns?.findings ?? [];
  const totalVulns = vulns?.total_vulnerabilities ?? 0;
  const severityCounts: Record<string, number> = vulns?.severity_counts ?? {};

  const sarifRun = results.sarif?.runs?.[0];
  const sarifFindings: SarifFinding[] = sarifRun?.results ?? [];
  const sarifRules: SarifRule[] = sarifRun?.tool?.driver?.rules ?? [];
  const sarifRulesMap = new Map(sarifRules.map((r) => [r.id, r]));

  const sbomComponents: SbomComponent[] = results.sbom?.components ?? [];
  const sbomDependencies: SbomDependency[] = results.sbom?.dependencies ?? [];

  const repoName = repository.full_name;

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <Breadcrumbs
        crumbs={[
          { label: "Repositories", to: "/" },
          {
            label: repoName,
            to: repository.id ? `/repo/${repository.id}` : undefined,
          },
          { label: workflow_info.name || workflow_info.path },
        ]}
      />

      {/* Workflow header */}
      <div className="rounded-xl border border-border/60 bg-card p-5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <FileCode2 size={17} className="text-primary" />
            </div>
            <h2 className="font-mono text-lg font-semibold text-foreground tracking-tight">
              {workflow_info.name || workflow_info.path}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={`https://github.com/${repoName}/blob/${workflow_info.branch}/${workflow_info.path}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 bg-secondary/40 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-all duration-200"
            >
              <ExternalLink size={12} />
              GitHub
            </a>
            <StatusBadge status={scan_info.status} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <InfoBlock
            icon={<FileCode2 size={13} />}
            label="Path"
            value={workflow_info.path}
          />
          <InfoBlock
            icon={<GitBranch size={12} />}
            label="Branch"
            value={workflow_info.branch}
          />
        </div>

        {/* Last commit */}
        {(commit_info?.author || commit_info?.sha) && (
          <div className="mt-3 flex items-center gap-2.5 text-xs text-muted-foreground bg-muted/30 rounded-lg px-3 py-2">
            <GitCommit size={13} className="text-muted-foreground/70 shrink-0" />
            {commit_info.author && (
              <span className="font-mono font-semibold text-foreground">
                {commit_info.author}
              </span>
            )}
            {commit_info.sha && (
              <span className="font-mono">
                {commit_info.sha.slice(0, 7)}
              </span>
            )}
          </div>
        )}

        {scan_info.error_message && (
          <div className="mt-3 rounded-lg bg-destructive/8 border border-destructive/20 p-3">
            <p className="text-xs text-destructive font-mono">
              {scan_info.error_message}
            </p>
          </div>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          icon={<ShieldAlert size={18} />}
          label="SCA Vulnerabilities"
          count={totalVulns}
          variant={totalVulns > 0 ? "destructive" : "success"}
        />
        <SummaryCard
          icon={<AlertTriangle size={18} />}
          label="SAST Issues"
          count={sarifFindings.length}
          variant={sarifFindings.length > 0 ? "warning" : "success"}
        />
        <SummaryCard
          icon={<Package size={18} />}
          label="SBOM Components"
          count={sbomComponents.length}
          variant="neutral"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-border/60">
        <div className="relative flex gap-0">
          <TabButton
            ref={(el) => { tabRefs.current.sbom = el; }}
            active={activeTab === "sbom"}
            onClick={() => setActiveTab("sbom")}
            count={sbomComponents.length}
          >
            SBOM
          </TabButton>
          <TabButton
            ref={(el) => { tabRefs.current.vulnerabilities = el; }}
            active={activeTab === "vulnerabilities"}
            onClick={() => setActiveTab("vulnerabilities")}
            count={totalVulns}
          >
            SCA Vulnerabilities
          </TabButton>
          <TabButton
            ref={(el) => { tabRefs.current.sarif = el; }}
            active={activeTab === "sarif"}
            onClick={() => setActiveTab("sarif")}
            count={sarifFindings.length}
          >
            SAST Issues
          </TabButton>
          {/* Sliding indicator */}
          <div
            className="absolute bottom-0 h-0.5 bg-primary rounded-full transition-all duration-300 ease-out"
            style={{ left: indicatorStyle.left, width: indicatorStyle.width }}
          />
        </div>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "vulnerabilities" && (
          <VulnerabilitiesTab
            findings={vulnFindings}
            severityCounts={severityCounts}
            total={totalVulns}
          />
        )}
        {activeTab === "sarif" && (
          <SarifTab
            findings={sarifFindings}
            rulesMap={sarifRulesMap}
            githubFileUrl={`https://github.com/${repoName}/blob/${workflow_info.branch}/${workflow_info.path}`}
          />
        )}
        {activeTab === "sbom" && (
          <SbomGraphView
            components={sbomComponents}
            dependencies={sbomDependencies}
            vulnFindings={vulnFindings}
          />
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────── */

function InfoBlock({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-muted/40 rounded-lg px-3 py-2.5">
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="text-muted-foreground/70">{icon}</span>
        <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-medium">
          {label}
        </span>
      </div>
      <p className="font-mono text-sm text-foreground truncate">{value}</p>
    </div>
  );
}

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
      <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0", bgStyles[variant])}>
        {icon}
      </div>
      <div>
        <p className="font-mono text-2xl font-bold tracking-tight">{count}</p>
        <p className="text-[11px] text-muted-foreground font-medium">{label}</p>
      </div>
    </div>
  );
}

import React from "react";

const TabButton = React.forwardRef<
  HTMLButtonElement,
  {
    active: boolean;
    onClick: () => void;
    count: number;
    children: React.ReactNode;
  }
>(({ active, onClick, count, children }, ref) => {
  return (
    <button
      ref={ref}
      onClick={onClick}
      className={cn(
        "px-4 py-2.5 text-sm font-medium transition-all duration-200",
        active
          ? "text-primary"
          : "text-muted-foreground hover:text-foreground"
      )}
    >
      {children}
      {count > 0 && (
        <span
          className={cn(
            "ml-2 font-mono text-[10px] rounded-full px-2 py-0.5 font-semibold",
            active
              ? "bg-primary/10 text-primary"
              : "bg-muted text-muted-foreground"
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
});
TabButton.displayName = "TabButton";

/* ── Vulnerabilities Tab ─────────────────────────────────────── */

function VulnerabilitiesTab({
  findings,
  severityCounts,
  total,
}: {
  findings: VulnFinding[];
  severityCounts: Record<string, number>;
  total: number;
}) {
  if (total === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/40 bg-gradient-to-b from-primary/[0.03] to-transparent p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-primary/8 flex items-center justify-center mx-auto mb-4 animate-breathe">
          <Shield size={28} className="text-primary" />
        </div>
        <p className="text-sm text-muted-foreground">
          No vulnerabilities found.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Severity breakdown */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(severityCounts)
          .filter(([, count]) => count > 0)
          .sort(
            ([a], [b]) =>
              severityOrder(a) - severityOrder(b)
          )
          .map(([sev, count]) => (
            <div
              key={sev}
              className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-card px-3.5 py-2"
            >
              <SeverityBadge severity={sev} />
              <span className="font-mono text-sm font-bold">{count}</span>
            </div>
          ))}
      </div>

      {/* Findings list */}
      <div className="space-y-3">
        {findings.map((f, i) => {
          const sev = f.severity?.toLowerCase();
          return (
          <div
            key={`${f.advisory_id}-${i}`}
            className={cn(
              "rounded-xl border bg-card p-4 pl-6 animate-fade-in-up",
              sev === "critical"
                ? "border-destructive/35 accent-border-l-destructive bg-destructive/[0.03]"
                : sev === "high"
                ? "border-orange-500/25 accent-border-l-warning"
                : "border-border/60"
            )}
            style={{ animationDelay: `${i * 30}ms` }}
          >
            <div className="flex items-start justify-between mb-2 gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <ShieldAlert size={15} className="text-destructive shrink-0" />
                <span className="font-mono text-sm font-semibold text-foreground truncate">
                  {f.action}
                </span>
                <span className="font-mono text-xs font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5 shrink-0 whitespace-nowrap">
                  @{f.version}
                </span>
              </div>
              <SeverityBadge severity={f.severity} />
            </div>

            <p className="text-sm text-secondary-foreground mb-3 leading-relaxed">{f.summary}</p>

            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono text-xs font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5">{f.advisory_id}</span>
              {f.affected_range && (
                <span className="font-mono text-xs font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5">
                  Affected: {f.affected_range}
                </span>
              )}
              {f.fixed_version && (
                <span>
                  Fixed:{" "}
                  <span className="font-mono text-primary font-medium">{f.fixed_version}</span>
                </span>
              )}
              {f.aliases?.map((alias) => (
                <span
                  key={alias}
                  className="font-mono text-xs font-bold text-foreground bg-muted/50 rounded-md px-2 py-0.5"
                >
                  {alias}
                </span>
              ))}
              {f.reference_url && (
                <a
                  href={f.reference_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-primary hover:underline"
                >
                  <ExternalLink size={10} />
                  Reference
                </a>
              )}
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

function severityOrder(sev: string): number {
  const order: Record<string, number> = {
    critical: 0,
    high: 1,
    moderate: 2,
    medium: 2,
    low: 3,
    unknown: 4,
  };
  return order[sev.toLowerCase()] ?? 5;
}

/* ── SARIF Tab ───────────────────────────────────────────────── */

function SarifTab({
  findings,
  rulesMap,
  githubFileUrl,
}: {
  findings: SarifFinding[];
  rulesMap: Map<string, SarifRule>;
  githubFileUrl: string;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (findings.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/40 bg-gradient-to-b from-primary/[0.03] to-transparent p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-primary/8 flex items-center justify-center mx-auto mb-4 animate-breathe">
          <Shield size={28} className="text-primary" />
        </div>
        <p className="text-sm text-muted-foreground">
          No SARIF findings.
        </p>
      </div>
    );
  }

  // Count by level
  const levelCounts: Record<string, number> = {};
  for (const f of findings) {
    const rule = rulesMap.get(f.ruleId);
    const level = f.level ?? rule?.defaultConfiguration?.level ?? "warning";
    levelCounts[level] = (levelCounts[level] ?? 0) + 1;
  }

  return (
    <div className="space-y-4">
      {/* Severity summary bar */}
      <div className="flex flex-wrap gap-2">
        {["error", "warning", "note"].map(
          (level) =>
            levelCounts[level] && (
              <div
                key={level}
                className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-card px-3.5 py-2"
              >
                <SeverityBadge severity={level} />
                <span className="font-mono text-sm font-bold">
                  {levelCounts[level]}
                </span>
              </div>
            )
        )}
      </div>

      {/* Findings list */}
      <div className="space-y-3">
        {findings.map((f, i) => {
          const rule = rulesMap.get(f.ruleId);
          const level = f.level ?? rule?.defaultConfiguration?.level ?? "warning";
          const loc = f.locations?.[0];
          const phys = loc?.physicalLocation;
          const region = phys?.region;
          const snippet = region?.snippet?.text;
          const expanded = expandedIdx === i;

          const routeArr =
            loc?.logicalLocations?.[0]?.properties?.symbolic?.route?.route;
          const routeStr = routeArr?.map((r) => r.Key).join(" > ");

          const locMessage = loc?.message?.text;

          return (
            <div
              key={`${f.ruleId}-${i}`}
              className={cn(
                "rounded-xl border bg-card overflow-hidden transition-all duration-200 animate-fade-in-up",
                level === "error"
                  ? "border-destructive/35"
                  : level === "warning"
                  ? "border-yellow-500/25"
                  : "border-border/60"
              )}
              style={{ animationDelay: `${i * 30}ms` }}
            >
              {/* Card header */}
              <button
                onClick={() => setExpandedIdx(expanded ? null : i)}
                className="w-full text-left p-4 hover:bg-muted/15 transition-colors duration-150"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {expanded ? (
                      <ChevronDown size={13} className="text-muted-foreground shrink-0 mt-0.5" />
                    ) : (
                      <ChevronRight size={13} className="text-muted-foreground shrink-0 mt-0.5" />
                    )}
                    <AlertTriangle
                      size={15}
                      className={cn(
                        "shrink-0",
                        level === "error"
                          ? "text-destructive"
                          : level === "warning"
                          ? "text-yellow-600 dark:text-yellow-400"
                          : "text-blue-500"
                      )}
                    />
                    <span className="font-mono text-sm font-semibold text-foreground">
                      {f.ruleId}
                    </span>
                    {rule?.name && (
                      <span className="text-xs text-muted-foreground hidden sm:inline">
                        ({rule.name})
                      </span>
                    )}
                  </div>
                  <SeverityBadge severity={level} />
                </div>

                <p className="text-sm text-secondary-foreground mb-2 pl-8 leading-relaxed">
                  {f.message.text}
                </p>

                <div className="flex flex-wrap items-center gap-2 pl-8 text-xs text-muted-foreground">
                  {routeStr && (
                    <span className="font-mono bg-muted/40 rounded-md px-2 py-0.5 flex items-center gap-1">
                      <Code2 size={10} />
                      {routeStr}
                    </span>
                  )}
                  {region && (
                    <span className="font-mono">
                      L{region.startLine}
                      {region.endLine && region.endLine !== region.startLine
                        ? `\u2013${region.endLine}`
                        : ""}
                    </span>
                  )}
                  {snippet && (
                    <span className="text-primary text-[10px] font-medium">snippet available</span>
                  )}
                  {region && (
                    <a
                      href={`${githubFileUrl}#L${region.startLine}${region.endLine && region.endLine !== region.startLine ? `-L${region.endLine}` : ""}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 text-primary hover:underline ml-auto"
                    >
                      <ExternalLink size={10} />
                      View on GitHub
                    </a>
                  )}
                </div>
              </button>

              {/* Expanded detail */}
              {expanded && (
                <div className="border-t border-border/40 px-4 pb-4 pt-3 space-y-4 bg-muted/8">
                  {snippet && region && (
                    <SnippetBlock
                      snippet={snippet}
                      startLine={region.startLine}
                      endLine={region.endLine}
                      annotation={locMessage}
                      language={region.sourceLanguage}
                    />
                  )}

                  {f.relatedLocations && f.relatedLocations.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
                        <ArrowRight size={10} />
                        Related Locations
                      </span>
                      {f.relatedLocations.map((rl, ri) => {
                        const rlRegion = rl.physicalLocation?.region;
                        const rlSnippet = rlRegion?.snippet?.text;
                        return (
                          <div key={ri}>
                            {rlSnippet && rlRegion ? (
                              <SnippetBlock
                                snippet={rlSnippet}
                                startLine={rlRegion.startLine}
                                endLine={rlRegion.endLine}
                                annotation={rl.message?.text}
                                language={rlRegion.sourceLanguage}
                              />
                            ) : rl.message?.text ? (
                              <p className="text-xs text-muted-foreground font-mono bg-muted/25 rounded-lg px-3 py-2">
                                {rl.message.text}
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {(rule?.help || rule?.fullDescription) && (
                    <div className="rounded-xl border border-border/60 bg-card p-3.5 space-y-2">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
                        <Info size={10} />
                        Rule Details
                      </span>
                      {rule.help?.text && (
                        <p className="text-sm text-secondary-foreground leading-relaxed">
                          {rule.help.text}
                        </p>
                      )}
                      {rule.fullDescription && (
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {rule.fullDescription.text}
                        </p>
                      )}
                      {rule.helpUri && (
                        <a
                          href={rule.helpUri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium"
                        >
                          <ExternalLink size={10} />
                          Documentation
                        </a>
                      )}
                      {rule.properties?.tags && rule.properties.tags.length > 0 && (
                        <div className="flex gap-1.5 mt-1">
                          {rule.properties.tags.map((tag) => (
                            <span
                              key={tag}
                              className="text-[10px] font-mono bg-muted/40 rounded-md px-2 py-0.5 text-muted-foreground"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Code Snippet Block ──────────────────────────────────────── */

function SnippetBlock({
  snippet,
  startLine,
  endLine,
  annotation,
  language,
}: {
  snippet: string;
  startLine: number;
  endLine?: number;
  annotation?: string;
  language?: string;
}) {
  const lines = snippet.replace(/\n$/, "").split("\n");
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [snippet]);

  const lineRange = endLine && endLine !== startLine
    ? `L${startLine}–${endLine}`
    : `L${startLine}`;

  return (
    <div className="rounded-xl border border-border/60 overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/30 border-b border-border/40">
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
          {language && <span className="uppercase tracking-wider font-semibold">{language}</span>}
          <span>{lineRange}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors duration-150 px-1.5 py-0.5 rounded-md hover:bg-muted/50"
        >
          {copied ? <Check size={11} className="text-primary" /> : <Copy size={11} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {/* Code block */}
      <div className="overflow-x-auto bg-muted/20">
        <table className="w-full border-collapse code-table">
          <tbody>
            {lines.map((line, i) => {
              const lineNum = startLine + i;
              return (
                <tr key={i} className="hover:bg-muted/30 transition-colors duration-100">
                  <td className="text-right pr-3 pl-3 py-0 select-none text-xs font-mono text-muted-foreground/50 border-r border-border/40 w-[1%] whitespace-nowrap">
                    {lineNum}
                  </td>
                  <td className="pl-3 pr-4 py-0">
                    <pre className="font-mono text-sm text-foreground whitespace-pre">
                      {line}
                    </pre>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* Annotation */}
      {annotation && (
        <div className="border-t border-border/40 bg-yellow-500/5 px-3 py-2 flex items-start gap-2">
          <AlertTriangle size={12} className="text-yellow-600 dark:text-yellow-400 shrink-0 mt-0.5" />
          <span className="text-xs text-yellow-600 dark:text-yellow-400 italic leading-relaxed">
            {annotation}
          </span>
        </div>
      )}
    </div>
  );
}
