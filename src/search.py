"""Lets you type a question and see which GDPR/HIPAA rule chunks the retrieval
system thinks are the best match. Useful for sanity-checking retrieval quality
before building the full compliance-checking pipeline on top of it.

Also exposes query_rulebooks(), the shared retrieval function reused by
ask.py, audit.py, and eval/eval_retrieval.py, with an optional --rerank mode:
Voyage AI's hosted re-ranker re-scores a larger candidate pool for better
ranking, at the cost of one extra network call per question. Both embedding
and re-ranking are hosted calls now (see voyage_client.py) rather than local
models - needs VOYAGE_API_KEY in a local .env file (see .env.example)."""

import sys

import chromadb

from voyage_client import embed_texts, rerank as voyage_rerank

CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "compliance_rules"
TOP_K = 5
CANDIDATE_POOL_SIZE = 20  # how many first-stage results the re-ranker gets to choose from
SNIPPET_LENGTH = 200


def parse_args(argv: list[str]) -> tuple[str | None, bool]:
    """Pull out the --rerank flag; whatever's left (if anything) is the question."""
    rerank = "--rerank" in argv
    positional = [a for a in argv if a != "--rerank"]
    question = " ".join(positional) if positional else None
    return question, rerank


def get_question() -> str:
    """Take the question from a command-line argument, or ask for it if none was given.
    Kept as-is for ask.py, which doesn't use the --rerank flag."""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    return input("Ask a question about GDPR/HIPAA: ").strip()


def distance_to_similarity(distance: float) -> float:
    """Convert Chroma's cosine distance into a 0-1 cosine similarity score.

    The collection is configured with hnsw:space="cosine" (see ingest.py), so
    Chroma already returns true cosine distance = 1 - cosine_similarity -
    this is exact regardless of whether Voyage's embedding vectors happen to
    be unit-length, unlike the old squared-L2 shortcut this replaced.
    """
    return 1 - distance


def get_collection():
    """Connect to the local Chroma database. No embedding_function is
    attached - embeddings are computed via Voyage AI (see query_rulebooks())
    and supplied directly, so Chroma never loads a local model. Reused by
    ask.py so both scripts search the rulebooks the exact same way."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_collection(name=COLLECTION_NAME)


def rerank_candidates(question: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Re-score a candidate pool via Voyage AI's hosted re-ranker and keep the top_k best.

    Unlike embedding search (which scores the question and each chunk
    separately, then compares), a re-ranker reads the question and a chunk
    TOGETHER and outputs one relevance score for that specific pair - slower
    (a network call) but much better at telling apart rules that use similar
    vocabulary (e.g. HIPAA's administrative/physical/technical safeguards
    sections).
    """
    results = voyage_rerank(question, [c["text"] for c in candidates], top_k=top_k)
    reranked = []
    for r in results:
        candidate = candidates[r["index"]]
        candidate["rerank_score"] = r["relevance_score"]
        reranked.append(candidate)
    return reranked


def query_rulebooks(collection, question: str, top_k: int = TOP_K, rerank: bool = False) -> list[dict]:
    """Find the top_k best-matching rule chunks for a question.

    Without rerank: a single fast embedding-based lookup, top_k results.
    With rerank: fetch a larger pool (CANDIDATE_POOL_SIZE) from the embedding
    search first, then have Voyage's re-ranker re-score and re-order just
    that pool down to top_k - a "wide net, then sharp filter" two-stage
    design. Both stages are Voyage API calls now (see voyage_client.py).
    """
    n_results = CANDIDATE_POOL_SIZE if rerank else top_k
    query_embedding = embed_texts([question], input_type="query")[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    candidates = [
        {
            "citation": meta["citation"],
            "law": meta["law"],
            "text": doc,
            "distance": dist,
            "source_file": meta["source_file"],
        }
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ]
    if rerank:
        return rerank_candidates(question, candidates, top_k)
    return candidates[:top_k]


def print_results(question: str, candidates: list[dict], rerank: bool = False) -> None:
    mode_note = " (re-ranked)" if rerank else ""
    print(f'\nTop {len(candidates)} results for: "{question}"{mode_note}\n')
    for rank, c in enumerate(candidates, start=1):
        similarity = distance_to_similarity(c["distance"])
        score_note = f"similarity: {similarity:.3f}"
        if rerank:
            score_note += f", rerank score: {c['rerank_score']:.3f}"

        snippet = c["text"][:SNIPPET_LENGTH].replace("\n", " ").strip()
        if len(c["text"]) > SNIPPET_LENGTH:
            snippet += "..."

        print(f"{rank}. {c['citation']}  [{c['law']}]  ({score_note})")
        print(f"   {snippet}")
        print(f"   Source: {c['source_file']}\n")


def main():
    question, rerank = parse_args(sys.argv[1:])
    if question is None:
        question = input("Ask a question about GDPR/HIPAA: ").strip()
    if not question:
        print("No question given, exiting.")
        return

    print(f"Connecting to {CHROMA_DIR}...")
    collection = get_collection()

    if rerank:
        print("Re-ranking via Voyage AI's hosted re-ranker...")

    candidates = query_rulebooks(collection, question, top_k=TOP_K, rerank=rerank)
    print_results(question, candidates, rerank)


if __name__ == "__main__":
    main()
