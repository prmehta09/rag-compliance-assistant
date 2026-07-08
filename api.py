"""FastAPI backend that exposes the existing GDPR/HIPAA compliance audit
pipeline over HTTP, so a separate frontend can trigger real audits instead of
only ever running them from the command line.

This file contains no audit logic of its own. It only:
  - loads the heavy resources (Chroma collection, Anthropic client) once
  - wires HTTP requests to run_audit() (see src/audit.py)
  - shapes the result as JSON

Run it with: venv\\Scripts\\uvicorn.exe api:app --reload
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from anthropic import Anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# audit.py lives in src/ and imports its sibling modules (ask.py, search.py)
# as plain top-level imports - e.g. `from search import get_collection` -
# the same way `python src/audit.py` works when run directly, because Python
# adds a script's own directory to sys.path. Importing audit.py from here
# instead (project root) needs the same thing done by hand, so we add src/
# to sys.path rather than turning src/ into a package and touching files we
# were told not to modify.
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from audit import run_audit  # noqa: E402  (import after sys.path setup, on purpose)
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
