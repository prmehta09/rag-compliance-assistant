import type { LucideIcon } from "lucide-react";

interface PillProps {
  icon: LucideIcon;
  children: string;
}

/** Understated outline pill — used for the three trust markers, nothing else. */
export function Pill({ icon: Icon, children }: PillProps) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-void-line px-3 py-1.5 text-xs text-paper-dim">
      <Icon className="h-3.5 w-3.5 text-paper-faint" aria-hidden />
      {children}
    </span>
  );
}
