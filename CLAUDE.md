# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a final-year engineering project: an agentic RAG (Retrieval-Augmented Generation) assistant
that checks documents for GDPR/HIPAA compliance gaps. For each gap it finds, it shows the exact
cited rule/clause it relied on, and it runs a self-verification step afterward to catch and reduce
hallucinated citations before showing results to the user.

Tech stack: Python.

The full pipeline is in place end to end: reading the rulebooks into a searchable vector database
(`src/ingest.py`), retrieval (`src/search.py`), question-answering with citations (`src/ask.py`),
document auditing against a curated checkpoint list (`src/audit.py`), and an independent
self-verification pass on top of the audit findings (`src/audit.py --verify`). Update the sections
below as more of the project takes shape (e.g. a richer report format, a UI, more checkpoints).

## Working rules

- **Always run the test suite before declaring a task done.** If no tests exist yet for the code
  you touched, say so explicitly instead of claiming the task is verified.
- **Never commit secrets.** API keys, tokens, and credentials (e.g. for the LLM provider or vector
  store) must only ever live in a local `.env` file or equivalent, which must stay out of git
  (add it to `.gitignore`). Never hardcode them in source files, notebooks, or commit messages.
- **Keep functions small and well-commented.** Favor short, single-purpose functions. Since this is
  a learning project, add brief comments explaining non-obvious steps — especially around the
  retrieval, citation-matching, and self-verification logic, which is easy to get lost in later.
- **Explain what you're doing in simple, beginner-friendly terms as you go.** The user is building
  this as a learning project, so narrate reasoning in plain language (e.g. what a step accomplishes
  and why) rather than assuming familiarity with RAG/agentic jargon.

## Commands

Set up the virtual environment and install dependencies (only needed once, or after
`requirements.txt` changes):

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the ingestion pipeline (reads `data/rulebooks/gdpr/` and `data/rulebooks/hipaa/`, chunks
them, embeds them locally, and stores them in `./chroma_db`):

```
venv\Scripts\python.exe src\ingest.py
```

Re-running `ingest.py` is safe — it deletes and rebuilds the collection each time instead of
duplicating chunks.

Search the rulebooks from the command line (prints the top 5 matching chunks with citation,
law, a text snippet, and a similarity score):

```
venv\Scripts\python.exe src\search.py "What are the rules about deleting someone's personal data?"
```

Or run it with no argument and it will prompt you to type a question.

Ask a question and get an answer generated from the retrieved rules, with citations (requires
`ANTHROPIC_API_KEY` set in a local `.env` file — see `.env.example`):

```
venv\Scripts\python.exe src\ask.py "Can a patient get a copy of their medical records?"
```

Or run it with no argument and it will prompt you to type a question.

Audit a document against a curated list of GDPR/HIPAA compliance checkpoints, printing a grouped
report and saving a copy to `reports/<document-name>_audit.md` (also requires `ANTHROPIC_API_KEY`):

```
venv\Scripts\python.exe src\audit.py data\documents_to_check\github_privacy_policy.md
```

Or run it with no argument and it defaults to auditing the GitHub sample privacy policy.

Add `--verify` to also run each finding through a second, independent Claude call that tries to
poke holes in it (catches over-stated findings, wrong citations, or claims the document/rules
don't actually support). Doubles the number of API calls. Findings flagged Questionable or
Unsupported are called out under "Needs Human Review" at the top of the report:

```
venv\Scripts\python.exe src\audit.py data\documents_to_check\github_privacy_policy.md --verify
```

Evaluate retrieval quality against a hand-curated gold standard set of questions (pure retrieval,
no API calls, free to run as often as you like). Prints Hit Rate @5 and Mean Reciprocal Rank (MRR)
plus a per-question hit/miss breakdown:

```
venv\Scripts\python.exe eval\eval_retrieval.py
```

No test suite exists yet.

## Architecture

- `data/rulebooks/gdpr/` and `data/rulebooks/hipaa/` — the source legal text, one file per
  article (GDPR) or section (HIPAA). See each folder's `README.md` for where the text came from.
- `src/ingest.py` — turns those files into a searchable vector database:
  1. Reads every rule file and strips off the header lines (title/citation/source), keeping just
     the legal text.
  2. Splits that text into overlapping chunks (~800 characters, ~150 character overlap) so long
     articles/sections are still searchable in reasonably small pieces.
  3. Embeds each chunk locally with the free `sentence-transformers` model `all-MiniLM-L6-v2` (no
     API key, runs on your own machine).
  4. Stores the chunks, their embeddings, and metadata (`law`, `citation`, `source_file`,
     `chunk_index`) in a local Chroma database at `./chroma_db`, so a later retrieval step can
     look up the best-matching rule and cite exactly where it came from.
- `./chroma_db/` — the persisted vector database. Ignored by git (regenerable by re-running
  `ingest.py`); don't hand-edit it.
- `src/search.py` — a manual test tool for the retrieval step: embeds a typed question with the
  same local model, queries Chroma for the top 5 matching chunks, and prints each one's citation,
  law, a text snippet, and a similarity score (converted from Chroma's distance metric). Also
  exposes `get_collection()`, reused by `ask.py` so both scripts search the same way.
- `src/ask.py` — the first full retrieval-plus-generation loop (the "R" and "G" of RAG): retrieves
  the top 5 matching rule chunks via `search.py`, then sends the question and those chunks to
  Claude (`claude-haiku-4-5`, loaded from `ANTHROPIC_API_KEY` in `.env` via `python-dotenv`) with a
  system prompt that restricts it to answering only from the provided rules, in plain language,
  citing the exact rule for every claim, and saying so if the rules don't contain the answer.
  Prints the answer plus the list of source citations it was given. `ask.py` itself has no
  self-verification step (that lives in `audit.py`, described below).
- `src/audit.py` — the core "audit a document" feature. For each entry in its `CHECKPOINTS` list
  (a curated, easily-extendable set of GDPR/HIPAA obligations - right to access, erasure, breach
  notification, security safeguards, etc.), it retrieves the matching rule chunks via
  `search.py`, then asks Claude to judge whether the document text addresses that obligation,
  responding in a fixed `STATUS:`/`CITATION:`/`EXPLANATION:` format that gets parsed and grouped
  into a report (Gaps shown first, since they're the most actionable). Sends the whole document
  per checkpoint (not just a keyword-matched excerpt) so judgments aren't skewed by truncation.
  Reuses `MODEL`/`load_api_key()` from `ask.py` and `get_collection()` from `search.py`.
  With `--verify`, each finding is passed - along with the same rule chunks and document text
  used to make it, but NOT the original reasoning process - to a second Claude call
  (`verify_finding()`) whose system prompt explicitly tells it to re-derive its own judgment
  independently rather than assume the first finding is correct, and to mark it Unsupported if the
  cited rule doesn't say what was claimed or the document doesn't support the stated status, or
  Questionable if something's imprecise or overstated. Verdicts are shown alongside each finding,
  and anything Questionable/Unsupported is surfaced in a "Needs Human Review" summary at the top of
  the report — this is the project's self-verification step, aimed at catching hallucinated or
  overstated findings before a human trusts them.
- `reports/` — audit reports saved by `audit.py`. Ignored by git (regenerable by re-running the
  audit); don't hand-edit it.
- `eval/gold_retrieval.json` — a hand-curated (not AI-generated) set of ~19 test questions spanning
  both GDPR and HIPAA, each with the rule citation(s) that a good retrieval system should surface.
  This is ground truth used to measure retrieval quality, not something to "fix" if scores are low -
  low scores mean the retrieval system needs improving, not the gold set.
- `eval/eval_retrieval.py` — runs each gold-set question through our normal retrieval (top-5) and
  checks whether the expected citation actually comes back, reporting Hit Rate @5 (what fraction of
  questions found the right rule at all) and Mean Reciprocal Rank (how high up it was ranked, on
  average). Purely local/free - no Claude API calls, since it only tests the embedding + Chroma
  retrieval step, not generation.
