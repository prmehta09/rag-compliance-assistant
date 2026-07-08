import { ShieldAlert, ShieldCheck } from "lucide-react";
import type { Finding } from "../lib/api";
import { StatusBadge } from "./StatusBadge";

interface FindingCardProps {
  finding: Finding;
  index: number;
}

/** One checkpoint result - reuses the site's outline-pill/quiet-card language. */
export function FindingCard({ finding, index }: FindingCardProps) {
  return (
    <li
      className="animate-fade-up rounded-2xl border border-void-line bg-void-raised p-5 sm:p-6"
      style={{ animationDelay: `${Math.min(index, 6) * 40}ms` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-sm font-medium text-paper sm:text-base">{finding.checkpoint}</h3>
        <StatusBadge status={finding.status} />
      </div>

      <p className="mt-3 text-xs uppercase tracking-[0.08em] text-paper-faint">
        {finding.citation}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-paper-dim">{finding.explanation}</p>

      {finding.verification && (
        <div className="mt-4 border-t border-void-line pt-4">
          {finding.flagged ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-xs font-medium text-amber-400">
              <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
              Needs human review
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-void-line px-3 py-1.5 text-xs text-paper-dim">
              <ShieldCheck className="h-3.5 w-3.5 text-paper-faint" aria-hidden />
              {finding.verification.verdict} · {finding.verification.confidence} confidence
            </span>
          )}
        </div>
      )}
    </li>
  );
}
