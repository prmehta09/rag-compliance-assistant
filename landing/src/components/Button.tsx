import type { ComponentPropsWithoutRef } from "react";
import { ArrowRight } from "lucide-react";

type ButtonProps = ComponentPropsWithoutRef<"button">;

export function PrimaryButton({ children, className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`group inline-flex items-center gap-2 rounded-full bg-paper px-6 py-3 text-sm font-medium text-void transition-all duration-300 ease-out hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-paper ${className}`}
      {...props}
    >
      {children}
      <ArrowRight
        className="h-4 w-4 transition-transform duration-300 ease-out group-hover:translate-x-0.5"
        aria-hidden
      />
    </button>
  );
}
