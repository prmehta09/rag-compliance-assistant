# Veritas — Agentic RAG Compliance Auditor

An agentic RAG (Retrieval-Augmented Generation) assistant that audits documents — privacy
policies, to start — against GDPR and HIPAA. For each compliance checkpoint it checks, it shows
the exact regulation it relied on (e.g. `Art. 33 GDPR`, `§ 164.524 HIPAA`), then runs an
independent second pass to catch and flag hallucinated or overstated findings before a human
ever sees them.

This is a final-year engineering project, built and documented as a learning project end to end.

## How it works

1. **Retrieve.** For each compliance checkpoint (e.g. "right to erasure," "breach notification"),
   the system searches a vector database of GDPR articles and HIPAA sections for the most
   relevant rule text.
2. **Judge.** The retrieved rule text and the full document being audited are sent to Claude,
   which judges the checkpoint as `Addressed`, `Partially Addressed`, `Gap`, or `Not Applicable`,
   citing the exact rule it relied on.
3. **Self-verify.** A second, independent Claude call re-derives its own judgment from the same
   evidence — without seeing the first call's reasoning — and flags the finding if the citation
   doesn't actually support the claim, or if the status is overstated. Flagged findings are
   surfaced separately as "Needs Human Review."

The full checkpoint list, prompts, and verification logic live in `src/audit.py`.

## Tech stack

- **Python** — the core pipeline (`src/`)
- **ChromaDB** — local vector store for the GDPR/HIPAA rule corpus, configured for cosine
  similarity
- **Voyage AI** — hosted embeddings (`voyage-3.5-lite`) and re-ranking (`rerank-2.5-lite`) for
  retrieval, called directly over REST (see `src/voyage_client.py`)
- **Anthropic Claude** (`claude-haiku-4-5`) — checkpoint judgment, self-verification, and
  question-answering
- **FastAPI** — HTTP API (`api.py`) exposing the audit pipeline, with streaming (SSE) audit
  progress and Markdown/PDF report downloads
- **React + Vite + TypeScript + Tailwind CSS** — frontend (`landing/`)
- **Streamlit** — an alternate, simpler local UI (`app.py`)

TODO(ritesh): confirm whether the FastAPI backend and/or the frontend are actually deployed
anywhere right now (Render/Vercel) — if so, link them here. Not asserting a live URL since I
can't verify one is current from the repo alone.

## Results

Retrieval quality is measured against a hand-curated, 19-question gold set spanning both GDPR
and HIPAA (`eval/gold_retrieval.json`), comparing plain embedding retrieval against the full
re-ranked pipeline.

| | Hit Rate@5 | MRR |
|---|---|---|
| Baseline (embedding only) | 84.2% | 0.689 |
| Full pipeline (+ re-ranking) | 89.5% | 0.820 |

**The headline result is the embedding migration, not re-ranking.** Moving from a local
`all-MiniLM-L6-v2` model to Voyage AI's hosted `voyage-3.5-lite` lifted baseline Hit Rate@5 from
57.9% to 84.2% (+26.3pp) — the new baseline alone now beats the *old full reranked pipeline*
(78.9%). With re-ranking added on top, the full pipeline reaches 89.5% (up from 78.9%, +10.6pp
end-to-end).

Re-ranking still adds a real, consistent gain on top of that stronger baseline — +5.3pp Hit
Rate@5, +0.132 MRR — and across the gold set it never once made a result worse (0 questions
broken, 0 ranked worse; 4 improved, 1 fixed outright, 12 unchanged). Its *marginal* contribution
is smaller than it used to be, but that's because there's simply less headroom left to improve
once the base retriever is this much stronger — not a regression in what re-ranking does.

**Honesty check:** 19 questions is a small gold set. Treat these numbers as directional, not
statistically significant — a ~5pp swing is roughly one question's worth of difference.

**Known limitations** — two questions still don't retrieve the expected rule:
- *"Can a company send my personal data to a country outside the EU?"* (expects `Art. 44 GDPR`)
  retrieves adjacent international-transfer articles (46, 45, 49) instead of the general
  principle article.
- *"What administrative steps must a healthcare organization take to protect electronic health
  records?"* (expects `§ 164.308`, administrative safeguards) retrieves `§ 164.312` (technical
  safeguards) instead — a genuine confusion between two related but distinct HIPAA safeguard
  categories.

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`) with:

```
ANTHROPIC_API_KEY=your-api-key-here
VOYAGE_API_KEY=your-voyage-api-key-here
```

Build the vector database (reads `data/rulebooks/gdpr/` and `data/rulebooks/hipaa/` — 99 GDPR
articles and 149 HIPAA sections — chunks them, embeds them via Voyage AI, and stores them in
`./chroma_db`):

```
venv\Scripts\python.exe src\ingest.py
```

## Running it

**Audit a document from the command line** (recommended flags — self-verification and re-ranked
retrieval):

```
venv\Scripts\python.exe src\audit.py data\documents_to_check\github_privacy_policy.md --verify --rerank
```

**Ask a one-off question** with citations:

```
venv\Scripts\python.exe src\ask.py "Can a patient get a copy of their medical records?"
```

**Run the FastAPI backend:**

```
venv\Scripts\uvicorn.exe api:app --reload
```

**Run the React frontend** (in a second terminal):

```
cd landing
npm install
npm run dev
```

**Or run the simpler Streamlit UI instead of the API + frontend:**

```
venv\Scripts\streamlit.exe run app.py
```

Full command reference, architecture notes, and per-file explanations live in `CLAUDE.md`.

## Evaluation

```
venv\Scripts\python.exe eval\eval_retrieval.py
```

Retrieval-only, no Claude calls (see Results above for the current numbers). A second script,
`eval\eval_verification.py`, evaluates the self-verification step and makes real Claude API
calls — see `CLAUDE.md` for a cost estimate before running it.

## License

TODO(ritesh): no LICENSE file exists in this repo yet — add one (or state explicitly that this
is unlicensed/all-rights-reserved for now) before treating this as open source.
