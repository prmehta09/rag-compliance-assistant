"""Lets you type a question and see which GDPR/HIPAA rule chunks the retrieval
system thinks are the best match. Useful for sanity-checking retrieval quality
before building the full compliance-checking pipeline on top of it."""

import sys

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "compliance_rules"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 5
SNIPPET_LENGTH = 200


def get_question() -> str:
    """Take the question from a command-line argument, or ask for it if none was given."""
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


def print_results(question: str, results: dict) -> None:
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    print(f'\nTop {len(documents)} results for: "{question}"\n')
    for rank, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), start=1):
        similarity = distance_to_similarity(dist)
        snippet = doc[:SNIPPET_LENGTH].replace("\n", " ").strip()
        if len(doc) > SNIPPET_LENGTH:
            snippet += "..."

        print(f"{rank}. {meta['citation']}  [{meta['law']}]  (similarity: {similarity:.3f})")
        print(f"   {snippet}")
        print(f"   Source: {meta['source_file']}\n")


def main():
    question = get_question()
    if not question:
        print("No question given, exiting.")
        return

    print(f"Loading local embedding model '{EMBEDDING_MODEL}' and connecting to {CHROMA_DIR}...")
    collection = get_collection()

    results = collection.query(query_texts=[question], n_results=TOP_K)
    print_results(question, results)


if __name__ == "__main__":
    main()
