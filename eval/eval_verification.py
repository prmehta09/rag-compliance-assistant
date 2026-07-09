"""Runs the verified compliance audit (audit.py's --verify logic) across every
sample document in data/documents_to_check/, using our best retrieval setup
(cross-encoder re-ranking, since we proved it beats plain retrieval), and
reports aggregate statistics on how often the self-verification step flags
findings for human review - and, best-effort, why.

This makes real Claude API calls: (checkpoints) x (documents) x 2 calls each
(one to produce the finding, one to verify it). See CLAUDE.md for the current
cost estimate before running this."""

import sys
from collections import Counter
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from ask import load_api_key  # noqa: E402
from audit import (  # noqa: E402
    CHECKPOINTS,
    FLAGGED_VERDICTS,
    audit_checkpoint,
    build_document_excerpt,
    retrieve_rules,
    split_into_sections,
    verify_finding,
)
from search import get_collection  # noqa: E402

DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents_to_check"
REPORT_PATH = Path(__file__).resolve().parent.parent / "reports" / "verification_eval_summary.md"

# Best-effort keyword patterns for classifying WHY a finding got flagged, based
# on the verifier's free-text reason. This is a simple heuristic, not a
# precise classifier - anything that doesn't match falls into "other".
FLAG_CATEGORY_KEYWORDS = {
    "Citation not grounded in retrieved evidence": [
        "not provided", "not actually appear", "wasn't provided", "was not provided",
        "not among", "not included in", "does not appear in the document",
        "excerpt provided does not", "excerpt was not provided", "not directly include",
        "not in the materials", "rule excerpt does not",
    ],
    "Overstated / imprecise explanation": [
        "overstat", "understat", "imprecise", "conflate", "not fully grounded",
        "oversimplif", "too broad", "too narrow",
    ],
}


def list_documents(exclude: list[str] = ()) -> list[Path]:
    """Every sample document to audit, skipping the folder's own README and
    anything named in `exclude` (e.g. to skip a large/expensive document)."""
    return sorted(
        p for p in DOCUMENTS_DIR.glob("*.md")
        if p.name != "README.md" and p.name not in exclude
    )


def parse_args(argv: list[str]) -> list[str]:
    """Collect filenames passed as --exclude <filename>, repeatable."""
    excludes = []
    i = 0
    while i < len(argv):
        if argv[i] == "--exclude" and i + 1 < len(argv):
            excludes.append(argv[i + 1])
            i += 2
        else:
            i += 1
    return excludes


def categorize_flag_reason(reason: str) -> str:
    """Best-effort bucket for a flagged finding's reason text, based on keyword matches."""
    lowered = reason.lower()
    for category, keywords in FLAG_CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Other"


def audit_one_document(client: Anthropic, collection, doc_path: Path) -> list[dict]:
    """Run the full verified audit (all checkpoints) on one document, using re-ranked retrieval."""
    text = doc_path.read_text(encoding="utf-8")
    document_excerpt = build_document_excerpt(split_into_sections(text))

    results = []
    for checkpoint in CHECKPOINTS:
        rule_chunks = retrieve_rules(collection, checkpoint, rerank=True)
        finding = audit_checkpoint(client, checkpoint, rule_chunks, document_excerpt)
        verification = verify_finding(client, checkpoint, finding, rule_chunks, document_excerpt)
        finding["verification"] = verification
        finding["document"] = doc_path.name
        results.append(finding)
    return results


def build_summary(all_results: list[dict]) -> str:
    """Format the aggregate verification statistics into one readable report."""
    lines = ["# Self-Verification Evaluation Summary", ""]
    total = len(all_results)
    verdict_counts = Counter(r["verification"]["verdict"] for r in all_results)
    flagged = [r for r in all_results if r["verification"]["verdict"] in FLAGGED_VERDICTS]

    lines.append("## Overall")
    lines.append("")
    lines.append(f"- Total findings produced: {total}")
    for verdict in ("Verified", "Questionable", "Unsupported"):
        count = verdict_counts.get(verdict, 0)
        lines.append(f"- {verdict}: {count} ({count / total:.1%})")
    other = total - sum(verdict_counts.get(v, 0) for v in ("Verified", "Questionable", "Unsupported"))
    if other:
        lines.append(f"- Other/unparsed verdicts: {other} ({other / total:.1%})")
    lines.append(f"- **Flagged for human review (Questionable + Unsupported): {len(flagged)} ({len(flagged) / total:.1%})**")
    lines.append("")

    lines.append("## Why findings were flagged (best-effort categorization)")
    lines.append("")
    if flagged:
        reason_counts = Counter(categorize_flag_reason(r["verification"]["reason"]) for r in flagged)
        for category, count in reason_counts.most_common():
            lines.append(f"- {category}: {count} ({count / len(flagged):.1%} of flagged findings)")
    else:
        lines.append("No findings were flagged.")
    lines.append("")

    lines.append("## Per-document breakdown")
    lines.append("")
    documents = sorted(set(r["document"] for r in all_results))
    for doc in documents:
        doc_results = [r for r in all_results if r["document"] == doc]
        doc_flagged = [r for r in doc_results if r["verification"]["verdict"] in FLAGGED_VERDICTS]
        doc_verdicts = Counter(r["verification"]["verdict"] for r in doc_results)
        lines.append(f"### {doc}")
        lines.append(f"- Findings: {len(doc_results)}")
        for verdict in ("Verified", "Questionable", "Unsupported"):
            lines.append(f"  - {verdict}: {doc_verdicts.get(verdict, 0)}")
        lines.append(f"  - Flagged for human review: {len(doc_flagged)}/{len(doc_results)}")
        for r in doc_flagged:
            v = r["verification"]
            lines.append(f"    - **{r['checkpoint']}** ({v['verdict']}, {v['confidence']} confidence): {v['reason']}")
        lines.append("")

    return "\n".join(lines)


def main():
    excludes = parse_args(sys.argv[1:])
    documents = list_documents(exclude=excludes)
    if excludes:
        print(f"Excluding: {', '.join(excludes)}")
    print(f"Found {len(documents)} documents to audit: {', '.join(d.name for d in documents)}\n")

    print("Connecting to Chroma (embedding/re-ranking happens via Voyage AI per-request)...")
    collection = get_collection()

    print("Loading Anthropic client...\n")
    client = Anthropic(api_key=load_api_key())

    all_results = []
    for doc_num, doc_path in enumerate(documents, start=1):
        print(f"Document {doc_num}/{len(documents)}: {doc_path.name}")
        doc_results = audit_one_document(client, collection, doc_path)
        for r in doc_results:
            flag = " [FLAGGED]" if r["verification"]["verdict"] in FLAGGED_VERDICTS else ""
            print(f"  {r['checkpoint']}: {r['status']} -> verifier: {r['verification']['verdict']}{flag}")
        all_results.extend(doc_results)
        print()

    summary = build_summary(all_results)
    print(summary)

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(summary, encoding="utf-8")
    print(f"\nFull summary also saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
