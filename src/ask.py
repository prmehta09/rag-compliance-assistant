"""Answers a plain-language question about GDPR/HIPAA by combining our
retrieval system (search.py) with Claude: it finds the most relevant rule
chunks, then asks Claude to answer using ONLY those chunks and to cite the
exact rule for every claim. This is the "R" (retrieval) + "G" (generation)
of RAG working together."""

import os

from anthropic import Anthropic
from dotenv import load_dotenv

from search import TOP_K, get_collection, get_question

MODEL = "claude-haiku-4-5"  # fast, cheap model - plenty for answering from a handful of short rule chunks
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are a compliance assistant that answers questions about GDPR and HIPAA.

Rules you must follow:
- Answer ONLY using the rule excerpts provided below. Do not use outside knowledge.
- Write in plain, simple language a non-lawyer can understand.
- For every claim you make, cite the exact rule it comes from (e.g. "Art. 17 GDPR" or "§ 164.524").
- If the provided excerpts do not contain enough information to answer, say so plainly instead of guessing."""


def retrieve_chunks(question: str) -> list[dict]:
    """Find the top matching rule chunks for a question using our existing Chroma search."""
    collection = get_collection()
    results = collection.query(query_texts=[question], n_results=TOP_K)
    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append({"citation": meta["citation"], "law": meta["law"], "text": doc})
    return chunks


def build_user_message(question: str, chunks: list[dict]) -> str:
    """Combine the question with the retrieved rule excerpts into one prompt for Claude."""
    excerpt_blocks = "\n\n".join(
        f"[{c['law']} - {c['citation']}]\n{c['text']}" for c in chunks
    )
    return (
        f"Question: {question}\n\n"
        f"Here are the most relevant rule excerpts:\n\n{excerpt_blocks}"
    )


def load_api_key() -> str:
    """Load ANTHROPIC_API_KEY from the local .env file. Never hardcode the key itself."""
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found. Add it to a local .env file (see .env.example)."
        )
    return api_key


def ask_claude(client: Anthropic, question: str, chunks: list[dict]) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(question, chunks)}],
    )
    return next(block.text for block in response.content if block.type == "text")


def main():
    question = get_question()
    if not question:
        print("No question given, exiting.")
        return

    print("Step 1/3: Retrieving the most relevant rule chunks...")
    chunks = retrieve_chunks(question)

    print(f"Step 2/3: Asking Claude ({MODEL}) to answer using only those rules...")
    api_key = load_api_key()
    client = Anthropic(api_key=api_key)
    answer = ask_claude(client, question, chunks)

    print("Step 3/3: Done.\n")
    print(f'Question: "{question}"\n')
    print("Answer:")
    print(answer)
    print("\nSources given to the model:")
    for c in chunks:
        print(f"- {c['citation']} [{c['law']}]")


if __name__ == "__main__":
    main()
