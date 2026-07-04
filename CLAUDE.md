# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a final-year engineering project: an agentic RAG (Retrieval-Augmented Generation) assistant
that checks documents for GDPR/HIPAA compliance gaps. For each gap it finds, it shows the exact
cited rule/clause it relied on, and it runs a self-verification step afterward to catch and reduce
hallucinated citations before showing results to the user.

Tech stack: Python.

The repository is currently empty (no code has been written yet), so this file will need to be
expanded with real commands and architecture notes as the project takes shape. Whoever (human or
Claude) adds the first real module, test runner, or dependency file should update the sections
below rather than leaving them as placeholders.

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

No build, lint, or test commands exist yet since the codebase is empty. Once dependencies and a
test framework are set up (e.g. `pip install -r requirements.txt`, `pytest`), record the actual
commands here, including how to run a single test.

## Architecture

Not yet established. Once the project has real structure (e.g. document ingestion, retrieval
pipeline, compliance rule store, citation checker, self-verification pass), document the
high-level data flow here so future sessions don't have to re-derive it by reading every file.
