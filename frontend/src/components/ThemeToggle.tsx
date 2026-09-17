import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    if (typeof window !== "undefined") {
      return document.documentElement.classList.contains("dark");
    }
    return true;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <button
      onClick={() => setDark((d) => !d)}
      className="relative p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition-all duration-200"
      aria-label="Toggle theme"
    >
      <div className="relative w-[18px] h-[18px]">
        <Sun
          size={18}
          className={`absolute inset-0 transition-all duration-300 ${
            dark ? "opacity-100 rotate-0 scale-100" : "opacity-0 rotate-90 scale-50"
          }`}
        />
        <Moon
          size={18}
          className={`absolute inset-0 transition-all duration-300 ${
            dark ? "opacity-0 -rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"
          }`}
        />
      </div>
    </button>
  );
}
