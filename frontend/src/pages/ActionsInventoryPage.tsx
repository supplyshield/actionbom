import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchActionsInventory } from "@/lib/api";
import {
  Search,
  Package,
  ShieldAlert,
  FolderGit2,
  FileCode2,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import { toast } from "sonner";
import Breadcrumbs from "@/components/Breadcrumbs";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

export default function ActionsInventoryPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [vulnerableOnly, setVulnerableOnly] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, vulnerableOnly]);

  const skip = (page - 1) * PAGE_SIZE;

  const { data, isLoading, error } = useQuery({
    queryKey: ["actions-inventory", debouncedSearch, vulnerableOnly, page],
    queryFn: () =>
      fetchActionsInventory({
        search: debouncedSearch || undefined,
        vulnerable_only: vulnerableOnly || undefined,
        skip,
        limit: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  const clearFilters = useCallback(() => {
    setSearch("");
    setDebouncedSearch("");
    setVulnerableOnly(false);
    setPage(1);
  }, []);

  const hasFilters = debouncedSearch || vulnerableOnly;

  useEffect(() => {
    if (error)
      toast.error("Failed to load actions", {
        description: (error as Error).message,
      });
  }, [error]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Breadcrumbs crumbs={[{ label: "Actions Inventory" }]} />
          <p className="text-sm text-muted-foreground mt-1">
            GitHub Actions used across the organization
          </p>
        </div>
        {data && (
          <span className="font-mono text-xs text-muted-foreground bg-muted/60 rounded-full px-3 py-1">
            {data.total} actions
          </span>
        )}
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/60 bg-card/50 glass p-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/70"
          />
          <input
            type="text"
            placeholder="Search actions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 rounded-lg border border-input/60 bg-background/80 pl-9 pr-3 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-primary/40 font-mono transition-all duration-200"
          />
        </div>

        <button
          onClick={() => setVulnerableOnly(!vulnerableOnly)}
          className={cn(
            "h-9 rounded-lg border px-3 text-xs font-medium flex items-center gap-1.5 transition-all duration-200",
            vulnerableOnly
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : "border-input/60 bg-background/80 text-muted-foreground hover:text-foreground hover:border-primary/40"
          )}
        >
          <ShieldAlert size={12} />
          Vulnerable only
        </button>

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="h-9 rounded-lg border border-border/60 px-3 text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-all duration-200 flex items-center gap-1.5"
          >
            <X size={12} />
            Clear
          </button>
        )}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border/60 bg-card p-4"
            >
              <div className="h-5 w-1/3 shimmer rounded-md mb-2" />
              <div className="h-4 w-1/4 shimmer rounded-md" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive font-medium">
            Failed to load actions.
          </p>
          <p className="font-mono text-xs text-muted-foreground mt-2">
            {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty */}
      {data && data.actions.length === 0 && (
        <div className="rounded-xl border border-dashed border-border/40 bg-gradient-to-b from-primary/[0.03] to-transparent p-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto mb-4 animate-breathe">
            <Package size={28} className="text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground">
            {hasFilters
              ? "No actions match your filters."
              : "No actions found. Run a scan to populate results."}
          </p>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="mt-4 text-xs text-primary hover:underline font-medium"
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Actions list */}
      {data && data.actions.length > 0 && (
        <div className="space-y-2">
          {/* Table header */}
          <div className="grid grid-cols-12 gap-4 px-5 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
            <div className="col-span-5">Action</div>
            <div className="col-span-2 text-center">Versions</div>
            <div className="col-span-2 text-center">Workflows</div>
            <div className="col-span-1 text-center">Repos</div>
            <div className="col-span-2 text-center">Vulnerabilities</div>
          </div>

          {data.actions.map((action, i) => {
            const isVuln = action.vulnerable_count > 0;
            return (
              <button
                key={action.action_name}
                onClick={() =>
                  navigate(`/actions/${encodeURIComponent(action.action_name)}`)
                }
                className={cn(
                  "w-full text-left grid grid-cols-12 gap-4 items-center rounded-xl border bg-card px-5 py-4 card-lift card-glow-border cursor-pointer group animate-fade-in-up",
                  isVuln
                    ? "border-destructive/30 hover:glow-destructive"
                    : "border-border/60 hover:border-primary/50 hover:glow-primary"
                )}
                style={{ animationDelay: `${i * 20}ms` }}
              >
                {/* Action name */}
                <div className="col-span-5 flex items-center gap-3 min-w-0">
                  <div
                    className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors",
                      isVuln
                        ? "bg-destructive/10 group-hover:bg-destructive/15"
                        : "bg-primary/10 group-hover:bg-primary/15"
                    )}
                  >
                    {isVuln ? (
                      <ShieldAlert size={14} className="text-destructive" />
                    ) : (
                      <Package size={14} className="text-primary" />
                    )}
                  </div>
                  <span className="font-mono text-sm font-semibold text-foreground truncate">
                    {action.action_name}
                  </span>
                </div>

                {/* Versions */}
                <div className="col-span-2 text-center">
                  <span className="font-mono text-sm text-muted-foreground">
                    {action.version_count}
                  </span>
                </div>

                {/* Workflows */}
                <div className="col-span-2 text-center flex items-center justify-center gap-1.5">
                  <FileCode2
                    size={12}
                    className="text-muted-foreground/60"
                  />
                  <span className="font-mono text-sm text-muted-foreground">
                    {action.workflow_count}
                  </span>
                </div>

                {/* Repos */}
                <div className="col-span-1 text-center flex items-center justify-center gap-1.5">
                  <FolderGit2
                    size={12}
                    className="text-muted-foreground/60"
                  />
                  <span className="font-mono text-sm text-muted-foreground">
                    {action.repo_count}
                  </span>
                </div>

                {/* Vulns */}
                <div className="col-span-2 text-center">
                  {isVuln ? (
                    <span className="inline-flex items-center gap-1.5 text-destructive font-mono text-sm font-semibold">
                      <ShieldAlert size={12} />
                      {action.vulnerable_count}
                    </span>
                  ) : (
                    <span className="font-mono text-sm text-muted-foreground/50">
                      —
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary/80 disabled:opacity-25 disabled:cursor-not-allowed transition-all duration-150"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="font-mono text-xs text-muted-foreground px-3">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary/80 disabled:opacity-25 disabled:cursor-not-allowed transition-all duration-150"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
