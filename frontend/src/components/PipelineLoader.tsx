import { useEffect, useState } from "react";
import { GitCommit, Hammer, ScanSearch, ShieldCheck } from "lucide-react";

const stages = [
  { icon: GitCommit, label: "Commit" },
  { icon: Hammer, label: "Build" },
  { icon: ScanSearch, label: "Scan" },
  { icon: ShieldCheck, label: "Secure" },
];

interface Props {
  onComplete: () => void;
}

export default function PipelineLoader({ onComplete }: Props) {
  const [fadingOut, setFadingOut] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setFadingOut(true), 2200);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      className="flex flex-col items-center justify-center py-32 transition-opacity duration-500"
      style={{ opacity: fadingOut ? 0 : 1 }}
      onTransitionEnd={() => {
        if (fadingOut) onComplete();
      }}
    >
      {/* Title */}
      <div
        className="mb-14 text-center"
        style={{ animation: "pipeline-subtitle-in 0.4s ease-out forwards" }}
      >
        <h2 className="text-3xl font-bold text-foreground tracking-tight">
          Action<span className="text-primary">BOM</span>
        </h2>
        <p
          className="text-sm text-muted-foreground mt-2 tracking-wide"
          style={{
            opacity: 0,
            animation: "pipeline-subtitle-in 0.4s ease-out 0.3s forwards",
          }}
        >
          Scanning your CI/CD pipeline
        </p>
      </div>

      {/* Pipeline */}
      <div className="flex items-center gap-0">
        {stages.map((stage, i) => {
          const Icon = stage.icon;
          const stageDelay = i * 0.4;
          const pipeDelay = stageDelay + 0.2;

          return (
            <div key={stage.label} className="flex items-center">
              {/* Stage node */}
              <div className="flex flex-col items-center">
                <div
                  className="w-14 h-14 rounded-2xl border border-primary/20 bg-card flex items-center justify-center"
                  style={{
                    opacity: 0,
                    animation: `pipeline-stage-in 0.5s ease-out ${stageDelay}s forwards, pipeline-glow-pulse 1.5s ease-in-out ${stageDelay + 0.5}s infinite`,
                  }}
                >
                  <Icon size={22} className="text-primary" />
                </div>
                <span
                  className="font-mono text-[11px] text-muted-foreground mt-2.5 tracking-wide"
                  style={{
                    opacity: 0,
                    animation: `pipeline-label-in 0.3s ease-out ${stageDelay + 0.2}s forwards`,
                  }}
                >
                  {stage.label}
                </span>
              </div>

              {/* Connecting pipe */}
              {i < stages.length - 1 && (
                <div className="w-20 sm:w-28 h-0.5 bg-border/40 mx-1.5 relative overflow-hidden rounded-full self-start mt-7">
                  <div
                    className="absolute inset-y-0 left-0 bg-primary rounded-full"
                    style={{
                      width: "0%",
                      animation: `pipeline-pipe-flow 0.35s ease-out ${pipeDelay}s forwards`,
                    }}
                  />
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: "0%",
                      background: "hsl(var(--node-glow))",
                      opacity: 0.35,
                      filter: "blur(4px)",
                      animation: `pipeline-pipe-flow 0.35s ease-out ${pipeDelay}s forwards`,
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Loading dots */}
      <div
        className="mt-12 flex items-center gap-2"
        style={{
          opacity: 0,
          animation: "pipeline-subtitle-in 0.3s ease-out 1.6s forwards",
        }}
      >
        {[0, 1, 2].map((d) => (
          <div
            key={d}
            className="w-1.5 h-1.5 rounded-full bg-primary/80"
            style={{
              animation: `pipeline-glow-pulse 1s ease-in-out ${d * 0.2}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
