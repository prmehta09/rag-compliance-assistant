"""Thin wrapper around Voyage AI's REST API for embeddings and re-ranking -
the hosted replacement for the local sentence-transformers models this
project used to run in-process.

Calls the API directly with `requests` instead of the official `voyageai`
SDK on purpose: the SDK pulls in langchain-core, langsmith, tokenizers, and
pillow as transitive dependencies, which measured ~400MB of extra RAM at
import time - enough to erase the entire point of moving off local
torch-based models to fit Render's free-tier 512MB limit. A couple of
requests.post() calls need none of that.
"""

import os
import time

import requests
from dotenv import load_dotenv

API_BASE = "https://api.voyageai.com/v1"
EMBEDDING_MODEL = "voyage-3.5-lite"
RERANK_MODEL = "rerank-2.5-lite"
REQUEST_TIMEOUT = 30  # seconds

# Retry/backoff for 429s - unverified Voyage accounts are throttled to 3
# RPM / 10K TPM, so hitting one mid-ingest (or mid-audit) is expected, not a
# bug. Exponential: 20s, 40s, 80s, then capped at 90s.
MAX_RETRIES = 6
BASE_BACKOFF_SECONDS = 20
MAX_BACKOFF_SECONDS = 90

# Loaded once at import time so every caller (ingest.py, search.py, ...) gets
# VOYAGE_API_KEY for free without each needing its own load_dotenv() call.
# No-ops harmlessly in production, where env vars come from the platform
# (e.g. Render's dashboard) rather than a local .env file.
load_dotenv()


def _headers() -> dict:
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "VOYAGE_API_KEY not found. Add it to a local .env file (see .env.example)."
        )
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _post_with_retry(url: str, payload: dict) -> dict:
    """POSTs to a Voyage endpoint, retrying only on 429 (rate limit) with
    backoff - honors the response's Retry-After header if present, otherwise
    doubles a base delay each attempt. Any other error status (401/403/5xx/
    etc.) raises immediately via raise_for_status(), same as before - only
    rate limits get retried, nothing is silently swallowed.
    """
    for retry_num in range(MAX_RETRIES + 1):  # first attempt + up to MAX_RETRIES retries
        response = requests.post(url, headers=_headers(), json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()

        if retry_num == MAX_RETRIES:
            raise RuntimeError(
                f"Voyage API still rate-limited after {MAX_RETRIES} retries - giving up ({url})."
            )

        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            wait_seconds = float(retry_after)
        else:
            wait_seconds = min(BASE_BACKOFF_SECONDS * (2 ** retry_num), MAX_BACKOFF_SECONDS)

        print(f"  429, backing off {wait_seconds:.0f}s (retry {retry_num + 1}/{MAX_RETRIES})")
        time.sleep(wait_seconds)


def embed_texts(texts: list[str], input_type: str) -> list[list[float]]:
    """Embeds a batch of texts via Voyage.

    `input_type` must be "query" or "document" - Voyage encodes each
    asymmetrically (its models are trained expecting this distinction), so
    ingest.py must use "document" for rule chunks and search.py must use
    "query" for questions, matching how the two sides will be compared.
    """
    body = _post_with_retry(
        f"{API_BASE}/embeddings",
        {"input": texts, "model": EMBEDDING_MODEL, "input_type": input_type},
    )
    # Items aren't guaranteed to come back in input order (each carries its
    # own "index"), so sort before returning.
    ordered = sorted(body["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in ordered]


def rerank(query: str, documents: list[str], top_k: int) -> list[dict]:
    """Re-scores `documents` against `query`, returning the top_k best as
    {"index": <position in the original `documents` list>, "relevance_score": float},
    ordered best-first.

    Results come back under "data" (like embed_texts()'s response, not
    "results" as Voyage's own docs described - confirmed against a live
    call). Sorted explicitly by relevance_score here rather than trusting
    the API to already return them in order, same caution embed_texts()
    already takes with its "index" field.
    """
    body = _post_with_retry(
        f"{API_BASE}/rerank",
        {"query": query, "documents": documents, "model": RERANK_MODEL, "top_k": top_k},
    )
    return sorted(body["data"], key=lambda item: item["relevance_score"], reverse=True)
