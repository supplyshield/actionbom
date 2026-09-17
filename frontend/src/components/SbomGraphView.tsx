import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import type { SbomComponent, SbomDependency, VulnFinding } from "@/types/api";
import {
  computeSbomLayout,
  NODE_WIDTH,
  NODE_HEIGHT,
} from "@/lib/sbomLayout";
import SbomGraphNode from "./SbomGraphNode";
import SbomDetailPanel from "./SbomDetailPanel";
import { ZoomIn, ZoomOut, Maximize2, Minimize2, ScanSearch, Package } from "lucide-react";

interface Props {
  components: SbomComponent[];
  dependencies: SbomDependency[];
  vulnFindings?: VulnFinding[];
}

export default function SbomGraphView({ components, dependencies, vulnFindings = [] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  const { nodes, edges, width, height } = useMemo(
    () => computeSbomLayout(components, dependencies),
    [components, dependencies]
  );

  const compMap = useMemo(() => {
    const m = new Map<string, SbomComponent>();
    for (const c of components) {
      const ref = c["bom-ref"] ?? c.purl ?? c.name;
      m.set(ref, c);
    }
    return m;
  }, [components]);

  const posMap = useMemo(
    () => new Map(nodes.map((n) => [n.id, n])),
    [nodes]
  );

  // Build lookup: component name -> list of VulnFindings affecting it
  const vulnMap = useMemo(() => {
    const m = new Map<string, VulnFinding[]>();
    for (const f of vulnFindings) {
      const existing = m.get(f.action) ?? [];
      existing.push(f);
      m.set(f.action, existing);
    }
    return m;
  }, [vulnFindings]);

  const selectedComp = selected ? compMap.get(selected) : null;

  const fitView = useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const scaleX = rect.width / width;
    const scaleY = rect.height / height;
    const s = Math.min(scaleX, scaleY, 2);
    setZoom(s);
    setPan({
      x: (rect.width - width * s) / 2,
      y: (rect.height - height * s) / 2,
    });
  }, [width, height]);

  useEffect(() => {
    requestAnimationFrame(() => fitView());
  }, [fullscreen, fitView]);

  useEffect(() => {
    if (!fullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const zoomTo = useCallback(
    (factor: number) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      setZoom((prevZoom) => {
        const newZoom = Math.min(3, Math.max(0.15, prevZoom * factor));
        const ratio = newZoom / prevZoom;
        setPan((prevPan) => ({
          x: cx - (cx - prevPan.x) * ratio,
          y: cy - (cy - prevPan.y) * ratio,
        }));
        return newZoom;
      });
    },
    []
  );

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom((prevZoom) => {
        const newZoom = Math.min(3, Math.max(0.15, prevZoom * factor));
        const ratio = newZoom / prevZoom;
        setPan((prevPan) => ({
          x: mx - (mx - prevPan.x) * ratio,
          y: my - (my - prevPan.y) * ratio,
        }));
        return newZoom;
      });
    },
    []
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      setDragging(true);
      dragStart.current = {
        x: e.clientX,
        y: e.clientY,
        panX: pan.x,
        panY: pan.y,
      };
    },
    [pan]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragging) return;
      setPan({
        x: dragStart.current.panX + (e.clientX - dragStart.current.x),
        y: dragStart.current.panY + (e.clientY - dragStart.current.y),
      });
    },
    [dragging]
  );

  const handleMouseUp = useCallback(() => setDragging(false), []);

  if (components.length === 0) {
    return (
      <div className="rounded-xl border border-border/60 bg-card p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto mb-4">
          <Package size={28} className="text-muted-foreground" />
        </div>
        <p className="text-sm text-muted-foreground">No SBOM components.</p>
      </div>
    );
  }

  return (
    <div
      className={
        fullscreen
          ? "fixed inset-0 z-50 flex bg-background"
          : "flex rounded-xl border border-border/60 overflow-hidden bg-background"
      }
      style={fullscreen ? undefined : { height: "520px" }}
    >
      {/* Graph canvas */}
      <div className="flex-1 relative" ref={containerRef}>
        {/* Toolbar */}
        <div className="absolute top-3 right-3 z-10 flex items-center gap-0.5 glass border border-border/60 rounded-lg px-1 py-1">
          <ToolbarBtn onClick={() => zoomTo(1.2)} title="Zoom in">
            <ZoomIn size={14} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => zoomTo(0.8)} title="Zoom out">
            <ZoomOut size={14} />
          </ToolbarBtn>
          <ToolbarBtn onClick={fitView} title="Fit view">
            <ScanSearch size={14} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => setFullscreen((f) => !f)} title={fullscreen ? "Exit fullscreen" : "Fullscreen"}>
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </ToolbarBtn>
        </div>

        {/* Stats */}
        <div className="absolute top-3 left-3 z-10 font-mono text-[11px] text-muted-foreground glass border border-border/60 rounded-lg px-3 py-1.5">
          {components.length} components · {edges.length} deps · {Math.round(zoom * 100)}%
        </div>

        {/* SVG */}
        <svg
          className={`w-full h-full ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <defs>
            <pattern
              id="sbom-grid"
              width="40"
              height="40"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="hsl(var(--grid-color, 224 14% 10%))"
                strokeWidth="0.5"
              />
            </pattern>
            <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <rect width="100%" height="100%" fill="url(#sbom-grid)" />

          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            {/* Edges */}
            {edges.map((edge) => {
              const from = posMap.get(edge.from);
              const to = posMap.get(edge.to);
              if (!from || !to) return null;

              const x1 = from.x + NODE_WIDTH;
              const y1 = from.y + NODE_HEIGHT / 2;
              const x2 = to.x;
              const y2 = to.y + NODE_HEIGHT / 2;
              const midX = (x1 + x2) / 2;
              const d = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;

              const isHighlighted =
                selected === edge.from || selected === edge.to;
              const fromComp = compMap.get(edge.from);
              const toComp = compMap.get(edge.to);
              const isVulnEdge =
                (fromComp && vulnMap.has(fromComp.name)) ||
                (toComp && vulnMap.has(toComp.name));

              return (
                <g key={`${edge.from}-${edge.to}`}>
                  <path
                    d={d}
                    fill="none"
                    stroke={
                      isHighlighted
                        ? isVulnEdge ? "hsl(0 72% 50%)" : "hsl(177 72% 48%)"
                        : isVulnEdge ? "hsl(0 72% 40%)" : "hsl(var(--border))"
                    }
                    strokeWidth={isHighlighted ? 2 : 1}
                    opacity={isHighlighted ? 1 : isVulnEdge ? 0.5 : 0.35}
                    className="transition-all duration-200"
                  />
                  <path
                    d={d}
                    fill="none"
                    stroke={
                      isHighlighted
                        ? isVulnEdge ? "hsl(0 72% 60%)" : "hsl(177 72% 62%)"
                        : isVulnEdge ? "hsl(0 72% 50%)" : "hsl(177 72% 48%)"
                    }
                    strokeWidth={isHighlighted ? 3 : 2}
                    strokeDasharray="4 20"
                    strokeLinecap="round"
                    opacity={isHighlighted ? 0.9 : isVulnEdge ? 0.4 : 0.3}
                    filter="url(#neon-glow)"
                    className="neon-edge"
                  />
                </g>
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => {
              const comp = compMap.get(node.id);
              if (!comp) return null;
              return (
                <SbomGraphNode
                  key={node.id}
                  component={comp}
                  x={node.x}
                  y={node.y}
                  selected={selected === node.id}
                  onSelect={setSelected}
                  vulnerable={vulnMap.has(comp.name)}
                />
              );
            })}
          </g>
        </svg>
      </div>

      {/* Detail panel */}
      {selectedComp && (
        <SbomDetailPanel
          component={selectedComp}
          vulnFindings={vulnMap.get(selectedComp.name) ?? []}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function ToolbarBtn({
  children,
  onClick,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition-all duration-150"
    >
      {children}
    </button>
  );
}
