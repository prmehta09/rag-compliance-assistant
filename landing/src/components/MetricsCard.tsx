import { ShieldCheck, TrendingUp } from "lucide-react";

/** A quiet product stat card — real pipeline numbers, not a dashboard mock. */
export function MetricsCard() {
  return (
    <div className="w-full max-w-xs rounded-2xl border border-void-line bg-void-raised px-6 py-6">
      <div className="flex items-center gap-2 text-paper-faint">
        <TrendingUp className="h-3.5 w-3.5" aria-hidden />
        <span className="text-[11px] font-medium uppercase tracking-[0.16em]">
          Retrieval Quality
        </span>
      </div>
      <p className="mt-3 font-serif text-3xl italic text-paper">
        57.9% <span className="not-italic text-paper-faint">→</span> 78.9%
      </p>
      <p className="mt-1.5 text-xs leading-relaxed text-paper-dim">
        Hit Rate@5 · cross-encoder re-ranking
      </p>

      <div className="my-5 h-px bg-void-line" />

      <div className="flex items-center gap-2 text-paper-faint">
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
        <span className="text-[11px] font-medium uppercase tracking-[0.16em]">
          Self-Verification
        </span>
      </div>
      <p className="mt-3 font-serif text-3xl italic text-paper">~17%</p>
      <p className="mt-1.5 text-xs leading-relaxed text-paper-dim">
        Findings flagged for human review
      </p>
    </div>
  );
}
