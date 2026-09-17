import type { SbomComponent, SbomDependency } from "@/types/api";

export const NODE_WIDTH = 320;
export const NODE_HEIGHT = 80;
const GAP_X = 100;
const GAP_Y = 40;

export interface GraphNodePosition {
  id: string;
  x: number;
  y: number;
  depth: number;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface SbomGraphData {
  nodes: GraphNodePosition[];
  edges: GraphEdge[];
  width: number;
  height: number;
}

/**
 * Build a horizontal BFS-based graph layout from CycloneDX components + dependencies.
 *
 * Nodes flow left → right (depth columns). Each column is vertically centered.
 */
export function computeSbomLayout(
  components: SbomComponent[],
  dependencies: SbomDependency[]
): SbomGraphData {
  // Build lookup: bom-ref → component
  const compMap = new Map<string, SbomComponent>();
  for (const c of components) {
    const ref = c["bom-ref"] ?? c.purl ?? c.name;
    compMap.set(ref, c);
  }

  // Build adjacency list from dependencies array
  const adj = new Map<string, string[]>();
  const allRefs = new Set<string>();

  for (const dep of dependencies) {
    allRefs.add(dep.ref);
    const children = dep.dependsOn ?? [];
    adj.set(dep.ref, children);
    for (const child of children) {
      allRefs.add(child);
    }
  }

  // Also include any components not referenced in dependencies
  for (const c of components) {
    const ref = c["bom-ref"] ?? c.purl ?? c.name;
    allRefs.add(ref);
  }

  // Determine root nodes: nodes that are never a dependency target
  const targeted = new Set<string>();
  for (const [, children] of adj) {
    for (const child of children) {
      targeted.add(child);
    }
  }
  const roots = [...allRefs].filter((r) => !targeted.has(r));
  // If no clear root, pick the first dependency entry or first component
  if (roots.length === 0 && dependencies.length > 0) {
    roots.push(dependencies[0].ref);
  } else if (roots.length === 0 && components.length > 0) {
    roots.push(components[0]["bom-ref"] ?? components[0].purl ?? components[0].name);
  }

  // BFS to assign depth
  const depthMap = new Map<string, number>();
  const queue: { id: string; depth: number }[] = [];
  for (const r of roots) {
    if (!depthMap.has(r)) {
      depthMap.set(r, 0);
      queue.push({ id: r, depth: 0 });
    }
  }

  const edges: GraphEdge[] = [];

  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    const children = adj.get(id) ?? [];
    for (const child of children) {
      edges.push({ from: id, to: child });
      if (!depthMap.has(child)) {
        depthMap.set(child, depth + 1);
        queue.push({ id: child, depth: depth + 1 });
      }
    }
  }

  // Include any orphan nodes (not reached by BFS) at depth 0
  for (const ref of allRefs) {
    if (!depthMap.has(ref)) {
      depthMap.set(ref, 0);
    }
  }

  // Group by depth
  const depthGroups = new Map<number, string[]>();
  for (const [id, d] of depthMap) {
    if (!depthGroups.has(d)) depthGroups.set(d, []);
    depthGroups.get(d)!.push(id);
  }

  const maxDepth = depthGroups.size > 0 ? Math.max(...depthGroups.keys()) : 0;
  let maxRows = 0;
  for (const group of depthGroups.values()) {
    maxRows = Math.max(maxRows, group.length);
  }

  const nodes: GraphNodePosition[] = [];
  for (const [depth, ids] of depthGroups) {
    const totalHeight = ids.length * NODE_HEIGHT + (ids.length - 1) * GAP_Y;
    const canvasCenter = (maxRows * (NODE_HEIGHT + GAP_Y) - GAP_Y) / 2;
    const startY = canvasCenter - totalHeight / 2;
    ids.forEach((id, i) => {
      nodes.push({
        id,
        x: depth * (NODE_WIDTH + GAP_X) + 60,
        y: startY + i * (NODE_HEIGHT + GAP_Y) + 60,
        depth,
      });
    });
  }

  const width = Math.max((maxDepth + 1) * (NODE_WIDTH + GAP_X) + 120, 800);
  const height = Math.max(maxRows * (NODE_HEIGHT + GAP_Y) + 120, 400);

  return { nodes, edges, width, height };
}
