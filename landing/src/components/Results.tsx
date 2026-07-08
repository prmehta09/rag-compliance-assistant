import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ChevronDown } from "lucide-react";
import { PrimaryButton } from "./Button";
import { SummaryBar } from "./SummaryBar";
import { FindingCard } from "./FindingCard";
import { auditStream, getDocuments, type Finding, type FindingStatus } from "../lib/api";

const DOCUMENT_LABELS: Record<string, string> = {
  "github_privacy_policy.md": "GitHub",
  "ebay_privacy_policy.md": "eBay",
  "mozilla_privacy_policy.md": "Mozilla",
  "teladoc_privacy_policy.md": "Teladoc",
  "amazon_privacy_policy.md": "Amazon",
  "airbnb_privacy_policy.md": "Airbnb",
  "spotify_privacy_policy.md": "Spotify",
  "linkedin_privacy_policy.md": "LinkedIn",
  "netflix_privacy_policy.md": "Netflix",
};

function labelFor(filename: string): string {
  if (DOCUMENT_LABELS[filename]) return DOCUMENT_LABELS[filename];

  // Fallback for any future file with no explicit mapping: title-case the
  // name with "_privacy_policy.md" (or just ".md") stripped off.
  const stem = filename.replace(/_privacy_policy\.md$/i, "").replace(/\.md$/i, "");
  return stem
    .replace(/[_-]+/g, " ")
    .trim()
    .split(" ")
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}

const EMPTY_COUNTS: Record<FindingStatus, number> = {
  Addressed: 0,
  "Partially Addressed": 0,
  Gap: 0,
  "Not Applicable": 0,
};

/**
 * The live-audit section (id="results", matched by the navbar's "Results"
 * link). Fetches the document list on mount, then streams a real audit from
 * the FastAPI backend when "Start Auditing" is clicked, rendering findings
 * as they arrive - see src/lib/api.ts for the actual streaming/parsing.
 */
export function Results() {
  const [documents, setDocuments] = useState<string[]>([]);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState("");

  const [findings, setFindings] = useState<Finding[]>([]);
  const [totalCheckpoints, setTotalCheckpoints] = useState(0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocuments()
      .then((docs) => {
        if (cancelled) return;
        setDocuments(docs);
        setSelectedDocument((current) => current || docs[0] || "");
      })
      .catch(() => {
        if (!cancelled) {
          setDocumentsError("Couldn't load the document list. Is the audit server running?");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Stop an in-flight stream if this section unmounts mid-audit.
  useEffect(() => () => cancelRef.current?.(), []);

  const counts = useMemo(() => {
    const next = { ...EMPTY_COUNTS };
    for (const finding of findings) next[finding.status] += 1;
    return next;
  }, [findings]);

  const score = useMemo(() => {
    const scored = counts.Addressed + counts["Partially Addressed"] + counts.Gap;
    if (scored === 0) return null;
    return Math.round(((counts.Addressed * 1 + counts["Partially Addressed"] * 0.5) / scored) * 100);
  }, [counts]);

  function handleStartAuditing() {
    if (!selectedDocument || running) return;

    setFindings([]);
    setTotalCheckpoints(0);
    setError(null);
    setRunning(true);

    const { cancel } = auditStream(
      selectedDocument,
      { verify: true, rerank: true },
      {
        onStart: ({ total }) => setTotalCheckpoints(total),
        onFinding: (finding) => setFindings((prev) => [...prev, finding]),
        onDone: () => setRunning(false),
        onError: (message) => {
          setError(message);
          setRunning(false);
        },
      },
    );
    cancelRef.current = cancel;
  }

  const showSummary = (running || findings.length > 0) && !error;

  return (
    <section
      id="results"
      className="relative z-10 mx-auto w-full max-w-7xl scroll-mt-24 px-6 py-24 sm:px-10 lg:px-16"
    >
      <div className="border-t border-void-line pt-16">
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-paper-faint">
          Live audit
        </p>
        <h2 className="mt-4 max-w-2xl text-3xl leading-tight sm:text-4xl">
          <span className="font-serif italic text-paper">See it</span>{" "}
          <span className="font-sans font-semibold text-paper">find the gaps</span>
        </h2>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-paper-dim">
          Pick a sample privacy policy and run the full self-verifying,
          cross-encoder re-ranked pipeline against it. Findings appear as each
          checkpoint completes.
        </p>

        <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="relative">
            <label htmlFor="document-select" className="sr-only">
              Document to audit
            </label>
            <select
              id="document-select"
              value={selectedDocument}
              onChange={(event) => setSelectedDocument(event.target.value)}
              disabled={running || documents.length === 0}
              className="w-full appearance-none rounded-full border border-void-line bg-void-raised py-3 pl-5 pr-10 text-sm text-paper outline-none transition-colors duration-200 focus-visible:border-clay disabled:opacity-50 sm:w-56"
            >
              {documents.length === 0 && (
                <option>{documentsError ? "Unavailable" : "Loading…"}</option>
              )}
              {documents.map((doc) => (
                <option key={doc} value={doc}>
                  {labelFor(doc)}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-paper-faint"
              aria-hidden
            />
          </div>

          <PrimaryButton
            onClick={handleStartAuditing}
            disabled={running || !selectedDocument}
            aria-busy={running}
          >
            {running ? "Auditing…" : "Start Auditing"}
          </PrimaryButton>
        </div>

        {documentsError && <p className="mt-3 text-sm text-paper-faint">{documentsError}</p>}

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-400/25 bg-amber-400/5 px-5 py-4 text-sm text-paper-dim">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden />
            <p>{error}</p>
          </div>
        )}

        {showSummary && (
          <div className="mt-8">
            <SummaryBar
              score={score}
              counts={counts}
              completed={findings.length}
              total={totalCheckpoints}
              running={running}
            />
          </div>
        )}

        {findings.length > 0 && (
          <ul className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {findings.map((finding, index) => (
              <FindingCard key={`${finding.checkpoint}-${index}`} finding={finding} index={index} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
