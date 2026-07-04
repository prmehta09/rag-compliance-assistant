"""Lets you type a question and see which GDPR/HIPAA rule chunks the retrieval
system thinks are the best match. Useful for sanity-checking retrieval quality
before building the full compliance-checking pipeline on top of it.

Also exposes query_rulebooks(), the shared retrieval function reused by
ask.py, audit.py, and eval/eval_retrieval.py, with an optional --rerank mode:
a free, local cross-encoder re-scores a larger candidate pool for better
ranking, at the cost of a bit more compute (no API calls either way)."""

import sys

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "compliance_rules"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_K = 5
CANDIDATE_POOL_SIZE = 20  # how many first-stage results the re-ranker gets to choose from
SNIPPET_LENGTH = 200

_cross_encoder = None  # lazy-loaded singleton so we only load the model once per run


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
    """Convert Chroma's squared-L2 distance into a 0-1 cosine similarity score.

    Our embeddings are unit-length vectors, so squared L2 distance and cosine
    similarity are directly related: squared_L2 = 2 - 2*cosine_similarity.
    """
    return 1 - (distance / 2)


def get_collection():
    """Connect to the local Chroma database using the same embedding model
    that was used to build it. Reused by ask.py so both scripts search
    the rulebooks the exact same way."""
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)


def get_cross_encoder():
    """Load the local cross-encoder re-ranker once and reuse it (it's slower
    to load than the embedding model, so we don't want to repeat that per
    question in a loop like eval_retrieval.py's)."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
    return _cross_encoder


def rerank_candidates(question: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Re-score a candidate pool with the cross-encoder and keep the top_k best.

    Unlike our embedding model (which scores the question and each chunk
    separately, then compares), a cross-encoder reads the question and a
    chunk TOGETHER and outputs one relevance score for that specific pair -
    slower per comparison, but much better at telling apart rules that use
    similar vocabulary (e.g. HIPAA's administrative/physical/technical
    safeguards sections).
    """
    cross_encoder = get_cross_encoder()
    pairs = [(question, c["text"]) for c in candidates]
    scores = cross_encoder.predict(pairs)
    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)
    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates[:top_k]


def query_rulebooks(collection, question: str, top_k: int = TOP_K, rerank: bool = False) -> list[dict]:
    """Find the top_k best-matching rule chunks for a question.

    Without rerank: a single fast embedding-based lookup, top_k results.
    With rerank: fetch a larger pool (CANDIDATE_POOL_SIZE) from the embedding
    search first, then have the cross-encoder re-score and re-order just that
    pool down to top_k - a "wide net, then sharp filter" two-stage design.
    """
    n_results = CANDIDATE_POOL_SIZE if rerank else top_k
    results = collection.query(query_texts=[question], n_results=n_results)
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

    print(f"Loading local embedding model '{EMBEDDING_MODEL}' and connecting to {CHROMA_DIR}...")
    collection = get_collection()

    if rerank:
        print(f"Loading local cross-encoder re-ranker '{CROSS_ENCODER_MODEL}' (downloads once, ~90MB)...")

    candidates = query_rulebooks(collection, question, top_k=TOP_K, rerank=rerank)
    print_results(question, candidates, rerank)


if __name__ == "__main__":
    main()
