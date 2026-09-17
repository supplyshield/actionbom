import type { SbomComponent, VulnFinding } from "@/types/api";
import { X, Package, ShieldAlert, ExternalLink } from "lucide-react";
import SeverityBadge from "./SeverityBadge";
import { formatComponentVersion } from "@/lib/utils";

interface Props {
  component: SbomComponent;
  vulnFindings?: VulnFinding[];
  onClose: () => void;
}

export default function SbomDetailPanel({ component, vulnFindings = [], onClose }: Props) {
  const hasVulns = vulnFindings.length > 0;

  return (
    <div className="w-[340px] shrink-0 border-l border-border/60 glass flex flex-col overflow-hidden animate-in slide-in-from-right-4 duration-200">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
        <h2 className="font-mono text-sm font-semibold text-foreground truncate">
          {component.name}
        </h2>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg hover:bg-secondary/80"
        >
          <X size={15} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <InfoBlock label="Version" value={formatComponentVersion(component.version, component.properties) ?? "\u2014"} />
          <InfoBlock label="Type" value={component.type} />
        </div>

        {component.purl && (
          <div>
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              Package URL
            </span>
            <p className="font-mono text-xs text-primary mt-1.5 break-all leading-relaxed">
              {component.purl}
            </p>
          </div>
        )}

        {component.properties && component.properties.length > 0 && (
          <div>
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              Properties
            </span>
            <div className="mt-2 space-y-1.5">
              {component.properties.map((p, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 text-sm text-secondary-foreground font-mono bg-muted/30 rounded-lg px-3 py-1.5"
                >
                  <Package size={11} className="text-muted-foreground/60 shrink-0" />
                  <span className="text-muted-foreground/70">{p.name}:</span>
                  <span className="truncate">{p.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Vulnerability section */}
        {hasVulns && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <ShieldAlert size={13} className="text-destructive" />
              <span className="text-[10px] font-semibold text-destructive uppercase tracking-widest">
                Vulnerabilities ({vulnFindings.length})
              </span>
            </div>
            <div className="space-y-3">
              {vulnFindings.map((f, i) => (
                <div
                  key={`${f.advisory_id}-${i}`}
                  className="rounded-lg border border-destructive/25 bg-destructive/[0.04] p-3 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-foreground">
                      {f.advisory_id}
                    </span>
                    <SeverityBadge severity={f.severity} />
                  </div>

                  <p className="text-xs text-secondary-foreground leading-relaxed">
                    {f.summary}
                  </p>

                  <div className="space-y-1 text-xs text-muted-foreground">
                    {f.affected_range && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-muted-foreground/70">Affected:</span>
                        <span className="font-mono">{f.affected_range}</span>
                      </div>
                    )}
                    {f.fixed_version && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-muted-foreground/70">Fixed:</span>
                        <span className="font-mono text-primary font-medium">{f.fixed_version}</span>
                      </div>
                    )}
                  </div>

                  {f.aliases && f.aliases.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {f.aliases.map((alias) => (
                        <span
                          key={alias}
                          className="font-mono text-[10px] bg-muted/40 rounded-md px-1.5 py-0.5 text-muted-foreground"
                        >
                          {alias}
                        </span>
                      ))}
                    </div>
                  )}

                  {f.reference_url && (
                    <a
                      href={f.reference_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline font-medium"
                    >
                      <ExternalLink size={10} />
                      View Advisory
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted/30 rounded-xl px-3 py-2.5">
      <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-medium">
        {label}
      </span>
      <p className="font-mono text-sm text-foreground mt-0.5 capitalize">
        {value}
      </p>
    </div>
  );
}
