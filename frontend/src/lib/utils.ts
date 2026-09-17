import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type ComponentProperty = { name: string; value: string };

/**
 * Render the version label for an SBOM component.
 *
 * If the source workflow uses a floating ref (e.g. `@v3`) and the SBOM
 * resolved it to a concrete release version (e.g. `3.28.5`), show both:
 *   "v3 → 3.28.5"
 *
 * If the ref is already a full semver, or no resolution happened, just
 * show the version. Returns null if no version info is available.
 */
export function formatComponentVersion(
  version: string | null | undefined,
  properties: ComponentProperty[] | null | undefined,
): string | null {
  if (!version) return null;
  const sourceRef = properties?.find((p) => p.name === "github:action:ref")?.value;
  if (!sourceRef) return version;
  // Normalize for comparison: strip leading 'v', case-insensitive, trim.
  const norm = (s: string) => s.replace(/^v/i, "").trim().toLowerCase();
  if (norm(sourceRef) === norm(version)) return version;
  return `${sourceRef} → ${version}`;
}
