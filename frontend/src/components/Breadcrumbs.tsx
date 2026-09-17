import { Link, useLocation } from "react-router-dom";
import { ChevronRight } from "lucide-react";

export interface Crumb {
  label: string;
  to?: string;
}

export default function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  const location = useLocation();

  return (
    <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight size={13} className="text-muted-foreground/40" />}
            {isLast || !crumb.to ? (
              <span className="text-foreground font-semibold truncate max-w-[220px]">
                {crumb.label}
              </span>
            ) : (
              <Link
                to={crumb.to}
                className={`hover:text-primary transition-colors duration-150 truncate max-w-[220px] ${
                  location.pathname === crumb.to ? "text-primary" : ""
                }`}
              >
                {crumb.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
