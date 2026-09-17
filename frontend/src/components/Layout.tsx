import { Outlet, Link, useLocation } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";
import { cn } from "@/lib/utils";

function PipelineLogo() {
  return (
    <svg
      width="30"
      height="30"
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="transition-all duration-300"
    >
      {/* Pipeline nodes */}
      <circle cx="6" cy="8" r="3" className="stroke-primary fill-primary/15" strokeWidth="1.5" />
      <circle cx="22" cy="8" r="3" className="stroke-primary fill-primary/15" strokeWidth="1.5" />
      <circle cx="22" cy="22" r="3" className="stroke-primary fill-primary/15" strokeWidth="1.5" />

      {/* Pipes */}
      <line x1="9" y1="8" x2="19" y2="8" className="stroke-primary" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="22" y1="11" x2="22" y2="19" className="stroke-primary" strokeWidth="1.5" strokeLinecap="round" />

      {/* Pulse dot */}
      <circle r="1.5" className="fill-primary">
        <animateMotion dur="2s" repeatCount="indefinite" path="M 6,8 L 22,8 L 22,22" />
      </circle>
    </svg>
  );
}

function NavLink({ to, label }: { to: string; label: string }) {
  const location = useLocation();
  const isActive =
    to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

  return (
    <Link
      to={to}
      className={cn(
        "px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
        isActive
          ? "text-primary bg-primary/10"
          : "text-muted-foreground hover:text-foreground hover:bg-secondary/80"
      )}
    >
      {label}
    </Link>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen bg-background bg-dotgrid">
      <header className="sticky top-0 z-50 border-b border-border/60 glass header-glow">
        <div className="container flex items-center justify-between h-14 px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="group-hover:glow-primary rounded-full transition-all duration-300">
                <PipelineLogo />
              </div>
              <h1 className="text-lg font-bold text-foreground tracking-tight">
                Action<span className="text-primary">BOM</span>
              </h1>
            </Link>
            <nav className="flex items-center gap-1">
              <NavLink to="/" label="Repositories" />
              <NavLink to="/actions" label="Actions" />
            </nav>
          </div>
          <ThemeToggle />
        </div>
      </header>
      <main className="container px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
