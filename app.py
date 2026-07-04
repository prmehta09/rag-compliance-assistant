"""Streamlit web page for the compliance auditor. Lets you pick one of our
sample documents and either:
  - view an already-generated audit report for free (parses the saved
    Markdown report back into structured data), or
  - run a brand new live audit, which makes real Claude API calls using our
    best setup (re-ranked retrieval + self-verification).

Run with: streamlit run app.py

Visual design note: colors are the fixed "status" tokens (good/warning/
critical/muted) rather than arbitrary theme colors, since they encode a
real state (Addressed/Partial/Gap and Verified/Questionable/Unsupported),
always paired with an emoji/label so color is never the only signal.
"""

import re
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ask import load_api_key  # noqa: E402
from audit import (  # noqa: E402
    CHECKPOINTS,
    FLAGGED_VERDICTS,
    STATUS_ORDER,
    audit_checkpoint,
    build_document_excerpt,
    build_report,
    retrieve_rules,
    save_report,
    split_into_sections,
    verify_finding,
)
from search import get_collection  # noqa: E402

REPORTS_DIR = Path("reports")

# Friendly labels for the dropdown, mapped to the actual sample document files.
DOCUMENTS = {
    "GitHub — Privacy Statement (big tech)": Path("data/documents_to_check/github_privacy_policy.md"),
    "Teladoc Health — Privacy Policy (healthcare)": Path("data/documents_to_check/teladoc_privacy_policy.md"),
    "eBay — User Privacy Notice (e-commerce)": Path("data/documents_to_check/ebay_privacy_policy.md"),
    "Mozilla — Privacy Notice (tech, bonus)": Path("data/documents_to_check/mozilla_privacy_policy.md"),
}

STATUS_EMOJI = {"Gap": "🔴", "Partially Addressed": "🟡", "Addressed": "🟢", "Not Applicable": "⚪"}
VERDICT_EMOJI = {"Verified": "✅", "Questionable": "⚠️", "Unsupported": "❌"}

# Fixed semantic colors (never reassigned to arbitrary series) - same hex used
# for card borders/glows, badges, and the chart colors below, so every part of
# the page agrees on what "Gap" or "Questionable" looks like.
GOOD, WARNING, CRITICAL, MUTED = "#0ca30c", "#fab219", "#d03b3b", "#898781"
STATUS_COLORS = {"Gap": CRITICAL, "Partially Addressed": WARNING, "Addressed": GOOD, "Not Applicable": MUTED}
VERDICT_COLORS = {"Verified": GOOD, "Questionable": WARNING, "Unsupported": CRITICAL}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

.stApp {
    background: radial-gradient(circle at 15% -10%, #16213e 0%, #05070d 55%, #05070d 100%);
}

.gradient-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 2.5rem;
    line-height: 1.15;
    background: linear-gradient(90deg, #22d3ee 0%, #8b7cf6 55%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.3rem;
}

.subtitle { color: #a3a8b8; font-size: 1.02rem; margin-bottom: 1.6rem; max-width: 46rem; }

.stat-card {
    background: rgba(255, 255, 255, 0.04);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 1.1rem 0.5rem;
    text-align: center;
}
.stat-card .stat-icon { font-size: 1.5rem; }
.stat-card .stat-value { font-weight: 700; font-size: 2.1rem; margin: 0.15rem 0; color: #f4f5f7; }
.stat-card .stat-label { color: #a3a8b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }
.glow-good     { box-shadow: 0 0 22px rgba(12,163,12,0.30);  border-color: rgba(12,163,12,0.40) !important; }
.glow-warning  { box-shadow: 0 0 22px rgba(250,178,25,0.30); border-color: rgba(250,178,25,0.40) !important; }
.glow-critical { box-shadow: 0 0 22px rgba(208,59,59,0.30);  border-color: rgba(208,59,59,0.40) !important; }
.glow-accent   { box-shadow: 0 0 22px rgba(34,211,238,0.22); border-color: rgba(34,211,238,0.35) !important; }

.chart-card {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 14px;
    padding: 0.8rem 1rem 0.2rem 1rem;
    margin-bottom: 1rem;
}

.finding-card {
    background: rgba(255, 255, 255, 0.035);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 4px solid #898781;
    border-radius: 12px;
    padding: 1rem 1.3rem;
    margin-bottom: 0.9rem;
}
.finding-card.flagged { box-shadow: 0 0 22px rgba(250,178,25,0.22); }

.finding-title { font-weight: 600; font-size: 1.05rem; margin-bottom: 0.5rem; color: #f4f5f7; }
.citation-chip {
    display: inline-block;
    padding: 0.15rem 0.65rem;
    border-radius: 999px;
    font-size: 0.8rem;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.14);
    color: #cbd0dc;
    margin-bottom: 0.55rem;
}
.explanation-text { color: #c3c7d1; font-size: 0.94rem; line-height: 1.5; margin-bottom: 0.6rem; }

.verdict-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 600;
}
.verdict-reason { color: #9a9fae; font-size: 0.86rem; margin-top: 0.4rem; }
</style>
"""


def report_path_for(doc_path: Path) -> Path:
    """Where audit.py's save_report() would have saved this document's report."""
    return REPORTS_DIR / f"{doc_path.stem}_audit.md"


def parse_verification_line(line: str) -> dict:
    """Parse one '- Verification: Verdict (confidence: X) [NEEDS HUMAN REVIEW] — reason' line."""
    match = re.match(
        r"- Verification: (.+?) \(confidence: (.+?)\)(?: \[NEEDS HUMAN REVIEW\])? — (.*)",
        line,
    )
    if not match:
        return {"verdict": "Unparsed", "confidence": "", "reason": line}
    verdict, confidence, reason = match.groups()
    # Claude doesn't always match our requested capitalization exactly (e.g.
    # "VERIFIED" instead of "Verified") - normalize so display is consistent.
    return {"verdict": verdict.strip().capitalize(), "confidence": confidence.strip(), "reason": reason.strip()}


def parse_audit_report(text: str) -> list[dict]:
    """Parse audit.py's saved Markdown report back into structured findings,
    so a report loaded from disk displays the same way as one just produced
    by a live run. The "Needs Human Review" summary section is skipped and
    recomputed from the per-checkpoint data instead, to avoid maintaining
    two copies of the same information."""
    findings = []
    sections = text.split("\n## ")[1:]  # each section is one status group
    for section in sections:
        header_line, _, body = section.partition("\n")
        status = re.sub(r"\s*\(\d+\)\s*$", "", header_line).strip()
        if status == "Needs Human Review":
            continue

        for block in body.split("\n### ")[1:]:  # each block is one checkpoint
            lines = block.strip().splitlines()
            checkpoint = lines[0].strip()
            citation, explanation, verification = "", "", None
            for line in lines[1:]:
                if line.startswith("- Citation:"):
                    citation = line.split(":", 1)[1].strip()
                elif line.startswith("- Explanation:"):
                    explanation = line.split(":", 1)[1].strip()
                elif line.startswith("- Verification:"):
                    verification = parse_verification_line(line)
            findings.append({
                "checkpoint": checkpoint,
                "status": status,
                "citation": citation,
                "explanation": explanation,
                "verification": verification,
            })
    return findings


@st.cache_resource
def get_cached_collection():
    """Cache the embedding model + Chroma connection across reruns, since
    Streamlit reruns the whole script on every interaction and reloading the
    model each time would make the app feel slow."""
    return get_collection()


@st.cache_resource
def get_cached_client() -> Anthropic:
    return Anthropic(api_key=load_api_key())


def run_live_audit(doc_path: Path) -> list[dict]:
    """Run a full verified audit on one document, using our best retrieval
    setup (re-ranked), reusing audit.py's own functions - not a reimplementation."""
    text = doc_path.read_text(encoding="utf-8")
    document_excerpt = build_document_excerpt(split_into_sections(text))
    collection = get_cached_collection()
    client = get_cached_client()

    progress = st.progress(0.0, text="Starting audit...")
    results = []
    for i, checkpoint in enumerate(CHECKPOINTS, start=1):
        progress.progress((i - 1) / len(CHECKPOINTS), text=f"Checking: {checkpoint['name']}...")
        rule_chunks = retrieve_rules(collection, checkpoint, rerank=True)
        finding = audit_checkpoint(client, checkpoint, rule_chunks, document_excerpt)
        finding["verification"] = verify_finding(client, checkpoint, finding, rule_chunks, document_excerpt)
        results.append(finding)
    progress.progress(1.0, text="Done.")

    report_text = build_report(str(doc_path), results, verified=True)
    saved_path = save_report(str(doc_path), report_text)
    st.success(f"Live audit complete! Report saved to {saved_path}")
    return results


def render_summary(findings: list[dict]) -> None:
    """Four glowing stat cards: total checkpoints, verified, gaps, flagged."""
    total = len(findings)
    verified = sum(1 for f in findings if f["verification"] and f["verification"]["verdict"] == "Verified")
    gaps = sum(1 for f in findings if f["status"] == "Gap")
    flagged = sum(1 for f in findings if f["verification"] and f["verification"]["verdict"] in FLAGGED_VERDICTS)

    cards = [
        ("🧭", total, "Checkpoints", "glow-accent"),
        ("✅", verified, "Verified", "glow-good"),
        ("🔴", gaps, "Gaps", "glow-critical"),
        ("⚠️", flagged, "Flagged for review", "glow-warning"),
    ]
    cols = st.columns(4)
    for col, (icon, value, label, glow) in zip(cols, cards):
        col.markdown(
            f"""<div class="stat-card {glow}">
                    <div class="stat-icon">{icon}</div>
                    <div class="stat-value">{value}</div>
                    <div class="stat-label">{label}</div>
                </div>""",
            unsafe_allow_html=True,
        )


def render_status_chart(findings: list[dict]) -> None:
    """Donut chart of checkpoint statuses - a quick "at a glance" view, with
    the exact counts already given in the stat cards and the legend/hover."""
    counts = {status: sum(1 for f in findings if f["status"] == status) for status in STATUS_ORDER}
    counts = {status: n for status, n in counts.items() if n > 0}

    fig = go.Figure(go.Pie(
        labels=[f"{status} ({n})" for status, n in counts.items()],
        values=list(counts.values()),
        hole=0.62,
        marker=dict(colors=[STATUS_COLORS[s] for s in counts], line=dict(color="#05070d", width=3)),
        textinfo="percent",
        textposition="outside",
        textfont=dict(color="#cbd0dc", family="Inter, sans-serif", size=12),
        hoverinfo="label+value+percent",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#e5e7eb"),
        legend=dict(font=dict(color="#cbd0dc", size=12)),
        margin=dict(t=30, b=10, l=10, r=10),
        height=300,
        showlegend=True,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_compliance_gauge(findings: list[dict]) -> None:
    """Meter-style gauge: a compliance score out of 100, counting Addressed as
    a full point and Partially Addressed as a half point, over every checkpoint
    that actually applies (excluding Not Applicable ones)."""
    applicable = [f for f in findings if f["status"] != "Not Applicable"]
    if not applicable:
        st.info("No applicable checkpoints to score.")
        return

    points = sum(1.0 if f["status"] == "Addressed" else 0.5 if f["status"] == "Partially Addressed" else 0.0
                 for f in applicable)
    score = round(100 * points / len(applicable))
    severity = GOOD if score >= 70 else WARNING if score >= 40 else CRITICAL

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(suffix="%", font=dict(color=severity, family="Inter, sans-serif", size=42)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="#5b6178", tickfont=dict(color="#8b90a3", size=10)),
            bar=dict(color=severity, thickness=0.3),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[dict(range=[0, 100], color="rgba(255,255,255,0.06)")],
        ),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#e5e7eb"),
        margin=dict(t=20, b=10, l=30, r=30),
        height=300,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_needs_review(findings: list[dict]) -> None:
    flagged = [f for f in findings if f["verification"] and f["verification"]["verdict"] in FLAGGED_VERDICTS]
    if not flagged:
        return

    st.subheader(f"⚠️ Needs Human Review ({len(flagged)})")
    for f in flagged:
        v = f["verification"]
        color = VERDICT_COLORS.get(v["verdict"], MUTED)
        st.markdown(
            f"""<div class="finding-card flagged" style="border-left-color:{color};">
                    <div class="finding-title">{f['checkpoint']} <span style="color:#9a9fae; font-weight:400;">
                        — original status: {f['status']}</span></div>
                    <span class="verdict-badge" style="color:{color}; border:1px solid {color}66;">
                        {VERDICT_EMOJI.get(v['verdict'], '❔')} {v['verdict']} (confidence: {v['confidence']})</span>
                    <div class="verdict-reason">{v['reason']}</div>
                </div>""",
            unsafe_allow_html=True,
        )


def render_finding(finding: dict) -> None:
    status = finding["status"]
    emoji = STATUS_EMOJI.get(status, "❔")
    status_color = STATUS_COLORS.get(status, MUTED)

    v = finding["verification"]
    verification_html = ""
    if v:
        v_color = VERDICT_COLORS.get(v["verdict"], MUTED)
        flagged_tag = " · <strong>NEEDS HUMAN REVIEW</strong>" if v["verdict"] in FLAGGED_VERDICTS else ""
        verification_html = f"""
            <span class="verdict-badge" style="color:{v_color}; border:1px solid {v_color}66;">
                {VERDICT_EMOJI.get(v['verdict'], '❔')} {v['verdict']} (confidence: {v['confidence']}){flagged_tag}
            </span>
            <div class="verdict-reason">{v['reason']}</div>
        """
    flagged_class = " flagged" if v and v["verdict"] in FLAGGED_VERDICTS else ""

    st.markdown(
        f"""<div class="finding-card{flagged_class}" style="border-left-color:{status_color};">
                <div class="finding-title">{emoji} {status} — {finding['checkpoint']}</div>
                <div class="citation-chip">📖 {finding['citation']}</div>
                <div class="explanation-text">{finding['explanation']}</div>
                {verification_html}
            </div>""",
        unsafe_allow_html=True,
    )


def render_results(findings: list[dict]) -> None:
    st.subheader("📊 Summary")
    render_summary(findings)

    st.write("")
    col_chart, col_gauge = st.columns(2)
    with col_chart:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("**Checkpoint Status Breakdown**")
        render_status_chart(findings)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_gauge:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("**Compliance Score**")
        render_compliance_gauge(findings)
        st.markdown("</div>", unsafe_allow_html=True)

    render_needs_review(findings)

    st.subheader("📋 All Checkpoints")
    for status in STATUS_ORDER:
        for finding in [f for f in findings if f["status"] == status]:
            render_finding(finding)


def main():
    st.set_page_config(page_title="GDPR/HIPAA Compliance Auditor", page_icon="🔍", layout="centered")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.markdown('<div class="gradient-title">🔍 GDPR/HIPAA Compliance Auditor</div>', unsafe_allow_html=True)
    st.markdown(
        """<div class="subtitle">An AI assistant that audits documents (like privacy policies) against key
        GDPR/HIPAA obligations — citing the exact rule for every finding, and double-checking its own work
        with an independent verification pass.</div>""",
        unsafe_allow_html=True,
    )

    doc_label = st.selectbox("Choose a document to audit:", list(DOCUMENTS.keys()))
    doc_path = DOCUMENTS[doc_label]

    mode = st.radio("Mode:", ["View saved report (free, instant)", "Run live audit (costs money)"])

    if "live_results" not in st.session_state:
        st.session_state.live_results = {}

    findings = None

    if mode.startswith("View saved report"):
        report_path = report_path_for(doc_path)
        if report_path.exists():
            findings = parse_audit_report(report_path.read_text(encoding="utf-8"))
        else:
            st.info(f'No saved report yet for **{doc_path.name}**. Switch to "Run live audit" to generate one.')
    else:
        st.warning(
            "⚠️ This calls the Claude API roughly 20 times (10 checkpoints × audit + verify), "
            "using our best setup: re-ranked retrieval + self-verification. "
            "Estimated cost: roughly $0.10–$0.30 depending on document size."
        )
        if st.button("Run Live Audit Now"):
            st.session_state.live_results[str(doc_path)] = run_live_audit(doc_path)
        findings = st.session_state.live_results.get(str(doc_path))

    if findings:
        render_results(findings)


if __name__ == "__main__":
    main()
