interface BadgeProps {
  children: string;
}

/** The small eyebrow line above the hero title — quiet, not a loud chip. */
export function Badge({ children }: BadgeProps) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-void-line px-3 py-1 text-paper-faint">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-clay" aria-hidden />
      <span className="text-[11px] font-medium uppercase tracking-[0.22em]">
        {children}
      </span>
    </div>
  );
}
