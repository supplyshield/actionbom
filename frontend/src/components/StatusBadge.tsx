import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  completed:
    "bg-primary/10 text-primary border-primary/20",
  failed:
    "bg-destructive/10 text-destructive border-destructive/20",
  running:
    "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20",
  pending:
    "bg-muted text-muted-foreground border-border",
};

export default function StatusBadge({ status }: { status: string }) {
  const normalized = status?.toLowerCase() ?? "unknown";
  const style = statusStyles[normalized] ?? statusStyles.pending;
  const isRunning = normalized === "running";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold font-mono tracking-wide",
        style
      )}
    >
      {isRunning && (
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 status-dot-pulse" />
      )}
      {normalized === "completed" && (
        <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      )}
      {normalized === "failed" && (
        <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      )}
      {status}
    </span>
  );
}
