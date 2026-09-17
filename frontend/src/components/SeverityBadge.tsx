import { cn } from "@/lib/utils";

const severityStyles: Record<string, string> = {
  critical:
    "bg-destructive/15 text-destructive border-destructive/30 font-bold shadow-[0_0_8px_hsl(var(--destructive)/0.15)]",
  high:
    "bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30",
  moderate:
    "bg-yellow-500/12 text-yellow-600 dark:text-yellow-400 border-yellow-500/25",
  medium:
    "bg-yellow-500/12 text-yellow-600 dark:text-yellow-400 border-yellow-500/25",
  low:
    "bg-muted text-muted-foreground border-border",
  warning:
    "bg-yellow-500/12 text-yellow-600 dark:text-yellow-400 border-yellow-500/25",
  error:
    "bg-destructive/15 text-destructive border-destructive/30",
  note:
    "bg-blue-500/12 text-blue-600 dark:text-blue-400 border-blue-500/25",
};

export default function SeverityBadge({ severity }: { severity: string }) {
  const normalized = severity?.toLowerCase() ?? "unknown";
  const style = severityStyles[normalized] ?? "bg-muted text-muted-foreground border-border";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold font-mono uppercase tracking-wider",
        style
      )}
    >
      {severity}
    </span>
  );
}
