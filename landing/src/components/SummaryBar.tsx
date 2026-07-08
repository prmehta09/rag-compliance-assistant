import { Loader2 } from "lucide-react";
import type { FindingStatus } from "../lib/api";

interface SummaryBarProps {
  score: number | null;
  counts: Record<FindingStatus, number>;
  completed: number;
  total: number;
  running: boolean;
}

const STATUS_ORDER: FindingStatus[] = [
  "Addressed",
  "Partially Addressed",
  "Gap",
  "Not Applicable",
];

const STATUS_DOT: Record<FindingStatus, string> = {
  Addressed: "bg-emerald-400",
  "Partially Addressed": "bg-amber-400",
  Gap: "bg-red-400",
  "Not Applicable": "bg-paper-faint",
};

const RADIUS = 26;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Live compliance-score gauge + status counts + "checkpoint X of N" progress. */
export function SummaryBar({ score, counts, completed, total, running }: SummaryBarProps) {
  const dashOffset =
    score === null ? CIRCUMFERENCE : CIRCUMFERENCE - (score / 100) * CIRCUMFERENCE;

  return (
    <div className="flex flex-col gap-6 rounded-2xl border border-void-line bg-void-raised p-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-5">
        <div className="relative h-16 w-16 shrink-0">
          <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
            <circle
              cx="32"
              cy="32"
              r={RADIUS}
              fill="none"
              strokeWidth="5"
              style={{ stroke: "var(--color-void-line)" }}
            />
            <circle
              cx="32"
              cy="32"
              r={RADIUS}
              fill="none"
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              style={{ stroke: "var(--color-clay)" }}
              className="transition-[stroke-dashoffset] duration-700 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center font-serif text-lg italic text-paper">
            {score === null ? "—" : `${score}%`}
          </div>
        </div>

        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-paper-faint">
            Compliance score
          </p>
          <p className="mt-1 flex items-center gap-2 text-sm text-paper-dim">
            {running && (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-paper-faint" aria-hidden />
            )}
            Checkpoint {completed} of {total || "—"}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {STATUS_ORDER.map((status) => (
          <div key={status} className="flex items-center gap-2 text-xs text-paper-dim">
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT[status]}`} aria-hidden />
            {status} <span className="text-paper-faint">({counts[status]})</span>
          </div>
        ))}
      </div>
    </div>
  );
}
