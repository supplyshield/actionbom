import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchRepositories, fetchFilters, importOrgRepos } from "@/lib/api";
import {
  GitBranch,
  Calendar,
  Package,
  FolderGit2,
  Globe,
  Lock,
  Search,
  ChevronLeft,
  ChevronRight,
  X,
  Rocket,
  Loader2,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import Breadcrumbs from "@/components/Breadcrumbs";
import PipelineLoader from "@/components/PipelineLoader";

const PAGE_SIZE = 24;

export default function RepositoriesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showLoader, setShowLoader] = useState(
    () => !sessionStorage.getItem("actionbom-loaded")
  );

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [pod, setPod] = useState("");
  const [subpod, setSubpod] = useState("");
  const [page, setPage] = useState(1);

  // Onboarding form state (shown when data.total === 0)
  const [importOrg, setImportOrg] = useState("");
  const [importing, setImporting] = useState(false);

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, pod, subpod]);

  const skip = (page - 1) * PAGE_SIZE;

  const { data, isLoading, error } = useQuery({
    queryKey: ["repositories", debouncedSearch, pod, subpod, page],
    queryFn: () =>
      fetchRepositories({
        skip,
        limit: PAGE_SIZE,
        search: debouncedSearch || undefined,
        pod: pod || undefined,
        subpod: subpod || undefined,
      }),
  });

  const { data: filters } = useQuery({
    queryKey: ["repo-filters"],
    queryFn: fetchFilters,
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  const clearFilters = useCallback(() => {
    setSearch("");
    setDebouncedSearch("");
    setPod("");
    setSubpod("");
    setPage(1);
  }, []);

  const hasFilters = debouncedSearch || pod || subpod;

  // Toast on error
  useEffect(() => {
    if (error) toast.error("Failed to load repositories", { description: (error as Error).message });
  }, [error]);

  const handleImport = useCallback(async () => {
    const trimmed = importOrg.trim();
    if (!trimmed || importing) return;
    setImporting(true);
    try {
      const result = await importOrgRepos(trimmed);
      toast.success(
        `Imported ${result.inserted} repos from ${result.org}`,
        {
          description:
            result.fetched > result.inserted
              ? `${result.fetched - result.inserted} already tracked, skipped.`
              : undefined,
        }
      );
      setImportOrg("");
      // Populate the table with the freshly-imported rows
      await queryClient.invalidateQueries({ queryKey: ["repositories"] });
      await queryClient.invalidateQueries({ queryKey: ["repo-filters"] });
    } catch (e) {
      toast.error("Import failed", { description: (e as Error).message });
    } finally {
      setImporting(false);
    }
  }, [importOrg, importing, queryClient]);

  // First-time visitors on an empty install shouldn't wait through the
  // pipeline animation to reach the welcome card. Skip it if nothing
  // is tracked yet.
  if (showLoader && !(data && data.total_tracked === 0)) {
    return (
      <PipelineLoader
        onComplete={() => {
          setShowLoader(false);
          sessionStorage.setItem("actionbom-loaded", "1");
        }}
      />
    );
  }
  if (showLoader && data && data.total_tracked === 0) {
    // Mark as "seen" so returning users don't see it later either
    sessionStorage.setItem("actionbom-loaded", "1");
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Breadcrumbs crumbs={[{ label: "Repositories" }]} />
          <p className="text-sm text-muted-foreground mt-1">
            Repositories with scanned workflows
          </p>
        </div>
        {data && (
          <span className="font-mono text-xs text-muted-foreground bg-muted/60 rounded-full px-3 py-1">
            {data.total} repositories
          </span>
        )}
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/60 bg-card/50 glass p-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/70"
          />
          <input
            type="text"
            placeholder="Search repositories..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 rounded-lg border border-input/60 bg-background/80 pl-9 pr-3 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-primary/40 font-mono transition-all duration-200"
          />
        </div>

        {/* Pod filter */}
        {filters && filters.pods.length > 0 && (
          <select
            value={pod}
            onChange={(e) => setPod(e.target.value)}
            className={`h-9 rounded-lg border bg-background/80 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-primary/40 font-mono transition-all duration-200 ${pod ? "ring-2 ring-primary/20 border-primary/40" : "border-input/60"}`}
          >
            <option value="">All pods</option>
            {filters.pods.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        )}

        {/* Subpod filter */}
        {filters && filters.subpods.length > 0 && (
          <select
            value={subpod}
            onChange={(e) => setSubpod(e.target.value)}
            className={`h-9 rounded-lg border bg-background/80 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-primary/40 font-mono transition-all duration-200 ${subpod ? "ring-2 ring-primary/20 border-primary/40" : "border-input/60"}`}
          >
            <option value="">All subpods</option>
            {filters.subpods.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        )}

        {/* Clear filters */}
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

      {/* Active filter pills */}
      {hasFilters && (
        <div className="flex flex-wrap gap-2 -mt-3">
          {debouncedSearch && (
            <span className="inline-flex items-center gap-1.5 bg-primary/10 text-primary border border-primary/20 rounded-full px-3 py-1 text-xs font-mono font-medium">
              search: {debouncedSearch}
              <button onClick={() => { setSearch(""); setDebouncedSearch(""); }} className="hover:text-primary/70"><X size={10} /></button>
            </span>
          )}
          {pod && (
            <span className="inline-flex items-center gap-1.5 bg-primary/10 text-primary border border-primary/20 rounded-full px-3 py-1 text-xs font-mono font-medium">
              pod: {pod}
              <button onClick={() => setPod("")} className="hover:text-primary/70"><X size={10} /></button>
            </span>
          )}
          {subpod && (
            <span className="inline-flex items-center gap-1.5 bg-primary/10 text-primary border border-primary/20 rounded-full px-3 py-1 text-xs font-mono font-medium">
              subpod: {subpod}
              <button onClick={() => setSubpod("")} className="hover:text-primary/70"><X size={10} /></button>
            </span>
          )}
        </div>
      )}

      {/* Loading — shimmer skeletons */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border/60 bg-card p-5"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="h-5 w-3/4 shimmer rounded-md mb-3" />
              <div className="h-4 w-1/2 shimmer rounded-md mb-2" />
              <div className="h-4 w-1/3 shimmer rounded-md" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive font-medium">
            Failed to load repositories. Make sure the backend is running on
            port 8000.
          </p>
          <p className="font-mono text-xs text-muted-foreground mt-2">
            {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty — welcome card when the whole DB is empty */}
      {data && data.total_tracked === 0 && (
        <div className="rounded-xl border border-border/60 bg-card/50 glass p-10 max-w-xl mx-auto">
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 mx-auto mb-5">
            <Rocket size={26} className="text-primary" />
          </div>
          <h2 className="text-lg font-semibold text-foreground text-center">
            Welcome to ActionBOM
          </h2>
          <p className="text-sm text-muted-foreground text-center mt-2 mb-6">
            Import a GitHub organization to start scanning its workflows for
            supply-chain vulnerabilities.
          </p>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="github-org (e.g. actions)"
              value={importOrg}
              onChange={(e) => setImportOrg(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleImport();
              }}
              disabled={importing}
              autoFocus
              className="flex-1 h-10 rounded-lg border border-input/60 bg-background/80 px-3 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-primary/40 font-mono transition-all duration-200 disabled:opacity-50"
            />
            <button
              onClick={handleImport}
              disabled={!importOrg.trim() || importing}
              className="h-10 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 min-w-[110px] justify-center"
            >
              {importing ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Importing…
                </>
              ) : (
                "Import"
              )}
            </button>
          </div>

          <p className="text-xs text-muted-foreground/70 mt-4 text-center">
            Requires <code className="font-mono">GITHUB_TOKEN</code> set in{" "}
            <code className="font-mono">.env</code> for private repos and higher
            API rate limits.
          </p>
          <p className="text-xs text-muted-foreground/60 mt-2 text-center">
            Or set <code className="font-mono">TARGET_ORG</code> in{" "}
            <code className="font-mono">.env</code> and restart to auto-import
            on boot.
          </p>
        </div>
      )}

      {/* Import happened, cron hasn't produced any workflow rows yet */}
      {data && data.total_tracked > 0 && data.total === 0 && (
        <div className="rounded-xl border border-dashed border-border/40 bg-gradient-to-b from-primary/[0.03] to-transparent p-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto mb-4 animate-breathe">
            <Loader2 size={28} className="text-muted-foreground animate-spin" />
          </div>
          <p className="text-sm text-muted-foreground">
            {data.total_tracked} repositories imported. Waiting for the scanner to run.
          </p>
          <p className="text-xs text-muted-foreground/60 mt-2">
            Repositories appear here once at least one workflow has been scanned.
          </p>
        </div>
      )}

      {/* Empty — filter results only */}
      {data && data.total > 0 && data.repositories.length === 0 && (
        <div className="rounded-xl border border-dashed border-border/40 bg-gradient-to-b from-primary/[0.03] to-transparent p-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto mb-4 animate-breathe">
            <FolderGit2 size={28} className="text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground">
            No repositories match your filters.
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

      {/* Repo grid */}
      {data && data.repositories.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.repositories.map((repo, i) => (
            <button
              key={repo.id}
              onClick={() => navigate(`/repo/${repo.id}`)}
              className="text-left rounded-xl border border-border/60 bg-card p-5 hover:border-primary/50 hover:glow-primary card-lift card-glow-border cursor-pointer group animate-fade-in-up"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/15 transition-colors">
                    <FolderGit2 size={15} className="text-primary" />
                  </div>
                  <span className="font-mono text-sm font-semibold text-foreground truncate">
                    {repo.org}/{repo.name}
                  </span>
                </div>
                {repo.is_public ? (
                  <Globe
                    size={13}
                    className="text-muted-foreground/60 shrink-0 mt-1"
                  />
                ) : (
                  <Lock
                    size={13}
                    className="text-muted-foreground/60 shrink-0 mt-1"
                  />
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <GitBranch
                      size={12}
                      className="text-muted-foreground/70"
                    />
                    <span className="text-xs text-muted-foreground">
                      {repo.workflow_count} workflow{repo.workflow_count !== 1 ? "s" : ""}
                    </span>
                  </div>
                  {repo.pod && (
                    <span className="inline-flex items-center rounded-md bg-primary/8 text-primary px-2 py-0.5 text-[10px] font-mono font-medium tracking-wide">
                      {repo.pod}
                    </span>
                  )}
                </div>

                {repo.last_scan && (
                  <div className="flex items-center gap-1.5">
                    <Calendar
                      size={12}
                      className="text-muted-foreground/70"
                    />
                    <span className="text-xs text-muted-foreground">
                      Scanned{" "}
                      {formatDistanceToNow(new Date(repo.last_scan), {
                        addSuffix: true,
                      })}
                    </span>
                  </div>
                )}

                {!repo.last_scan && (
                  <div className="flex items-center gap-1.5">
                    <Package
                      size={12}
                      className="text-muted-foreground/70"
                    />
                    <span className="text-xs text-muted-foreground/70">
                      Not yet scanned
                    </span>
                  </div>
                )}
              </div>
            </button>
          ))}
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

          {paginationRange(page, totalPages).map((p, i) =>
            p === "..." ? (
              <span
                key={`dot-${i}`}
                className="px-2 text-xs text-muted-foreground/50 select-none"
              >
                ...
              </span>
            ) : (
              <button
                key={p}
                onClick={() => setPage(p as number)}
                className={`min-w-[34px] h-8 rounded-lg text-sm font-mono font-medium transition-all duration-150 ${
                  page === p
                    ? "bg-primary text-primary-foreground shadow-[0_0_12px_hsl(var(--primary)/0.25)]"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/80"
                }`}
              >
                {p}
              </button>
            )
          )}

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

/**
 * Generate a pagination range like: [1, 2, 3, "...", 10]
 */
function paginationRange(
  current: number,
  total: number
): (number | "...")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "...")[] = [];

  // Always show first page
  pages.push(1);

  if (current > 3) {
    pages.push("...");
  }

  // Pages around current
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) {
    pages.push("...");
  }

  // Always show last page
  if (total > 1) {
    pages.push(total);
  }

  return pages;
}
