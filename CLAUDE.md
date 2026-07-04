# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a final-year engineering project: an agentic RAG (Retrieval-Augmented Generation) assistant
that checks documents for GDPR/HIPAA compliance gaps. For each gap it finds, it shows the exact
cited rule/clause it relied on, and it runs a self-verification step afterward to catch and reduce
hallucinated citations before showing results to the user.

Tech stack: Python.

The retrieval piece (reading the rulebooks, chunking them, and storing them as searchable
embeddings) is in place; the rest of the pipeline (matching a document against retrieved rules,
citation checking, self-verification) still needs to be built. Update the sections below as more
of the project takes shape.

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
  Prints the answer plus the list of source citations it was given. No self-verification step yet —
  that's still to be built, and is the next planned step in the project overview above.
