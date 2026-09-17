import type { SbomComponent } from "@/types/api";
import { NODE_WIDTH, NODE_HEIGHT } from "@/lib/sbomLayout";
import { Package, Box, Layers, Container, ShieldAlert } from "lucide-react";
import { formatComponentVersion } from "@/lib/utils";

const typeIcons: Record<string, React.ReactNode> = {
  application: <Box size={13} />,
  library: <Package size={13} />,
  framework: <Layers size={13} />,
  container: <Container size={13} />,
};

function formatName(name: string): { short: string; context: string | null } {
  const wfIdx = name.indexOf(".github/workflows/");
  if (wfIdx > 0) {
    const context = name.slice(0, wfIdx).replace(/\/$/, "");
    const file = name.slice(wfIdx + ".github/workflows/".length);
    return { short: file || name, context };
  }
  const parts = name.split("/");
  if (parts.length > 2) {
    return { short: parts.slice(0, 2).join("/"), context: parts.slice(2).join("/") };
  }
  return { short: name, context: null };
}

interface Props {
  component: SbomComponent;
  x: number;
  y: number;
  selected: boolean;
  onSelect: (id: string) => void;
  vulnerable?: boolean;
}

export default function SbomGraphNode({
  component,
  x,
  y,
  selected,
  onSelect,
  vulnerable = false,
}: Props) {
  const ref = component["bom-ref"] ?? component.purl ?? component.name;
  const { short, context } = formatName(component.name);

  return (
    <foreignObject x={x} y={y} width={NODE_WIDTH} height={NODE_HEIGHT}>
      <div
        onClick={(e) => {
          e.stopPropagation();
          onSelect(ref);
        }}
        className={`
          h-full rounded-xl border cursor-pointer transition-all duration-200
          flex flex-col justify-center px-4 py-2 gap-0.5
          ${vulnerable
            ? `bg-destructive/8 border-destructive/40 hover:border-destructive/70 ${selected ? "border-destructive glow-destructive-strong" : ""}`
            : `bg-card hover:border-primary/50 hover:glow-primary ${selected ? "border-primary glow-primary-strong" : "border-border/60"}`
          }
        `}
        style={vulnerable ? { boxShadow: "0 0 12px hsl(0 72% 50% / 0.15)" } : undefined}
      >
        {context && (
          <span className="font-mono text-[10px] text-muted-foreground/60 truncate leading-tight">
            {context}
          </span>
        )}
        <div className="flex items-center gap-2">
          <span className={`shrink-0 opacity-80 ${vulnerable ? "text-destructive" : "text-primary"}`}>
            {vulnerable ? <ShieldAlert size={13} /> : (typeIcons[component.type] || <Package size={13} />)}
          </span>
          <span className="font-mono text-[13px] font-semibold text-foreground truncate">
            {short}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {component.version && (
            <span className="font-mono text-[10px] font-bold text-foreground bg-muted/50 rounded px-1.5 py-0.5 truncate">
              {formatComponentVersion(component.version, component.properties)}
            </span>
          )}
          {vulnerable ? (
            <span className="text-[10px] text-destructive/80 font-medium ml-auto">vulnerable</span>
          ) : (
            <span className="text-[10px] text-muted-foreground/50 capitalize ml-auto">
              {component.type}
            </span>
          )}
        </div>
      </div>
    </foreignObject>
  );
}
