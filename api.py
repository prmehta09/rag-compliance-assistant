"""FastAPI backend that exposes the existing GDPR/HIPAA compliance audit
pipeline over HTTP, so a separate frontend can trigger real audits instead of
only ever running them from the command line.

This file contains no audit logic of its own. It only:
  - loads the heavy resources (Chroma collection, Anthropic client) once
  - wires HTTP requests to run_audit() (see src/audit.py)
  - shapes the result as JSON

Run it with: venv\\Scripts\\uvicorn.exe api:app --reload
"""

import json
import re
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from anthropic import Anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from report_pdf import markdown_to_pdf_bytes

# audit.py lives in src/ and imports its sibling modules (ask.py, search.py)
# as plain top-level imports - e.g. `from search import get_collection` -
# the same way `python src/audit.py` works when run directly, because Python
# adds a script's own directory to sys.path. Importing audit.py from here
# instead (project root) needs the same thing done by hand, so we add src/
# to sys.path rather than turning src/ into a package and touching files we
# were told not to modify.
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from audit import CHECKPOINTS, build_report, run_audit, run_audit_stream  # noqa: E402  (import after sys.path setup, on purpose)
from search import get_collection  # noqa: E402
from ask import load_api_key  # noqa: E402

DOCUMENTS_DIR = Path(__file__).resolve().parent / "data" / "documents_to_check"

# Heavy resources (the embedding model + Chroma connection, the Anthropic
# client) are built once when the server starts and reused across every
# request - see lifespan() below - instead of being rebuilt on every /audit
# call the way the CLI rebuilds them on every run.
resources: dict = {"collection": None, "client": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    resources["collection"] = get_collection()
    resources["client"] = Anthropic(api_key=load_api_key())
    yield
    resources.clear()


app = FastAPI(title="Veritas Compliance Audit API", lifespan=lifespan)

# Allow the local frontend dev servers to call this API from the browser.
ALLOWED_ORIGINS = [
    "http://localhost:5183",  # landing/ (Vite dev server)
    "http://localhost:5173",  # landing/ (Vite default port)
    "http://localhost:3000",  # generic local React/Next dev server
    # TODO: add your deployed Vercel URL here once you have one, e.g.
    # "https://veritas.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VerificationModel(BaseModel):
    verdict: str
    confidence: str
    reason: str


class FindingModel(BaseModel):
    checkpoint: str
    status: str
    citation: str
    explanation: str
    verification: VerificationModel | None = None  # only present when verify=true
    flagged: bool


class AuditResponse(BaseModel):
    document: str
    findings: list[FindingModel]


class AuditRequest(BaseModel):
    document: str
    # Both default to True: the self-verifying, cross-encoder-re-ranked
    # pipeline is this project's core capability (see CLAUDE.md), not an
    # opt-in extra - an API caller has to deliberately turn it OFF, not on.
    verify: bool = True
    rerank: bool = True


def _available_documents() -> set[str]:
    """Real privacy-policy documents in data/documents_to_check/ - excludes
    README.md, which documents the sample set rather than being one itself."""
    return {p.name for p in DOCUMENTS_DIR.glob("*.md") if p.name.lower() != "readme.md"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def list_documents():
    return sorted(_available_documents())


# The 9 filenames this project ships with - reserved so a pasted policy can
# never overwrite (or silently shadow) one of the curated samples. This is a
# fixed list, not "whatever's on disk right now": auto-suffixing (below) is
# fine for paste-vs-paste name collisions, but a collision with one of these
# specific files is always rejected outright, never worked around.
BUNDLED_SAMPLE_DOCUMENTS = frozenset({
    "github_privacy_policy.md",
    "ebay_privacy_policy.md",
    "mozilla_privacy_policy.md",
    "teladoc_privacy_policy.md",
    "amazon_privacy_policy.md",
    "airbnb_privacy_policy.md",
    "spotify_privacy_policy.md",
    "linkedin_privacy_policy.md",
    "netflix_privacy_policy.md",
})

MIN_PASTE_LENGTH = 200
MAX_PASTE_LENGTH = 100_000  # comfortably under audit.py's 150K silent-truncation cap

# A handful of structural tags that show up in real HTML but essentially
# never in normal prose - used to reject accidental HTML pastes (e.g.
# copy-pasting straight from a browser tab) rather than trying to strip them,
# which risks mangling the exact wording an audit finding might cite.
_HTML_STRUCTURAL_TAGS = re.compile(r"<(!doctype|html|head|body|div|table|script|style)\b", re.IGNORECASE)
_GENERIC_TAG = re.compile(r"</?[a-zA-Z][\w-]*(?:\s[^<>]*)?>")


def _looks_like_html(text: str) -> bool:
    if _HTML_STRUCTURAL_TAGS.search(text):
        return True
    # A handful of stray "<" characters (e.g. "income < $50,000") is normal
    # prose; a pile of tag-shaped substrings is not.
    return len(_GENERIC_TAG.findall(text)) >= 5


def _slugify(name: str) -> str:
    """Collapses anything that isn't a-z/0-9 into a single underscore, so the
    result can only ever contain [a-z0-9_] - no `/`, `\\`, or `..`, which
    rules out path traversal regardless of what the user typed as a name."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


class CreateDocumentRequest(BaseModel):
    name: str
    text: str


class CreateDocumentResponse(BaseModel):
    filename: str
    label: str


@app.post("/documents", response_model=CreateDocumentResponse, status_code=201)
def create_document(request: CreateDocumentRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pasted text is empty.")
    if len(text) < MIN_PASTE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Pasted text is too short (minimum {MIN_PASTE_LENGTH} characters) to be a real policy.",
        )
    if len(text) > MAX_PASTE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Pasted text is too long (maximum {MAX_PASTE_LENGTH:,} characters).",
        )
    if _looks_like_html(text):
        raise HTTPException(
            status_code=400,
            detail="This looks like HTML, not plain text. Please paste the plain policy text only.",
        )

    label = request.name.strip()
    slug = _slugify(label)
    if not slug:
        raise HTTPException(status_code=400, detail="Please provide a name for this policy.")

    base_filename = f"{slug}_privacy_policy.md"
    if base_filename in BUNDLED_SAMPLE_DOCUMENTS:
        raise HTTPException(
            status_code=409,
            detail=f"'{label}' collides with a bundled sample document - please choose a different name.",
        )

    # Paste-vs-paste collisions (not a bundled sample - already excluded
    # above) get auto-disambiguated instead of rejected.
    filename = base_filename
    suffix = 2
    while (DOCUMENTS_DIR / filename).exists():
        filename = f"{slug}_privacy_policy_{suffix}.md"
        suffix += 1

    content = f"# {label}\n\nSource: User-submitted (pasted {date.today().isoformat()})\n\n{text}\n"
    (DOCUMENTS_DIR / filename).write_text(content, encoding="utf-8")

    return CreateDocumentResponse(filename=filename, label=label)


@app.post("/audit", response_model=AuditResponse)
def audit_document(request: AuditRequest):
    if request.document not in _available_documents():
        raise HTTPException(status_code=404, detail=f"Unknown document: {request.document}")

    document_path = DOCUMENTS_DIR / request.document
    try:
        result = run_audit(
            str(document_path),
            verify=request.verify,
            rerank=request.rerank,
            collection=resources["collection"],
            client=resources["client"],
        )
    except Exception as exc:
        # str(exc) is the SDK/library error message, never the API key itself
        # (the key is never part of a request/response body or exception text
        # in the anthropic or chromadb clients) - safe to surface to the caller.
        raise HTTPException(status_code=500, detail=f"Audit failed: {exc}") from exc

    return result


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event: an event name line plus a JSON data line,
    terminated by a blank line (the SSE wire format browsers expect)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream_audit_events(document_path: Path, filename: str, verify: bool, rerank: bool):
    """Drives run_audit_stream() and turns each yielded finding into an SSE
    event. No audit logic lives here - this only formats what run_audit_stream
    already produced."""
    yield _sse("start", {"total": len(CHECKPOINTS), "document": filename})

    try:
        for finding in run_audit_stream(
            str(document_path),
            verify=verify,
            rerank=rerank,
            collection=resources["collection"],
            client=resources["client"],
        ):
            # Round-trip through FindingModel so a streamed finding is
            # validated against the exact same shape /audit's JSON response
            # promises - the two endpoints can't quietly drift apart.
            yield f"event: finding\ndata: {FindingModel(**finding).model_dump_json()}\n\n"
    except Exception as exc:
        # Same rule as /audit: str(exc) is a library error message, never the
        # Anthropic API key (it never appears in SDK exception text).
        yield _sse("error", {"message": f"Audit failed: {exc}"})
        return

    yield _sse("done", {})


@app.post("/audit/stream")
def audit_document_stream(request: AuditRequest):
    if request.document not in _available_documents():
        raise HTTPException(status_code=404, detail=f"Unknown document: {request.document}")

    document_path = DOCUMENTS_DIR / request.document
    return StreamingResponse(
        _stream_audit_events(document_path, request.document, request.verify, request.rerank),
        media_type="text/event-stream",
        headers={
            # Stops intermediary proxies (e.g. nginx) from buffering the
            # response and holding events back until the connection closes.
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _infer_verified(findings: list[FindingModel]) -> bool:
    """build_report() treats verification as all-or-nothing across a single
    audit's findings (run_audit()/run_audit_stream() either set it on every
    finding or none), so checking the first one - once we know there is
    one - tells us how the whole list was produced."""
    if not findings:
        return False
    return findings[0].verification is not None


def _report_markdown(request: AuditResponse) -> str:
    """Rebuilds the exact report build_report() would have produced for this
    audit, straight from the already-computed findings the client sends back
    - no re-auditing, no new Claude/Chroma calls."""
    results = [finding.model_dump() for finding in request.findings]
    return build_report(request.document, results, verified=_infer_verified(request.findings))


@app.post("/report/markdown")
def report_markdown(request: AuditResponse):
    report_text = _report_markdown(request)
    filename = f"{Path(request.document).stem}_audit.md"
    return Response(
        content=report_text,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/report/pdf")
def report_pdf(request: AuditResponse):
    report_text = _report_markdown(request)
    pdf_bytes = markdown_to_pdf_bytes(report_text)
    filename = f"{Path(request.document).stem}_audit.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
