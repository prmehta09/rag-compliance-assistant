import { useState } from "react";
import { GitFork, Menu, X } from "lucide-react";

const NAV_ITEMS = [
  { label: "Overview", href: "#overview", active: true },
  { label: "Architecture", href: "#architecture" },
  { label: "Pipeline", href: "#pipeline" },
  { label: "Results", href: "#results" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="absolute inset-x-0 top-0 z-50">
      <div className="mx-auto grid max-w-7xl grid-cols-2 items-center px-6 py-6 sm:px-10 lg:grid-cols-3 lg:px-16">
        <a href="#overview" className="flex items-baseline gap-2.5 justify-self-start">
          <span className="font-serif text-lg italic tracking-tight text-paper">
            Veritas
          </span>
          <span className="hidden text-[10px] font-medium uppercase tracking-[0.16em] text-paper-faint sm:inline">
            Agentic RAG Compliance Auditor
          </span>
        </a>

        <nav
          aria-label="Primary"
          className="hidden justify-self-center lg:block"
        >
          <ul className="flex items-center gap-8">
            {NAV_ITEMS.map((item) => (
              <li key={item.label}>
                <a
                  href={item.href}
                  aria-current={item.active ? "page" : undefined}
                  className={`relative py-1 text-sm transition-colors duration-200 ${
                    item.active
                      ? "text-paper"
                      : "text-paper-faint hover:text-paper"
                  }`}
                >
                  {item.label}
                  {item.active && (
                    <span
                      aria-hidden
                      className="absolute -bottom-1 left-0 h-px w-full bg-clay"
                    />
                  )}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="hidden justify-self-end lg:flex">
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            aria-label="View source on GitHub"
            className="text-paper-faint transition-colors duration-200 hover:text-paper"
          >
            <GitFork className="h-5 w-5" aria-hidden />
          </a>
        </div>

        <button
          type="button"
          onClick={() => setMobileOpen((open) => !open)}
          aria-expanded={mobileOpen}
          aria-label="Toggle navigation menu"
          className="justify-self-end text-paper lg:hidden"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && (
        <nav
          aria-label="Primary mobile"
          className="mx-6 rounded-2xl border border-void-line bg-void-raised px-6 py-5 lg:hidden"
        >
          <ul className="flex flex-col gap-4">
            {NAV_ITEMS.map((item) => (
              <li key={item.label}>
                <a
                  href={item.href}
                  className={`text-sm ${item.active ? "text-paper" : "text-paper-faint"}`}
                  onClick={() => setMobileOpen(false)}
                >
                  {item.label}
                </a>
              </li>
            ))}
            <li>
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 text-sm text-paper-faint"
              >
                <GitFork className="h-4 w-4" aria-hidden />
                GitHub
              </a>
            </li>
          </ul>
        </nav>
      )}
    </header>
  );
}
