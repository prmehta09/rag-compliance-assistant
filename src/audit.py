"""Audits a document (e.g. a privacy policy) against a curated list of GDPR/HIPAA
compliance checkpoints. For each checkpoint, it retrieves the relevant rule(s)
from our Chroma database and asks Claude to judge whether the document
adequately addresses that obligation, citing the exact rule it relied on.

With --verify, each finding is then checked by a second, independent Claude
call whose only job is to try to poke holes in the first finding - catching
citations that don't say what was claimed, or statuses the document text
doesn't actually support."""

import sys
from pathlib import Path

from anthropic import Anthropic

from ask import MODEL, load_api_key
from search import get_collection

DEFAULT_DOCUMENT = "data/documents_to_check/github_privacy_policy.md"
# Generous cap - Haiku's 200K-token context comfortably fits any of our sample
# documents in full (even the largest, ~123K chars). This only kicks in as a
# safety net for unusually huge future documents, not to shrink normal ones -
# truncating real content risks reporting a false "Gap" just because the
# relevant part of the document got cut off before Claude saw it.
MAX_EXCERPT_CHARS = 150000
RULES_PER_CHECKPOINT = 3
MAX_TOKENS = 300

# The curated list of compliance obligations to check for. Each has a short
# "query" used to retrieve matching rules from Chroma - add more entries here
# to extend what the audit covers.
CHECKPOINTS = [
    {
        "id": "lawful_basis",
        "name": "Lawful basis / consent for processing",
        "query": "lawful basis for processing personal data, consent requirements",
    },
    {
        "id": "right_to_access",
        "name": "Right to access personal data",
        "query": "individual's right to access their personal data or medical records",
    },
    {
        "id": "right_to_erasure",
        "name": "Right to erasure / deletion",
        "query": "right to erasure, right to be forgotten, deleting personal data",
    },
    {
        "id": "data_portability",
        "name": "Right to data portability",
        "query": "right to data portability, receiving personal data in a portable format",
    },
    {
        "id": "right_to_object",
        "name": "Right to object / opt out of marketing",
        "query": "right to object to processing, opting out of direct marketing",
    },
    {
        "id": "data_retention",
        "name": "Data retention limits",
        "query": "limiting storage of personal data, data retention periods",
    },
    {
        "id": "breach_notification",
        "name": "Data breach notification",
        "query": "notifying individuals or authorities of a personal data breach",
    },
    {
        "id": "security_safeguards",
        "name": "Security safeguards",
        "query": "technical and organizational security measures to protect personal data",
    },
    {
        "id": "international_transfers",
        "name": "International data transfers",
        "query": "transferring personal data to other countries, cross-border data transfers",
    },
    {
        "id": "transparency_notice",
        "name": "Transparency / notice of privacy practices",
        "query": "informing individuals about how their personal data is collected and used",
    },
]

SYSTEM_PROMPT = """You are a compliance auditor checking whether a document (e.g. a privacy policy) \
adequately addresses one specific GDPR/HIPAA obligation.

Rules you must follow:
- Base your judgment ONLY on the provided document text and the provided rule excerpts. Do not use \
outside knowledge of GDPR/HIPAA beyond what is given to you.
- Do not invent gaps or compliance that isn't supported by the document text. If the document simply \
doesn't mention something, that IS a gap - but don't assume detail that isn't written.
- If this checkpoint doesn't apply to this document (e.g. a HIPAA obligation for a document that is \
clearly not about health data), answer "Not Applicable" rather than treating it as a gap.
- Respond in EXACTLY this format and nothing else:

STATUS: <Addressed | Partially Addressed | Gap | Not Applicable>
CITATION: <the exact rule citation this judgment relies on, e.g. "Art. 17 GDPR" or "§ 164.524">
EXPLANATION: <one or two plain-language sentences explaining your judgment>"""


def split_into_sections(text: str) -> list[str]:
    """Split a markdown document into sections at each heading line."""
    sections = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [s for s in sections if s]


def build_document_excerpt(sections: list[str], max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Join sections up to a character cap, so very long documents don't blow up cost/latency."""
    excerpt = ""
    for section in sections:
        if len(excerpt) + len(section) > max_chars:
            break
        excerpt = f"{excerpt}\n\n{section}" if excerpt else section
    return excerpt.strip()


def retrieve_rules(collection, checkpoint: dict, top_k: int = RULES_PER_CHECKPOINT) -> list[dict]:
    """Find the rule chunks most relevant to one checkpoint."""
    results = collection.query(query_texts=[checkpoint["query"]], n_results=top_k)
    return [
        {"citation": meta["citation"], "law": meta["law"], "text": doc}
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def build_checkpoint_prompt(checkpoint: dict, rule_chunks: list[dict], document_excerpt: str) -> str:
    rules_block = "\n\n".join(f"[{c['law']} - {c['citation']}]\n{c['text']}" for c in rule_chunks)
    return (
        f"Compliance checkpoint: {checkpoint['name']}\n\n"
        f"Relevant rule excerpts:\n\n{rules_block}\n\n"
        f"Document text to audit:\n\n{document_excerpt}"
    )


def parse_checkpoint_response(text: str) -> dict:
    """Pull the STATUS/CITATION/EXPLANATION lines out of Claude's reply."""
    status, citation, explanation = "Unparsed", "", text.strip()
    for line in text.splitlines():
        if line.startswith("STATUS:"):
            status = line.split(":", 1)[1].strip()
        elif line.startswith("CITATION:"):
            citation = line.split(":", 1)[1].strip()
        elif line.startswith("EXPLANATION:"):
            explanation = line.split(":", 1)[1].strip()
    return {"status": status, "citation": citation, "explanation": explanation}


def audit_checkpoint(client: Anthropic, checkpoint: dict, rule_chunks: list[dict], document_excerpt: str) -> dict:
    """Ask Claude to judge the document against one checkpoint, given the already-retrieved rules."""
    prompt = build_checkpoint_prompt(checkpoint, rule_chunks, document_excerpt)
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    answer_text = next(block.text for block in response.content if block.type == "text")
    result = parse_checkpoint_response(answer_text)
    result["checkpoint"] = checkpoint["name"]
    return result


VERIFY_SYSTEM_PROMPT = """You are an independent compliance reviewer double-checking someone else's \
finding for accuracy. Your job is to catch mistakes, not to rubber-stamp the original conclusion.

You will be given a compliance checkpoint, the rule excerpt(s) the original finding relied on, the \
document text that was audited, and the original finding (its status, cited rule, and explanation).

Independently re-examine the rule excerpts and the document text yourself, as if you were making the \
finding fresh - do not simply assume the original finding is right. Then compare your own conclusion \
to the original finding.

Mark the finding UNSUPPORTED if either is true:
- The cited rule excerpt does not actually say what the explanation claims it says.
- The document text does not actually support the stated status (e.g. the finding says "Addressed" but \
the document doesn't really cover it, or says "Gap" but the document does address it elsewhere in the \
text you were given).

Mark it QUESTIONABLE if the overall conclusion is roughly right but something is off - an imprecise or \
partially wrong citation, an overstated or understated explanation, or reasoning not fully grounded in \
the text you were given.

Otherwise mark it VERIFIED.

Respond in EXACTLY this format and nothing else:

VERDICT: <Verified | Questionable | Unsupported>
CONFIDENCE: <High | Medium | Low>
REASON: <one or two plain-language sentences explaining your verdict>"""


def build_verification_prompt(checkpoint: dict, finding: dict, rule_chunks: list[dict], document_excerpt: str) -> str:
    rules_block = "\n\n".join(f"[{c['law']} - {c['citation']}]\n{c['text']}" for c in rule_chunks)
    return (
        f"Compliance checkpoint: {checkpoint['name']}\n\n"
        f"Relevant rule excerpts:\n\n{rules_block}\n\n"
        f"Document text that was audited:\n\n{document_excerpt}\n\n"
        f"Original finding to check:\n"
        f"STATUS: {finding['status']}\n"
        f"CITATION: {finding['citation']}\n"
        f"EXPLANATION: {finding['explanation']}"
    )


def parse_verification_response(text: str) -> dict:
    """Pull the VERDICT/CONFIDENCE/REASON lines out of Claude's reply."""
    verdict, confidence, reason = "Unparsed", "", text.strip()
    for line in text.splitlines():
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip()
        elif line.startswith("CONFIDENCE:"):
            confidence = line.split(":", 1)[1].strip()
        elif line.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return {"verdict": verdict, "confidence": confidence, "reason": reason}


# Verdicts that mean a human should take a second look before trusting the finding.
FLAGGED_VERDICTS = {"Questionable", "Unsupported"}


def verify_finding(client: Anthropic, checkpoint: dict, finding: dict, rule_chunks: list[dict], document_excerpt: str) -> dict:
    """Run a second, independent Claude call whose only job is to try to poke holes in `finding`."""
    prompt = build_verification_prompt(checkpoint, finding, rule_chunks, document_excerpt)
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=VERIFY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    answer_text = next(block.text for block in response.content if block.type == "text")
    return parse_verification_response(answer_text)


# Ordered so the most actionable findings (gaps) appear first in the report.
STATUS_ORDER = ["Gap", "Partially Addressed", "Addressed", "Not Applicable"]


def build_report(document_path: str, results: list[dict], verified: bool = False) -> str:
    """Format all checkpoint results into one readable report, grouped by status.

    When `verified` is True, each result also carries a "verification" dict, and
    a summary section calling out anything flagged for human review is added
    at the top so those findings aren't buried in the full list.
    """
    lines = ["# Compliance Audit Report", "", f"Document: {document_path}", ""]

    if verified:
        flagged = [r for r in results if r["verification"]["verdict"] in FLAGGED_VERDICTS]
        lines.append(f"## Needs Human Review ({len(flagged)})")
        lines.append("")
        if flagged:
            for r in flagged:
                v = r["verification"]
                lines.append(f"- **{r['checkpoint']}** — original status: {r['status']}, "
                              f"verifier says: {v['verdict']} (confidence: {v['confidence']}) — {v['reason']}")
        else:
            lines.append("None - the verifier agreed with every finding below.")
        lines.append("")

    for status in STATUS_ORDER:
        matching = [r for r in results if r["status"] == status]
        if not matching:
            continue
        lines.append(f"## {status} ({len(matching)})")
        lines.append("")
        for r in matching:
            lines.append(f"### {r['checkpoint']}")
            lines.append(f"- Citation: {r['citation']}")
            lines.append(f"- Explanation: {r['explanation']}")
            if verified:
                v = r["verification"]
                flag = " [NEEDS HUMAN REVIEW]" if v["verdict"] in FLAGGED_VERDICTS else ""
                lines.append(f"- Verification: {v['verdict']} (confidence: {v['confidence']}){flag} — {v['reason']}")
            lines.append("")
    return "\n".join(lines)


def save_report(document_path: str, report_text: str) -> Path:
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    out_path = reports_dir / f"{Path(document_path).stem}_audit.md"
    out_path.write_text(report_text, encoding="utf-8")
    return out_path


def parse_args(argv: list[str]) -> tuple[str, bool]:
    """Pull out the --verify flag; whatever's left (if anything) is the document path."""
    verify = "--verify" in argv
    positional = [a for a in argv if a != "--verify"]
    doc_path = positional[0] if positional else DEFAULT_DOCUMENT
    return doc_path, verify


def main():
    doc_path, verify = parse_args(sys.argv[1:])

    print(f"Step 1/4: Reading and splitting {doc_path}...")
    text = Path(doc_path).read_text(encoding="utf-8")
    sections = split_into_sections(text)
    document_excerpt = build_document_excerpt(sections)
    print(f"  Document has {len(sections)} sections; using {len(document_excerpt)} characters for judgment.")

    print("\nStep 2/4: Loading local embedding model and connecting to Chroma...")
    collection = get_collection()

    print("\nStep 3/4: Loading Anthropic client...")
    client = Anthropic(api_key=load_api_key())

    verify_note = " (with independent verification)" if verify else ""
    print(f"\nStep 4/4: Checking {len(CHECKPOINTS)} compliance checkpoints{verify_note}...")
    results = []
    for i, checkpoint in enumerate(CHECKPOINTS, start=1):
        print(f"  [{i}/{len(CHECKPOINTS)}] {checkpoint['name']}...")
        rule_chunks = retrieve_rules(collection, checkpoint)
        result = audit_checkpoint(client, checkpoint, rule_chunks, document_excerpt)
        print(f"      -> {result['status']}")

        if verify:
            verification = verify_finding(client, checkpoint, result, rule_chunks, document_excerpt)
            result["verification"] = verification
            flag = " [NEEDS HUMAN REVIEW]" if verification["verdict"] in FLAGGED_VERDICTS else ""
            print(f"      -> verifier: {verification['verdict']}{flag}")

        results.append(result)

    print()
    report_text = build_report(doc_path, results, verified=verify)
    print(report_text)

    report_path = save_report(doc_path, report_text)
    print(f"\nFull report also saved to: {report_path}")


if __name__ == "__main__":
    main()
