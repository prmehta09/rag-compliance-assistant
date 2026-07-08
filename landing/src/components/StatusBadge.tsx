import type { FindingStatus } from "../lib/api";

const STATUS_STYLES: Record<FindingStatus, string> = {
  Addressed: "text-emerald-400 bg-emerald-400/10 ring-emerald-400/25",
  "Partially Addressed": "text-amber-400 bg-amber-400/10 ring-amber-400/25",
  Gap: "text-red-400 bg-red-400/10 ring-red-400/25",
  "Not Applicable": "text-paper-faint bg-white/5 ring-white/10",
};

/** Small colored status chip - green/amber/red/grey per finding status. */
export function StatusBadge({ status }: { status: FindingStatus }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.1em] ring-1 ring-inset ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}
